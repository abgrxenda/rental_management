# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class BulkSerialWizard(models.TransientModel):
    _name = 'bulk.serial.wizard'
    _description = 'Bulk Serial Number Generator'
    
    equipment_id = fields.Many2one(
        'rental.equipment',
        string='Equipment',
        required=True,
        readonly=True
    )
    
    quantity = fields.Integer(
        string='Number of Serials to Generate',
        required=True,
        default=1,
        help='How many serial numbers to generate'
    )
    
    prefix_override = fields.Char(
        string='Serial Prefix (Optional)',
        help='Override the default prefix. Leave empty to use equipment code'
    )
    
    starting_number = fields.Integer(
        string='Starting Number',
        default=1,
        help='The sequence will start from this number'
    )
    
    preview_serials = fields.Text(
        string='Preview',
        compute='_compute_preview_serials',
        help='Preview of serial numbers that will be generated'
    )
    
    @api.constrains('quantity')
    def _check_quantity(self):
        """Validate quantity is positive"""
        for wizard in self:
            if wizard.quantity <= 0:
                raise ValidationError(_('Quantity must be greater than zero.'))
            if wizard.quantity > 1000:
                raise ValidationError(_('Cannot generate more than 1000 serials at once.'))
    
    @api.depends('quantity', 'prefix_override', 'starting_number', 'equipment_id')
    def _compute_preview_serials(self):
        """Show preview of serial numbers that will be generated"""
        for wizard in self:
            if wizard.equipment_id and wizard.quantity > 0:
                prefix = wizard.prefix_override or wizard.equipment_id.code or 'SN'
                
                # Get current highest number for this equipment
                existing_serials = wizard.equipment_id.serial_ids
                start = wizard.starting_number
                
                # Generate preview (show first 10 if more than 10)
                preview_lines = []
                preview_count = min(wizard.quantity, 10)
                
                for i in range(preview_count):
                    serial_num = start + i
                    serial_name = f"{prefix}-{serial_num:04d}"
                    preview_lines.append(serial_name)
                
                if wizard.quantity > 10:
                    preview_lines.append(f"... and {wizard.quantity - 10} more")
                
                wizard.preview_serials = "\n".join(preview_lines)
            else:
                wizard.preview_serials = "Enter quantity to see preview"
    
    def action_generate_serials(self):
        """Generate the serial numbers"""
        self.ensure_one()
        
        if not self.equipment_id.has_serials:
            raise UserError(_('This equipment does not have serial tracking enabled.'))
        
        # Prepare prefix
        prefix = self.prefix_override or self.equipment_id.code or 'SN'
        
        # Get starting number
        start_num = self.starting_number
        
        # Check for existing serials to avoid duplicates
        existing_serials = self.equipment_id.serial_ids.mapped('serial_number')
        
        # Generate serials
        created_serials = []
        skipped = []
        
        for i in range(self.quantity):
            serial_num = start_num + i
            serial_name = f"{prefix}-{serial_num:04d}"
            
            # Check if already exists
            if serial_name in existing_serials:
                skipped.append(serial_name)
                continue
            
            # Create serial
            serial = self.env['rental.equipment.serial'].create({
                'equipment_id': self.equipment_id.id,
                'serial_number': serial_name,
                'status': 'available',
            })
            created_serials.append(serial)
        
        # Show success message
        message = f"Successfully generated {len(created_serials)} serial number(s)."
        if skipped:
            message += f"\nSkipped {len(skipped)} duplicate(s): {', '.join(skipped[:5])}"
            if len(skipped) > 5:
                message += f" and {len(skipped) - 5} more"
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Serials Generated'),
                'message': message,
                'type': 'success',
                'sticky': False,
                'next': {
                    'type': 'ir.actions.act_window_close'
                }
            }
        }