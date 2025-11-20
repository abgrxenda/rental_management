
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
    line_ids = fields.One2many(
        'rental.pickup.wizard.line',
        'wizard_id',
        'Serials to Pickup'
    )
    pickup_signature = fields.Image(
        string='Customer Signature',
        required=True,
        max_width=1024,
        max_height=1024,
        help='Draw signature using mouse or stylus'
    )
    notes = fields.Text('Pickup Notes')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        project_id = self.env.context.get('default_project_id')
        if project_id:
            project = self.env['rental.project'].browse(project_id)
            # Get all reserved serials for this project
            reserved_serials = self.env['rental.equipment.serial'].search([
                ('current_project_id', '=', project.id),
                ('status', '=', 'reserved')
            ])
            lines = []
            for serial in reserved_serials:
                lines.append((0, 0, {
                    'serial_id': serial.id,
                    'equipment_id': serial.equipment_id.id,
                    'to_pickup': True,  # default checked
                }))
            res['line_ids'] = lines
        return res

    def action_confirm_pickup(self):
        self.ensure_one()
        lines_to_pickup = self.line_ids.filtered('to_pickup')
        if not lines_to_pickup:
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
        # for line in lines_to_pickup:
        #     line.serial_id.write({
        #         'status': 'rented',
        #         'actual_pickup_date': self.pickup_date
        #     })
        #     # Log pickup in status history
        #     self.env['rental.project.item.status'].create({
        #         'project_id': self.project_id.id,
        #         'equipment_id': line.equipment_id.id,
        #         'serial_id': line.serial_id.id,
        #         'status': 'rented',
        #         'signature': self.pickup_signature,
        #         'notes': f'Picked up on {self.pickup_date}. {self.notes or ""}'
        #     })

        # Create signature record
        
        try:
            request = self.env['ir.http'].sudo()._get_request()
            ip_address = request.httprequest.environ.get('REMOTE_ADDR') if request else False
        except:
            ip_address = False

        self.env['rental.project.signature'].create({
            'project_id': self.project_id.id,
            'signature_type': 'pickup',
            'signer_name': 'customer',
            'signer_role': 'customer',
            'signature': self.pickup_signature,
            'notes': self.notes,
            'serial_ids': [(6, 0, lines_to_pickup.mapped('serial_id').ids)],
            'ip_address': ip_address,
        })

        # Process each return
        for line in lines_to_pickup:
            line.action_process_pickup(self.pickup_date)
        
        # Update project state if first pickup
        if self.project_id.state == 'reserved':
            self.project_id.write({'state': 'ongoing'})

        # return {
        #     'type': 'ir.actions.client',
        #     'tag': 'display_notification',
        #     'params': {
        #         'title': _('Pickup Confirmed'),
        #         'message': f'{len(lines_to_pickup)} items picked up.',
        #         'type': 'success',
        #         'sticky': False,
        #     }
        # }


class RentalPickupWizardLine(models.TransientModel):
    _name = 'rental.pickup.wizard.line'
    _description = 'Pickup Wizard Line'

    wizard_id = fields.Many2one(
        'rental.pickup.wizard',
        required=True,
        ondelete='cascade'
    )
    serial_id = fields.Many2one(
        'rental.equipment.serial',
        'Serial Number',
        required=True
    )
    equipment_id = fields.Many2one(
        'rental.equipment',
        'Equipment',
        required=True,  # Add this
        store=True      # Add this
    )
    
    to_pickup = fields.Boolean('Pick Up', default=True)
    serial_number = fields.Char(related='serial_id.serial_number', string='Serial', readonly=True)
    status = fields.Selection(related='serial_id.status', readonly=True)
    programming_config = fields.Text(related='serial_id.programming_config', readonly=True)

    def action_process_pickup(self, pickup_date):
        """Process this pickup line"""
        self.ensure_one()

        # Get equipment_id from serial (safer approach)
        equipment_id = self.serial_id.equipment_id.id
        
        # ✅ ADD DEBUGGING - Print values to server log
        import logging
        _logger = logging.getLogger(__name__)
        
        _logger.info(f"=== PICKUP DEBUG ===")
        _logger.info(f"wizard_id: {self.wizard_id.id}")
        _logger.info(f"project_id: {self.wizard_id.project_id.id}")
        _logger.info(f"serial_id: {self.serial_id.id}")
        _logger.info(f"equipment_id (direct): {equipment_id}")
        _logger.info(f"equipment_id.id: {self.equipment_id.id if self.equipment_id else 'NONE'}")
        _logger.info(f"serial equipment: {self.serial_id.equipment_id.id if self.serial_id and self.serial_id.equipment_id else 'NONE'}")
        
        # Update serial
        self.serial_id.write({
            'status': 'rented',
            'actual_pickup_date': pickup_date
        })
            
        # Prepare status creation values
        status_vals = {
            'project_id': self.wizard_id.project_id.id,
            'equipment_id': equipment_id,
            'serial_id': self.serial_id.id,
            'status': 'rented',
            'signature': self.wizard_id.pickup_signature,
            'notes': f'Picked up on {pickup_date}. Notes: {self.wizard_id.notes or ""}'
        }
        
        _logger.info(f"Status vals: {status_vals}")
        
        # Log status history
        try:
            status_record = self.env['rental.project.item.status'].create(status_vals)
            _logger.info(f"Status record created: {status_record.id}")
        except Exception as e:
            _logger.error(f"ERROR creating status: {str(e)}")
            raise

        # Log status history
        # self.env['rental.project.item.status'].create({
        #     'project_id': self.wizard_id.project_id.id,
        #     'equipment_id': self.equipment_id.id,
        #     'serial_id': self.serial_id.id,
        #     'status': 'rented',
        #     'signature': self.wizard_id.pickup_signature,
        #     'notes': f'Pickup up on {pickup_date}. Notes: {self.wizard_id.notes}'
        # })
