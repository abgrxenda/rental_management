# Key Features:

# Automatic pricing - Calculates unit price based on duration and equipment rates
# Serial assignment - Auto-assign or manual selection
# Auto-generation - Generate serials on-the-fly if enabled
# Stock validation - Warns if insufficient stock
# Serial tracking - Track which serials are assigned to each line
# Status transitions - Reserve → Rent → Return flow
# Photo documentation - Photos per line item
# History logging - Log all serial status changes
# Quantity matching - Ensures serials match quantity for serialized items
# Smart buttons - View/manage assigned serials

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError


class RentalProjectItem(models.Model):
    _name = 'rental.project.item'
    _description = 'Rental Project Line Item'
    _order = 'project_id, sequence, id'
    
    project_id = fields.Many2one(
        'rental.project',
        'Project',
        required=True,
        ondelete='cascade',
        index=True
    )
    project_state = fields.Selection(
        related='project_id.state',
        string='Project Status',
        readonly=True,
        store=True
    )
    
    # Equipment Information
    equipment_id = fields.Many2one(
        'rental.equipment',
        'Equipment',
        required=True,
        index=True
    )
    equipment_code = fields.Char(
        'Equipment Code',
        related='equipment_id.code',
        readonly=True
    )
    equipment_has_serials = fields.Boolean(
        'Has Serials',
        related='equipment_id.has_serials',
        readonly=True
    )
    
    # Quantity and Serials
    quantity = fields.Integer(
        'Quantity',
        required=True,
        default=1,
        help='Number of units to rent'
    )
    assigned_serial_ids = fields.Many2many(
        'rental.equipment.serial',
        'rental_project_item_serial_rel',
        'item_id',
        'serial_id',
        string='Assigned Serials',
        help='Specific serial numbers assigned to this line'
    )
    assigned_serial_count = fields.Integer(
        'Assigned Serial Count',
        compute='_compute_assigned_serial_count'
    )
    serial_numbers_text = fields.Char(
        'Serial Numbers',
        compute='_compute_serial_numbers_text',
        help='Display list of assigned serial numbers'
    )
    
    # Pricing
    unit_price = fields.Float(
        'Unit Price',
        compute='_compute_unit_price',
        store=True,
        readonly=False,
        help='Price per unit for the rental period'
    )
    subtotal = fields.Float(
        'Subtotal',
        compute='_compute_subtotal',
        store=True
    )
    
    # Photos and Documentation
    image_ids = fields.Many2many(
        'ir.attachment',
        'rental_project_item_image_rel',
        'item_id',
        'attachment_id',
        string='Photos'
    )
    notes = fields.Text('Notes')
    
    sequence = fields.Integer('Sequence', default=10)
    
    # Compute Methods
    
    def _compute_assigned_serial_count(self):
        for item in self:
            item.assigned_serial_count = len(item.assigned_serial_ids)
    
    def _compute_serial_numbers_text(self):
        for item in self:
            if item.assigned_serial_ids:
                serials = item.assigned_serial_ids.mapped('serial_number')
                item.serial_numbers_text = ', '.join(serials)
            else:
                item.serial_numbers_text = ''
    
    @api.depends('equipment_id', 'project_id.duration_days')
    def _compute_unit_price(self):
        """Calculate unit price based on rental duration and equipment rates"""
        for item in self:
            if not item.equipment_id or not item.project_id:
                item.unit_price = 0.0
                continue
            
            duration = item.project_id.duration_days
            equipment = item.equipment_id
            
            # Determine best rate based on duration
            if duration >= 30 and equipment.monthly_rate:
                # Use monthly rate
                months = duration / 30.0
                item.unit_price = equipment.monthly_rate * months
            elif duration >= 7 and equipment.weekly_rate:
                # Use weekly rate
                weeks = duration / 7.0
                item.unit_price = equipment.weekly_rate * weeks
            else:
                # Use daily rate
                item.unit_price = equipment.daily_rate * duration
    
    @api.depends('quantity', 'unit_price')
    def _compute_subtotal(self):
        for item in self:
            item.subtotal = item.quantity * item.unit_price
    
    # Constraints
    
    @api.constrains('quantity')
    def _check_quantity(self):
        for item in self:
            if item.quantity <= 0:
                raise ValidationError(_('Quantity must be greater than zero.'))
    
    @api.constrains('quantity', 'equipment_has_serials')
    def _check_serial_quantity_match(self):
        """Ensure assigned serials match quantity for serialized items"""
        for item in self:
            if item.equipment_has_serials and item.project_state not in ['draft', 'cancelled']:
                if len(item.assigned_serial_ids) != item.quantity:
                    raise ValidationError(_(
                        'Number of assigned serials (%d) must match quantity (%d) for %s.'
                    ) % (len(item.assigned_serial_ids), item.quantity, item.equipment_id.name))
    
    # Onchange Methods
    
    @api.onchange('equipment_id')
    def _onchange_equipment_id(self):
        """Check availability when equipment is selected"""
        if self.equipment_id:
            # Check if enough stock is available
            if self.equipment_has_serials:
                available = self.equipment_id.available_stock
                if self.quantity > available:
                    return {
                        'warning': {
                            'title': _('Insufficient Stock'),
                            'message': _(
                                'Only %d unit(s) available. You requested %d.'
                            ) % (available, self.quantity)
                        }
                    }
    
    @api.onchange('quantity')
    def _onchange_quantity(self):
        """Warn if quantity exceeds available stock"""
        if self.equipment_id and self.equipment_has_serials:
            available = self.equipment_id.available_stock
            if self.quantity > available:
                return {
                    'warning': {
                        'title': _('Insufficient Stock'),
                        'message': _(
                            'Only %d unit(s) available. You requested %d.'
                        ) % (available, self.quantity)
                    }
                }
            # NEW: Auto-assign serials if in draft and we have enough
            if self.project_state == 'draft' and self.quantity > 0:
                # Check if we need to adjust assignments
                current_count = len(self.assigned_serial_ids)
                
                if self.quantity > current_count:
                    # Need more serials - auto-assign
                    self._auto_assign_serials()
                elif self.quantity < current_count:
                    # Need fewer serials - remove excess
                    serials_to_remove = self.assigned_serial_ids[:current_count - self.quantity]
                    self.assigned_serial_ids = [(3, serial.id) for serial in serials_to_remove]    
    
    # Serial Management Methods
    
    # NEW METHOD - Add right BEFORE action_reserve_serials
    def _auto_assign_serials(self):
        """
        Automatically assign available serials to this item.
        Called during draft state when quantity is set.
        """
        if not self.equipment_has_serials or not self.equipment_id:
            return
        
        # Only auto-assign in draft state
        if self.project_state != 'draft':
            return
        
        # Get currently assigned serials
        current_assigned = self.assigned_serial_ids
        current_count = len(current_assigned)
        
        # Calculate how many more we need
        needed = self.quantity - current_count
        
        if needed <= 0:
            return  # We have enough or too many
        
        # Get available serials (not already assigned to this item)
        available_serials = self.equipment_id.serial_ids.filtered(
            lambda s: s.status == 'available' and s.id not in current_assigned.ids
        )
        
        if len(available_serials) < needed:
            # Not enough available - check if we should auto-generate
            if self.equipment_id.auto_generate_serials:
                shortage = needed - len(available_serials)
                for i in range(shortage):
                    self.env['rental.equipment.serial'].create({
                        'equipment_id': self.equipment_id.id,
                        'status': 'available'
                    })
                # Refresh available serials
                available_serials = self.equipment_id.serial_ids.filtered(
                    lambda s: s.status == 'available' and s.id not in current_assigned.ids
                )
        
        # Assign serials (take first N available)
        serials_to_assign = available_serials[:needed]
        
        if serials_to_assign:
            # Add to assigned serials (using command 4 to link)
            self.assigned_serial_ids = [(4, serial.id) for serial in serials_to_assign]

    def action_reserve_serials(self):
        """Reserve/assign serials for this item"""
        self.ensure_one()
        
        if not self.equipment_has_serials:
            return  # Nothing to do for non-serialized items
        
        # Check if already has serials assigned
        if self.assigned_serial_ids:
            # Update status to reserved
            self.assigned_serial_ids.write({
                'status': 'reserved',
                'current_project_id': self.project_id.id
            })
            return
        
        # Need to assign new serials
        equipment = self.equipment_id
        
        # Get available serials
        available_serials = equipment.serial_ids.filtered(lambda s: s.status == 'available')
        
        if len(available_serials) < self.quantity:
            # Check if we should auto-generate
            if equipment.auto_generate_serials:
                # Generate missing serials
                needed = self.quantity - len(available_serials)
                for i in range(needed):
                    self.env['rental.equipment.serial'].create({
                        'equipment_id': equipment.id,
                        'status': 'available'
                    })
                # Re-fetch available serials
                available_serials = equipment.serial_ids.filtered(lambda s: s.status == 'available')
            else:
                raise UserError(_(
                    'Insufficient serials for %s. Need %d, found %d. Please add more serials or enable auto-generation.'
                ) % (equipment.name, self.quantity, len(available_serials)))
        
        # Assign serials (take first N available)
        serials_to_assign = available_serials[:self.quantity]
        
        # Update serials
        serials_to_assign.write({
            'status': 'reserved',
            'current_project_id': self.project_id.id
        })
        
        # Link to this item
        self.assigned_serial_ids = [(6, 0, serials_to_assign.ids)]
        
        # Log status history
        for serial in serials_to_assign:
            self.env['rental.project.item.status'].create({
                'project_id': self.project_id.id,
                'equipment_id': self.equipment_id.id,
                'serial_id': serial.id,
                'quantity': 1,
                'status': 'reserved',
                'notes': f'Serial {serial.serial_number} reserved for project {self.project_id.name}'
            })
    
    def action_start_rental(self):
        """Change serial status from reserved to rented"""
        self.ensure_one()
        
        if not self.equipment_has_serials:
            return
        
        self.assigned_serial_ids.write({'status': 'rented'})
        
        # Log status change
        for serial in self.assigned_serial_ids:
            self.env['rental.project.item.status'].create({
                'project_id': self.project_id.id,
                'equipment_id': self.equipment_id.id,
                'serial_id': serial.id,
                'quantity': 1,
                'status': 'rented',
                'notes': f'Rental started for serial {serial.serial_number}'
            })
    
    def action_complete_return(self):
        """Mark serials as returned and available"""
        self.ensure_one()
        
        if not self.equipment_has_serials:
            return
        
        # Change status to returned, then available
        self.assigned_serial_ids.write({
            'status': 'returned',
            'current_project_id': False
        })
        
        # Log return
        for serial in self.assigned_serial_ids:
            self.env['rental.project.item.status'].create({
                'project_id': self.project_id.id,
                'equipment_id': self.equipment_id.id,
                'serial_id': serial.id,
                'quantity': 1,
                'status': 'returned',
                'notes': f'Serial {serial.serial_number} returned'
            })
        
        # Set to available after a brief moment (simulating inspection)
        # In real scenario, this might be done manually after inspection
        self.assigned_serial_ids.write({'status': 'available'})
    
    def action_release_serials(self):
        """Release serials (cancel reservation)"""
        self.ensure_one()
        
        if not self.equipment_has_serials:
            return
        
        self.assigned_serial_ids.write({
            'status': 'available',
            'current_project_id': False
        })
        
        self.assigned_serial_ids = [(5, 0, 0)]  # Unlink all
    
    def action_view_serials(self):
        """View assigned serials"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Assigned Serials'),
            'res_model': 'rental.equipment.serial',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.assigned_serial_ids.ids)],
            'context': {'default_equipment_id': self.equipment_id.id}
        }
    
    def action_assign_serials_wizard(self):
        """Open wizard to manually select serials"""
        self.ensure_one()
        
        # Get available serials for this equipment
        available_serials = self.equipment_id.serial_ids.filtered(
            lambda s: s.status == 'available' or s.id in self.assigned_serial_ids.ids
        )
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Select Serial Numbers'),
            'res_model': 'serial.selection.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_project_item_id': self.id,
                'default_equipment_id': self.equipment_id.id,
                'default_quantity_needed': self.quantity,
                'default_currently_assigned_ids': [(6, 0, self.assigned_serial_ids.ids)],
                'available_serial_ids': available_serials.ids,
            }
        }