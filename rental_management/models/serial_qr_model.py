from odoo import models, fields, api
import base64
import logging

_logger = logging.getLogger(__name__)


class RentalSerialNumber(models.Model):
    _inherit = 'rental.serial.number'
    
    qr_code = fields.Binary(
        string='QR Code',
        attachment=True,
        readonly=True,
        help='Automatically generated QR code for this serial number'
    )
    
    qr_code_filename = fields.Char(
        string='QR Code Filename',
        compute='_compute_qr_code_filename',
        store=True
    )
    
    @api.depends('name')
    def _compute_qr_code_filename(self):
        """Generate filename for QR code"""
        for record in self:
            if record.name:
                # Sanitize filename
                safe_name = record.name.replace('/', '-').replace(' ', '_')
                record.qr_code_filename = f"QR_{safe_name}.png"
            else:
                record.qr_code_filename = "QR_code.png"
    
    @api.model_create_multi
    def create(self, vals_list):
        """Override create to generate QR code automatically"""
        records = super(RentalSerialNumber, self).create(vals_list)
        
        for record in records:
            record._generate_qr_code()
        
        return records
    
    def write(self, vals):
        """Regenerate QR code if serial number changes"""
        result = super(RentalSerialNumber, self).write(vals)
        
        # Regenerate QR if name changes
        if 'name' in vals:
            for record in self:
                record._generate_qr_code()
        
        return result
    
    def _generate_qr_code(self):
        """Generate QR code for this serial number"""
        self.ensure_one()
        
        if not self.name:
            return
        
        try:
            # Import the QR generator
            from .qr_generator import generate_qr_code
            
            # Get company logo if enabled
            logo_binary = None
            if self.company_id.use_qr_logo and self.company_id.qr_logo:
                logo_binary = base64.b64decode(self.company_id.qr_logo)
            
            # Generate QR code with serial number as data
            qr_base64 = generate_qr_code(self.name, logo_binary)
            
            # Save to record
            self.qr_code = qr_base64
            
            _logger.info(f"QR code generated for serial number: {self.name}")
            
        except Exception as e:
            _logger.error(f"Failed to generate QR code for {self.name}: {str(e)}")
    
    def action_regenerate_qr_code(self):
        """Manual action to regenerate QR code"""
        for record in self:
            record._generate_qr_code()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Success',
                'message': 'QR code(s) regenerated successfully',
                'type': 'success',
                'sticky': False,
            }
        }
    
    def action_download_qr_code(self):
        """Download QR code as PNG file"""
        self.ensure_one()
        
        if not self.qr_code:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Warning',
                    'message': 'No QR code available. Please generate one first.',
                    'type': 'warning',
                }
            }
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/rental.serial.number/{self.id}/qr_code/{self.qr_code_filename}?download=true',
            'target': 'self',
        }
    
    def action_print_qr_code(self):
        """Print QR code label"""
        self.ensure_one()
        
        return self.env.ref('rental_management.action_report_qr_code_label').report_action(self)
