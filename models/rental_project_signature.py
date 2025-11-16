# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError

class RentalProjectSignature(models.Model):
    _name = 'rental.project.signature'
    _description = 'Project Signature'
    _order = 'sign_datetime desc, id desc'
    _rec_name = 'signer_name'
    
    project_id = fields.Many2one(
        'rental.project',
        string='Project',
        required=True,
        ondelete='cascade',
        index=True
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
        help='Name of the person signing'
    )
    
    signer_role = fields.Selection([
        ('customer', 'Customer'),
        ('staff', 'Staff Member'),
        ('manager', 'Manager'),
        ('witness', 'Witness')
    ], string='Signer Role', default='customer')

    signature = fields.Image(  # Changed from Binary to Image
        string='Signature',
        required=True,
        max_width=1024,
        max_height=1024,
        help='Digital signature captured on screen'
    )

    sign_datetime = fields.Datetime(
        string='Signed Date & Time',
        required=True,
        default=fields.Datetime.now,
        readonly=True
    )
    
    user_id = fields.Many2one(
        'res.users',
        string='Recorded By',
        default=lambda self: self.env.user,
        readonly=True
    )
    
    notes = fields.Text(
        string='Notes',
        help='Additional notes about this signature'
    )
    
    # Related info for quick filtering
    serial_ids = fields.Many2many(
        'rental.equipment.serial',
        'signature_serial_rel',
        'signature_id',
        'serial_id',
        string='Related Serials',
        help='Serial numbers related to this signature (for partial pickups/returns)'
    )
    
    ip_address = fields.Char(
        string='IP Address',
        readonly=True,
        help='IP address where signature was captured'
    )
    
    def name_get(self):
        """Custom display name"""
        result = []
        for record in self:
            type_label = dict(self._fields['signature_type'].selection).get(record.signature_type)
            name = f"{record.signer_name} - {type_label}"
            result.append((record.id, name))
        return result
    
    def action_view_signature_detail(self):
        """Open detailed view of this signature"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Signature Details'),
            'res_model': 'rental.project.signature',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }