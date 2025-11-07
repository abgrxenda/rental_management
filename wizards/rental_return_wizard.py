# Key Features:

# Item-by-item assessment - Check each serial/item individually
# Condition tracking - Good, Minor Damage, Damaged, Lost
# Auto-calculated fees - Based on condition and settings
# Photo documentation - Attach photos per item
# Digital signature - Capture customer signature
# Status updates - Automatically update serial statuses
# History logging - Create status history entries
# Activity creation - Schedule follow-up for damaged items
# Smart defaults - Pre-populate with project items
# Total calculation - Sum all damage fees

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class RentalReturnWizard(models.TransientModel):
    _name = 'rental.return.wizard'
    _description = 'Equipment Return Wizard'
    
    project_id = fields.Many2one(
        'rental.project',
        'Project',
        required=True,
        readonly=True
    )
    actual_return_date = fields.Date(
        'Actual Return Date',
        required=True,
        default=fields.Date.today
    )

    # Return assessment for each item
    item_line_ids = fields.One2many(
        'rental.return.wizard.line',
        'wizard_id',
        'Items'
    )

    # Overall assessment
    has_damage = fields.Boolean('Has Damage')
    total_damage_fee = fields.Float(
        'Total Damage Fee',
        compute='_compute_total_damage_fee'
    )

    # Return signature and photos
    return_signature = fields.Binary('Customer Signature')
    return_photos = fields.Many2many(
        'ir.attachment',
        'partial_return_wizard_photo_rel',
        'wizard_id',
        'attachment_id',
        string='Return Photos'
    )

    notes = fields.Text('Return Notes')

    @api.depends('item_line_ids.damage_fee')
    def _compute_total_damage_fee(self):
        for wizard in self:
            wizard.total_damage_fee = sum(wizard.item_line_ids.mapped('damage_fee'))

    @api.model
    def default_get(self, fields_list):
        """Populate wizard with project items"""
        res = super().default_get(fields_list)
        
        project_id = self.env.context.get('default_project_id') or self.env.context.get('active_id')
        if project_id:
            project = self.env['rental.project'].browse(project_id)
            res['project_id'] = project.id
            
            # Create lines for each item in the project
            lines = []
            for item in project.item_ids:
                # Create a line for each assigned serial
                if item.equipment_has_serials and item.assigned_serial_ids:
                    for serial in item.assigned_serial_ids:
                        line_vals = {
                            'equipment_id': item.equipment_id.id,
                            'serial_id': serial.id,  # Explicitly set serial_id
                            'quantity': 1,
                            'condition': 'good',
                            'damage_fee': 0.0
                        }
                        lines.append((0, 0, line_vals))
                else:
                    # For non-serialized items, create one line
                    line_vals = {
                        'equipment_id': item.equipment_id.id,
                        'serial_id': False,
                        'quantity': item.quantity,
                        'condition': 'good',
                        'damage_fee': 0.0
                    }
                    lines.append((0, 0, line_vals))
            
            res['item_line_ids'] = lines
        
        return res

    def action_complete_return(self):
        """Complete the return process"""
        self.ensure_one()
        
        # Check if any items have damage
        has_any_damage = any(line.condition != 'good' for line in self.item_line_ids)
        
        # Update project with return information
        self.project_id.write({
            'actual_return_date': self.actual_return_date,
            'damage_fee': self.total_damage_fee,
            'has_damage': has_any_damage,  # NEW: Set has_damage flag
            'return_signature': self.return_signature,
            'return_photos': [(6, 0, self.return_photos.ids)]
        })
        
        # Process each return line
        for line in self.item_line_ids:
            line.action_process_return()
        
        # Mark project as returned
        self.project_id.action_complete_return()
        
        # If has damage, create activity for follow-up
        if has_any_damage or self.total_damage_fee > 0:
            self.project_id.activity_schedule(
                'mail.mail_activity_data_todo',
                summary=_('Follow up on damaged equipment'),
                note=_('Equipment returned with damage. Total damage fee: %s. Notes: %s') % (
                    self.total_damage_fee, self.notes or 'None'
                ),
                user_id=self.env.user.id
            )
        
        # return {
        #     'type': 'ir.actions.client',
        #     'tag': 'display_notification',
        #     'params': {
        #         'title': _('Return Complete'),
        #         'message': _('Equipment returned successfully.%s') % (
        #             f' Damage fee: {self.total_damage_fee}' if self.total_damage_fee > 0 else ''
        #         ),
        #         'type': 'warning' if has_any_damage else 'success',
        #         'sticky': False,
        #     }
        # }

class RentalReturnWizardLine(models.TransientModel):
    _name = 'rental.return.wizard.line'
    _description = 'Return Wizard Line'

    wizard_id = fields.Many2one(
        'rental.return.wizard',
        string='Wizard',
        required=True,
        ondelete='cascade'
    )

    equipment_id = fields.Many2one(
        'rental.equipment',
        string='Equipment',
        required=True
    )

    equipment_name = fields.Char(
        string='Equipment Name',
        related='equipment_id.name',
        readonly=True
    )

    serial_id = fields.Many2one(
        'rental.equipment.serial',
        string='Serial Number'
    )

    serial_number = fields.Char(
        string='Serial',
        related='serial_id.serial_number',
        readonly=True
    )

    quantity = fields.Integer('Quantity', default=1)

    # Return assessment
    condition = fields.Selection([
        ('good', 'Good Condition'),
        ('minor_damage', 'Minor Damage'),
        ('damaged', 'Damaged'),
        ('lost', 'Lost')
    ], string='Condition', default='good', required=True)

    damage_description = fields.Text('Damage Description')
    damage_fee = fields.Float('Damage/Repair Fee', default=0.0)

    # Photos for this specific item
    photo_ids = fields.Many2many(
        'ir.attachment',
        'return_line_photo_rel',
        'line_id',
        'attachment_id',
        string='Photos'
    )

    @api.onchange('condition')
    def _onchange_condition(self):
        """Auto-fill damage fee based on condition and settings"""
        if self.condition == 'good':
            self.damage_fee = 0.0
        elif self.condition == 'minor_damage':
            # Suggest minor damage fee from settings
            param = self.env['ir.config_parameter'].sudo()
            self.damage_fee = float(param.get_param('rental.damage_minor_threshold', 100))
        elif self.condition == 'damaged':
            # Suggest moderate damage fee from settings
            param = self.env['ir.config_parameter'].sudo()
            self.damage_fee = float(param.get_param('rental.damage_moderate_threshold', 500))
        elif self.condition == 'lost':
            # Suggest full equipment value
            if self.equipment_id:
                self.damage_fee = self.equipment_id.item_value or 1000.0

        # Update wizard's has_damage flag
        if self.condition != 'good':
            self.wizard_id.has_damage = True

    def action_process_return(self):
        """Process this return line"""
        self.ensure_one()
        
        # Debug log
        import logging
        _logger = logging.getLogger(__name__)
        _logger.info(f"Processing return for equipment: {self.equipment_id.name}, serial: {self.serial_id.serial_number if self.serial_id else 'None'}, condition: {self.condition}")
        
        if self.serial_id:
            # Determine new status based on condition
            if self.condition == 'good':
                new_status = 'returned'
            elif self.condition == 'minor_damage':
                new_status = 'damaged'
            elif self.condition == 'damaged':
                new_status = 'repairing'
            elif self.condition == 'lost':
                new_status = 'disposed'
            else:
                new_status = 'returned'
            
            # Update serial status
            self.serial_id.write({
                'status': new_status,
                'current_project_id': False if new_status in ['returned', 'disposed'] else self.wizard_id.project_id.id
            })
            
            _logger.info(f"Updated serial {self.serial_id.serial_number} status to: {new_status}")
            
            # Determine damage severity
            damage_severity = None
            if self.condition == 'minor_damage':
                damage_severity = 'minor'
            elif self.condition in ['damaged', 'lost']:
                damage_severity = 'severe'
            
            # Create detailed status history entry
            condition_label = dict(self._fields['condition'].selection).get(self.condition)
            notes = f"Returned in {condition_label} condition"
            if self.damage_description:
                notes += f"\nDetails: {self.damage_description}"
            if self.damage_fee > 0:
                notes += f"\nDamage fee: ${self.damage_fee}"
            
            # Create status history
            self.env['rental.project.item.status'].create({
                'project_id': self.wizard_id.project_id.id,
                'equipment_id': self.equipment_id.id,
                'serial_id': self.serial_id.id,
                'status': new_status,
                'notes': notes,
                'damage_description': self.damage_description,
                'damage_severity': damage_severity,
                'repair_cost_estimate': self.damage_fee if self.damage_fee > 0 else 0.0,
                'photo_ids': [(6, 0, self.photo_ids.ids)] if self.photo_ids else False
            })
            
            _logger.info(f"Created status history for serial {self.serial_id.serial_number}")
        
        # Update wizard's has_damage flag
        if self.condition != 'good':
            self.wizard_id.has_damage = True