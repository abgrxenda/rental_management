# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class AddSignatureWizard(models.TransientModel):
    _name = 'add.signature.wizard'
    _description = 'Add Signature Wizard'
    
    project_id = fields.Many2one(
        'rental.project',
        string='Project',
        required=True,
        readonly=True
    )
    
    signature_type = fields.Selection([
        ('pickup', 'Pickup Signature'),
        ('return', 'Return Signature'),
        ('partial_pickup', 'Partial Pickup'),
        ('partial_return', 'Partial Return'),
        ('damage_acknowledgment', 'Damage Acknowledgment'),
        ('other', 'Other')
    ], string='Signature Type', required=True, default='pickup')
    
    signer_name = fields.Char(
        string='Signer Name',
        required=True,
        help='Full name of the person signing'
    )
    
    signer_role = fields.Selection([
        ('customer', 'Customer'),
        ('staff', 'Staff Member'),
        ('manager', 'Manager'),
        ('witness', 'Witness')
    ], string='Signer Role', default='customer', required=True)
    
    signature = fields.Image(  # Changed from Binary to Image
        string='Signature',
        required=True,
        max_width=1024,
        max_height=1024,
        help='Draw signature using mouse or stylus'
    )
    
    notes = fields.Text(
        string='Notes',
        help='Additional notes about this signature'
    )
    
    serial_ids = fields.Many2many(
        'rental.equipment.serial',
        string='Related Serials',
        help='Select serials if this signature is for partial pickup/return'
    )
    
    @api.constrains('signature')
    def _check_signature(self):
        """Ensure signature is not empty"""
        for wizard in self:
            if not wizard.signature:
                raise ValidationError(_('Please provide a signature before saving.'))
    
    def action_save_signature(self):
        """Save the signature to the project"""
        self.ensure_one()
        
        # Get client IP address (Odoo 18 compatible way)
        try:
            request = self.env['ir.http'].sudo()._get_request()
            ip_address = request.httprequest.environ.get('REMOTE_ADDR') if request else False
        except:
            ip_address = False
        
        # Create signature record
        self.env['rental.project.signature'].create({
            'project_id': self.project_id.id,
            'signature_type': self.signature_type,
            'signer_name': self.signer_name,
            'signer_role': self.signer_role,
            'signature': self.signature,
            'notes': self.notes,
            'serial_ids': [(6, 0, self.serial_ids.ids)] if self.serial_ids else False,
            'ip_address': ip_address,
        })
        
        # return {
        #     'type': 'ir.actions.client',
        #     'tag': 'display_notification',
        #     'params': {
        #         'title': _('Signature Saved'),
        #         'message': _('Signature from %s has been recorded successfully.') % self.signer_name,
        #         'type': 'success',
        #         'sticky': False,
        #     }
        # }