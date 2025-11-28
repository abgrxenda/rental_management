# Key Features:

# Late Fee Configuration - Daily rate, percentage, or both
# Auto-generation Settings - Serial number generation preferences
# Default Values - Default rental duration, etc.
# Signature & Photo Requirements - Enforce documentation
# Email Notifications - Reminders and overdue alerts
# Invoice Automation - Auto-create on return
# Stock Warnings - Low stock threshold alerts
# Damage Classification - Automatic severity classification by cost
# Flexible Calculation - Choose how late fees are calculated

from odoo import models, fields, api


# Extend res.company model
class ResCompany(models.Model):
    _inherit = 'res.company'
    
    qr_logo = fields.Binary(
        string='QR Code Logo',
        help='Logo to be displayed in the center of QR codes for rental items. '
             'Recommended size: 200x200px with transparent background.',
        attachment=True
    )
    
    qr_logo_filename = fields.Char(string='QR Logo Filename')
    
    use_qr_logo = fields.Boolean(
        string='Use Logo in QR Codes',
        default=True,
        help='If enabled, the QR logo will be embedded in all generated QR codes'
    )

# Extend res.config.settings model
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
    # Late Fee Settings
    rental_default_late_fee_enabled = fields.Boolean(
        'Enable Late Fees by Default',
        config_parameter='rental.default_late_fee_enabled',
        help='Automatically enable late fees for new rental projects'
    )
    rental_late_fee_daily_rate = fields.Float(
        'Late Fee - Daily Rate',
        config_parameter='rental.late_fee_daily_rate',
        help='Fixed amount charged per day overdue (e.g., $50/day)'
    )
    rental_late_fee_percentage = fields.Float(
        'Late Fee - Daily Percentage',
        config_parameter='rental.late_fee_percentage',
        help='Percentage of rental amount charged per day overdue (e.g., 5% per day)'
    )
    rental_late_fee_calculation_method = fields.Selection([
        ('daily', 'Use Daily Rate Only'),
        ('percentage', 'Use Percentage Only'),
        ('maximum', 'Use Maximum of Both')
    ], string='Late Fee Calculation Method',
       config_parameter='rental.late_fee_calculation_method',
       default='maximum',
       help='How to calculate late fees when both daily rate and percentage are set')
    
    # Auto-generation Settings
    rental_auto_generate_serials = fields.Boolean(
        'Auto-Generate Serial Numbers',
        config_parameter='rental.auto_generate_serials',
        help='Automatically generate serial numbers for equipment without serials'
    )
    rental_serial_prefix = fields.Char(
        'Serial Number Prefix',
        config_parameter='rental.serial_prefix',
        default='SN',
        help='Prefix for auto-generated serial numbers (e.g., SN-EQUIP-0001)'
    )
    
    # Project Settings
    rental_default_rental_duration = fields.Integer(
        'Default Rental Duration (Days)',
        config_parameter='rental.default_rental_duration',
        default=7,
        help='Default number of days for new rental projects'
    )
    rental_require_signature = fields.Boolean(
        'Require Digital Signature',
        config_parameter='rental.require_signature',
        default=True,
        help='Require digital signature for pickup and return'
    )
    rental_require_photos = fields.Boolean(
        'Require Photos',
        config_parameter='rental.require_photos',
        help='Require photos during pickup and return'
    )
    
    # Notification Settings
    rental_send_reminder_email = fields.Boolean(
        'Send Reminder Emails',
        config_parameter='rental.send_reminder_email',
        default=True,
        help='Send email reminders before rental end date'
    )
    rental_reminder_days_before = fields.Integer(
        'Reminder Days Before',
        config_parameter='rental.reminder_days_before',
        default=2,
        help='Send reminder this many days before rental end date'
    )
    rental_send_overdue_email = fields.Boolean(
        'Send Overdue Notifications',
        config_parameter='rental.send_overdue_email',
        default=True,
        help='Send email notifications for overdue rentals'
    )
    
    # Invoice Settings
    rental_auto_create_invoice = fields.Boolean(
        'Auto-Create Invoice on Return',
        config_parameter='rental.auto_create_invoice',
        help='Automatically create invoice when equipment is returned'
    )
    rental_invoice_include_late_fees = fields.Boolean(
        'Include Late Fees in Invoice',
        config_parameter='rental.invoice_include_late_fees',
        default=True,
        help='Automatically add late fees to invoice'
    )
    
    # Stock/Availability Settings
    rental_warn_low_stock = fields.Boolean(
        'Warn on Low Stock',
        config_parameter='rental.warn_low_stock',
        default=True,
        help='Show warning when equipment stock is low'
    )
    rental_low_stock_threshold = fields.Integer(
        'Low Stock Threshold',
        config_parameter='rental.low_stock_threshold',
        default=3,
        help='Minimum available units before showing low stock warning'
    )
    
    # Damage Assessment Settings
    rental_damage_minor_threshold = fields.Float(
        'Minor Damage - Max Cost',
        config_parameter='rental.damage_minor_threshold',
        default=100.0,
        help='Maximum repair cost to classify as minor damage'
    )
    rental_damage_moderate_threshold = fields.Float(
        'Moderate Damage - Max Cost',
        config_parameter='rental.damage_moderate_threshold',
        default=500.0,
        help='Maximum repair cost to classify as moderate damage (above this is severe)'
    )
    
    @api.onchange('rental_late_fee_daily_rate', 'rental_late_fee_percentage')
    def _onchange_late_fee_values(self):
        """Suggest calculation method based on what's filled"""
        if self.rental_late_fee_daily_rate and not self.rental_late_fee_percentage:
            self.rental_late_fee_calculation_method = 'daily'
        elif self.rental_late_fee_percentage and not self.rental_late_fee_daily_rate:
            self.rental_late_fee_calculation_method = 'percentage'
        elif self.rental_late_fee_daily_rate and self.rental_late_fee_percentage:
            self.rental_late_fee_calculation_method = 'maximum'