# Key Features:

# Mail tracking - Activity feed and chatter
# Serial tracking - Optional with auto-generation
# Stock computation - Real-time available/reserved/rented counts
# Multiple pricing - Daily, weekly, monthly rates
# Validation - At least one rate must be set
# Smart buttons - View serials and rental history
# Availability check - Method for date-based availability

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class RentalEquipment(models.Model):
    _name = 'rental.equipment'
    _description = 'Rental Equipment/Item'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, name'
    
    name = fields.Char('Item Name', required=True, tracking=True, index=True)
    code = fields.Char('Item Code', copy=False, index=True)
    description = fields.Text('Description', translate=True)
    notes = fields.Text('Internal Notes')
    
    # Item Details
    item_value = fields.Float('Item Value/Purchase Price', tracking=True)
    has_serials = fields.Boolean(
        'Track Serial Numbers', 
        default=False,
        help='Enable serial number tracking for this equipment'
    )
    auto_generate_serials = fields.Boolean(
        'Auto-Generate Serials',
        default=False,
        help='Automatically generate serial numbers when added to projects'
    )
    
    # Stock Management
    total_stock = fields.Integer(
        'Total Stock', 
        compute='_compute_stock', 
        store=True,
        help='Total number of units/serials'
    )
    available_stock = fields.Integer(
        'Available Stock', 
        compute='_compute_stock', 
        store=True,
        help='Number of available units/serials'
    )
    reserved_stock = fields.Integer(
        'Reserved Stock',
        compute='_compute_stock',
        store=True
    )
    rented_stock = fields.Integer(
        'Currently Rented',
        compute='_compute_stock',
        store=True
    )
    
    # Pricing
    daily_rate = fields.Float('Daily Rate', tracking=True)
    weekly_rate = fields.Float('Weekly Rate', tracking=True)
    monthly_rate = fields.Float('Monthly Rate', tracking=True)
    
    # Media
    image = fields.Binary('Image', attachment=True)
    image_filename = fields.Char('Image Filename')
    
    # Categories (Many2many - equipment can have multiple categories)
    category_ids = fields.Many2many(
        'rental.equipment.category',
        'rental_equipment_category_rel',
        'equipment_id',
        'category_id',
        string='Categories'
    )
    
    # Relations
    serial_ids = fields.One2many(
        'rental.equipment.serial',
        'equipment_id',
        'Serial Numbers'
    )
    project_item_ids = fields.One2many(
        'rental.project.item',
        'equipment_id',
        'Rental History'
    )
    
    # Status
    sequence = fields.Integer('Sequence', default=10)
    active = fields.Boolean('Active', default=True)
    
    # Computed fields for UI
    serial_count = fields.Integer(
        'Serial Count',
        compute='_compute_serial_count'
    )
    rental_count = fields.Integer(
        'Rental Count',
        compute='_compute_rental_count'
    )
    
    @api.depends('serial_ids', 'serial_ids.status')
    def _compute_stock(self):
        """Calculate stock levels based on serial statuses"""
        for equipment in self:
            if equipment.has_serials:
                serials = equipment.serial_ids
                equipment.total_stock = len(serials)
                equipment.available_stock = len(serials.filtered(lambda s: s.status == 'available'))
                equipment.reserved_stock = len(serials.filtered(lambda s: s.status == 'reserved'))
                equipment.rented_stock = len(serials.filtered(lambda s: s.status == 'rented'))
            else:
                # For non-serialized items, set to 0 or implement quantity-based logic
                equipment.total_stock = 0
                equipment.available_stock = 0
                equipment.reserved_stock = 0
                equipment.rented_stock = 0
    
    def _compute_serial_count(self):
        """Count total serials"""
        for equipment in self:
            equipment.serial_count = len(equipment.serial_ids)
    
    def _compute_rental_count(self):
        """Count rental history"""
        for equipment in self:
            equipment.rental_count = len(equipment.project_item_ids)
    
    @api.constrains('daily_rate', 'weekly_rate', 'monthly_rate')
    def _check_rates(self):
        """Validate that at least one rate is set"""
        for equipment in self:
            if not any([equipment.daily_rate, equipment.weekly_rate, equipment.monthly_rate]):
                raise ValidationError(_('Please set at least one rental rate (Daily, Weekly, or Monthly).'))
    
    @api.model
    def create(self, vals):
        """Generate code if not provided"""
        if not vals.get('code'):
            vals['code'] = self.env['ir.sequence'].next_by_code('rental.equipment') or 'EQ-NEW'
        return super().create(vals)
    
    def action_view_serials(self):
        """Open serials list for this equipment"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Serial Numbers'),
            'res_model': 'rental.equipment.serial',
            'view_mode': 'list,form',
            'domain': [('equipment_id', '=', self.id)],
            'context': {'default_equipment_id': self.id}
        }
    
    def action_view_rental_history(self):
        """Open rental history for this equipment"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Rental History'),
            'res_model': 'rental.project.item',
            'view_mode': 'list,form',
            'domain': [('equipment_id', '=', self.id)],
        }

    def action_open_bulk_serial_wizard(self):
        """Open wizard to bulk generate serial numbers"""
        self.ensure_one()
        
        if not self.has_serials:
            raise UserError(_('This equipment does not have serial tracking enabled.'))
        
        # Calculate suggested starting number
        existing_serials = self.serial_ids
        suggested_start = len(existing_serials) + 1
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Generate Serial Numbers'),
            'res_model': 'bulk.serial.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_equipment_id': self.id,
                'default_starting_number': suggested_start,
            }
        }
    
    def check_availability(self, quantity, start_date, end_date):
        """Check if equipment is available for given dates and quantity"""
        self.ensure_one()
        
        if not self.has_serials:
            # For non-serialized items, simple stock check
            return self.available_stock >= quantity
        
        # For serialized items, check available serials
        available_serials = self.serial_ids.filtered(lambda s: s.status == 'available')
        
        # TODO: Check if any reserved/rented serials will be available in the date range
        # This requires checking project dates
        
        return len(available_serials) >= quantity