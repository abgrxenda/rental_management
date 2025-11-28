# -*- coding: utf-8 -*-

from odoo import models, fields


class ResCompany(models.Model):
    _inherit = 'res.company'
    
    qr_logo = fields.Binary(
        string='QR Code Logo',
        help='Logo to be displayed in the center of QR codes. Recommended: 200x200px PNG',
        attachment=True
    )
    
    qr_logo_filename = fields.Char(string='QR Logo Filename')
    
    use_qr_logo = fields.Boolean(
        string='Use Logo in QR Codes',
        default=False,
        help='If enabled, the logo will be embedded in generated QR codes'
    )


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'
    
    qr_logo = fields.Binary(
        related='company_id.qr_logo',
        readonly=False,
        string='QR Code Logo'
    )
    
    qr_logo_filename = fields.Char(
        related='company_id.qr_logo_filename',
        readonly=False
    )
    
    use_qr_logo = fields.Boolean(
        related='company_id.use_qr_logo',
        readonly=False,
        string='Use Logo in QR Codes'
    )