
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class RentalPickupWizard(models.TransientModel):
    _name = 'rental.pickup.wizard'
    _description = 'Partial Equipment Pickup Wizard'
    
    project_id = fields.Many2one(
        'rental.project',
        'Project',
        required=True,
        readonly=True
    )
    pickup_date = fields.Date(
        'Pickup Date',
        required=True,
        default=fields.Date.today
    )
    serial_ids = fields.Many2many(
        'rental.equipment.serial',
        'pickup_wizard_serial_rel',
        'wizard_id',
        'serial_id',
        string='Serials to Pickup',
        domain="[('current_project_id', '=', project_id), ('status', '=', 'reserved')]"
    )
    pickup_signature = fields.Binary('Customer Signature')
    notes = fields.Text('Pickup Notes')
    
    @api.model
    def default_get(self, fields_list):
        """Pre-populate with reserved serials"""
        res = super().default_get(fields_list)
        
        project_id = self.env.context.get('default_project_id')
        if project_id:
            project = self.env['rental.project'].browse(project_id)
            
            # Get all reserved serials for this project
            reserved_serials = self.env['rental.equipment.serial'].search([
                ('current_project_id', '=', project.id),
                ('status', '=', 'reserved')
            ])
            
            res['serial_ids'] = [(6, 0, reserved_serials.ids)]
        
        return res
    
    def action_confirm_pickup(self):
        """Mark selected serials as picked up"""
        self.ensure_one()
        
        if not self.serial_ids:
            raise UserError(_('Please select at least one serial to pickup.'))
        
        # Validate pickup date
        if self.pickup_date < self.project_id.start_date:
            raise ValidationError(_(
                'Pickup date cannot be before project start date (%s).'
            ) % self.project_id.start_date)
        
        if self.pickup_date > self.project_id.end_date:
            raise ValidationError(_(
                'Pickup date cannot be after project end date (%s).'
            ) % self.project_id.end_date)
        
        # Update serials
        for serial in self.serial_ids:
            serial.write({
                'status': 'rented',
                'actual_pickup_date': self.pickup_date
            })
            
            # Log pickup in status history
            self.env['rental.project.item.status'].create({
                'project_id': self.project_id.id,
                'equipment_id': serial.equipment_id.id,
                'serial_id': serial.id,
                'status': 'rented',
                'notes': f'Picked up on {self.pickup_date}. {self.notes or ""}'
            })
        
        # Update project state if first pickup
        if self.project_id.state == 'reserved':
            self.project_id.write({'state': 'ongoing'})
        # IMPORTANT: Return action to reload the form with updated values
        return {
            'type': 'ir.actions.act_window',
            'name': _('Pickup Confirmed'),
            'res_model': 'rental.pickup.wizard',
            'res_id': self.id,  # Keep the same wizard record
            'view_mode': 'form',
            'target': 'new',
            'context': self.env.context,
        }
