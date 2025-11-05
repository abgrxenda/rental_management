# Key Features:

# Full lifecycle - Draft → Reserved → Ongoing → Returned → Invoiced
# Late fee calculation - Automatic based on overdue days
# Damage assessment - Track damage fees
# Digital signatures - Pickup and return signatures
# Photo documentation - Before/after photos
# Invoice generation - Auto-create from project
# Date validation - End date must be after start date
# Serial reservation - Automatic serial assignment on reserve
# Status history - Track all changes
# Mail integration - Activity tracking and chatter

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import timedelta


class RentalProject(models.Model):
    _name = 'rental.project'
    _description = 'Rental Project/Booking'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'start_date desc, name desc'
    
    name = fields.Char(
        'Project Number',
        required=True,
        copy=False,
        readonly=True,
        default='New',
        tracking=True
    )
    reference = fields.Char(
        'Customer Reference/PO',
        tracking=True,
        help='Customer purchase order or reference number'
    )
    
    # Customer Information
    partner_id = fields.Many2one(
        'res.partner',
        'Customer',
        required=True,
        tracking=True,
        index=True
    )
    partner_email = fields.Char('Email', related='partner_id.email', readonly=True)
    partner_phone = fields.Char('Phone', related='partner_id.phone', readonly=True)
    
    # Rental Dates
    start_date = fields.Date(
        'Start Date',
        required=True,
        tracking=True,
        default=fields.Date.today
    )
    end_date = fields.Date(
        'Expected End Date',
        required=True,
        tracking=True
    )
    actual_return_date = fields.Date('Actual Return Date', tracking=True)
    
    # Duration Calculations
    duration_days = fields.Integer(
        'Duration (Days)',
        compute='_compute_duration',
        store=True,
        help='Number of rental days'
    )
    days_overdue = fields.Integer(
        'Days Overdue',
        compute='_compute_overdue',
        help='Number of days past expected return date'
    )
    is_overdue = fields.Boolean('Is Overdue', compute='_compute_overdue', store=True)
    
    # Special Requirements
    special_programming = fields.Text(
        'Special Programming/Configuration',
        help='Custom configuration requirements for this rental'
    )
    internal_notes = fields.Text('Internal Notes')
    
    # Financial Information
    total_amount = fields.Float(
        'Rental Amount',
        compute='_compute_amounts',
        store=True,
        tracking=True
    )
    late_fee_enabled = fields.Boolean(
        'Apply Late Fees',
        default=lambda self: self.env['ir.config_parameter'].sudo().get_param('rental.default_late_fee_enabled', False),
        tracking=True
    )
    late_fee_amount = fields.Float(
        'Late Fee',
        compute='_compute_late_fee',
        store=True
    )
    damage_fee = fields.Float('Damage/Repair Fee', default=0.0, tracking=True)
        # NEW: Add has_damage field
    has_damage = fields.Boolean(
        'Has Damage',
        default=False,
        tracking=True,
        help='Indicates if equipment was returned with damage'
    )
    
    discount_amount = fields.Float('Discount', default=0.0, tracking=True)
    grand_total = fields.Float(
        'Grand Total',
        compute='_compute_amounts',
        store=True,
        tracking=True
    )
    
    # Payment Status
    payment_status = fields.Selection([
        ('unpaid', 'Unpaid'),
        ('partial', 'Partially Paid'),
        ('paid', 'Paid')
    ], string='Payment Status', default='unpaid', tracking=True)
    
    # Project Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('reserved', 'Reserved'),
        ('ongoing', 'Ongoing'),
        ('returned', 'Returned'),
        ('invoiced', 'Invoiced'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='draft', required=True, tracking=True, index=True)
    
    # Relations
    item_ids = fields.One2many(
        'rental.project.item',
        'project_id',
        'Rental Items',
        copy=True
    )
    item_status_ids = fields.One2many(
        'rental.project.item.status',
        'project_id',
        'Item Status History'
    )
    invoice_id = fields.Many2one('account.move', 'Invoice', copy=False)
    invoice_count = fields.Integer('Invoice Count', compute='_compute_invoice_count')
    
    # Documents and Signatures
    document_ids = fields.Many2many(
        'ir.attachment',
        'rental_project_attachment_rel',
        'project_id',
        'attachment_id',
        string='Documents'
    )
    pickup_signature = fields.Binary('Pickup Signature', attachment=True)
    pickup_signature_date = fields.Datetime('Pickup Date')
    return_signature = fields.Binary('Return Signature', attachment=True)
    return_signature_date = fields.Datetime('Return Date')
    
    # Photos (before/after)
    pickup_photos = fields.Many2many(
        'ir.attachment',
        'rental_project_pickup_photo_rel',
        'project_id',
        'attachment_id',
        string='Pickup Photos'
    )
    return_photos = fields.Many2many(
        'ir.attachment',
        'rental_project_return_photo_rel',
        'project_id',
        'attachment_id',
        string='Return Photos'
    )
    
    sequence = fields.Integer('Sequence', default=10)
    
    # NEW: Add color field for kanban
    color = fields.Integer('Color', default=0)

    # Compute Methods
    
    @api.depends('start_date', 'end_date')
    def _compute_duration(self):
        for project in self:
            if project.start_date and project.end_date:
                delta = project.end_date - project.start_date
                project.duration_days = delta.days + 1  # Include both start and end day
            else:
                project.duration_days = 0
    
    @api.depends('end_date', 'actual_return_date', 'state')
    def _compute_overdue(self):
        today = fields.Date.today()
        for project in self:
            if project.state == 'ongoing' and project.end_date:
                return_date = project.actual_return_date or today
                if return_date > project.end_date:
                    delta = return_date - project.end_date
                    project.days_overdue = delta.days
                    project.is_overdue = True
                else:
                    project.days_overdue = 0
                    project.is_overdue = False
            else:
                project.days_overdue = 0
                project.is_overdue = False
    
    @api.depends('item_ids.subtotal', 'late_fee_amount', 'damage_fee', 'discount_amount')
    def _compute_amounts(self):
        for project in self:
            project.total_amount = sum(project.item_ids.mapped('subtotal'))
            project.grand_total = (
                project.total_amount +
                project.late_fee_amount +
                project.damage_fee -
                project.discount_amount
            )
    
    @api.depends('days_overdue', 'late_fee_enabled', 'total_amount')
    def _compute_late_fee(self):
        IrConfigParam = self.env['ir.config_parameter'].sudo()
        daily_rate = float(IrConfigParam.get_param('rental.late_fee_daily_rate', 0))
        percentage = float(IrConfigParam.get_param('rental.late_fee_percentage', 0))
        
        for project in self:
            if project.late_fee_enabled and project.days_overdue > 0:
                # Option 1: Fixed daily rate
                fee_by_day = daily_rate * project.days_overdue
                
                # Option 2: Percentage of total per day
                fee_by_percentage = (project.total_amount * percentage / 100) * project.days_overdue
                
                # Use whichever is greater
                project.late_fee_amount = max(fee_by_day, fee_by_percentage)
            else:
                project.late_fee_amount = 0.0
    
    def _compute_invoice_count(self):
        for project in self:
            project.invoice_count = 1 if project.invoice_id else 0
    
    # CRUD and Sequencing
    
    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('rental.project') or 'RENT/NEW'
        return super().create(vals)
    
    # Constraints
    
    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        for project in self:
            if project.start_date and project.end_date:
                if project.end_date < project.start_date:
                    raise ValidationError(_('End date cannot be before start date.'))
    
    @api.constrains('item_ids')
    def _check_items(self):
        for project in self:
            if project.state != 'draft' and not project.item_ids:
                raise ValidationError(_('Project must have at least one rental item.'))
    
    # State Transition Methods
    
    def action_reserve(self):
        """Reserve equipment and generate/assign serials"""
        for project in self:
            if not project.item_ids:
                raise UserError(_('Cannot reserve project without items.'))
            
            # Reserve serials for each item
            for item in project.item_ids:
                item.action_reserve_serials()
            
            project.write({
                'state': 'reserved',
                'pickup_signature_date': fields.Datetime.now()
            })
    
    def action_start_rental(self):
        """Start the rental - equipment leaves warehouse"""
        for project in self:
            if project.state != 'reserved':
                raise UserError(_('Project must be reserved before starting rental.'))
            
            # Change serial statuses to 'rented'
            for item in project.item_ids:
                item.action_start_rental()
            
            project.write({'state': 'ongoing'})
    
    def action_return(self):
        """Open return wizard for damage assessment"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Return Equipment'),
            'res_model': 'rental.return.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_project_id': self.id,
                'default_actual_return_date': fields.Date.today()
            }
        }
    
    def action_complete_return(self):
        """Complete return (called from wizard)"""
        self.ensure_one()
        
        # Mark all serials as returned
        for item in self.item_ids:
            item.action_complete_return()
        
        self.write({
            'state': 'returned',
            'actual_return_date': fields.Date.today(),
            'return_signature_date': fields.Datetime.now()
        })
    
    def action_cancel(self):
        """Cancel the project"""
        for project in self:
            if project.state == 'ongoing':
                raise UserError(_('Cannot cancel ongoing rental. Please return equipment first.'))
            
            # Release reserved serials
            for item in project.item_ids:
                item.action_release_serials()
            
            project.write({'state': 'cancelled'})
    
    def action_set_to_draft(self):
        """Reset to draft"""
        for project in self:
            # Release reserved serials if going back to draft from reserved state
            if project.state == 'reserved':
                for item in project.item_ids:
                    # Change serials back to available
                    item.assigned_serial_ids.write({
                        'status': 'available',
                        'current_project_id': False
                    })
            
            project.write({'state': 'draft'})
        
            # return {
            #     'type': 'ir.actions.client',
            #     'tag': 'display_notification',
            #     'params': {
            #         'title': _('Project Set to Draft'),
            #         'message': _('Project has been reset to draft. You can now edit items and serials.'),
            #         'type': 'success',
            #         'sticky': False,
            #     }
            # }
    
    # Invoice Methods
    
    def action_create_invoice(self):
        """Generate invoice from rental project"""
        self.ensure_one()
        
        if self.invoice_id:
            raise UserError(_('Invoice already exists for this project.'))
        
        if not self.item_ids:
            raise UserError(_('Cannot create invoice without rental items.'))
        
        # Prepare invoice lines
        invoice_lines = self._prepare_invoice_lines()
        
        # Create invoice
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner_id.id,
            'invoice_date': fields.Date.today(),
            'invoice_origin': self.name,
            'invoice_line_ids': invoice_lines,
            'narration': self.internal_notes
        })
        
        self.write({
            'invoice_id': invoice.id,
            'state': 'invoiced'
        })
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Invoice'),
            'res_model': 'account.move',
            'res_id': invoice.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
        }
    
    def _prepare_invoice_lines(self):
        """Prepare invoice lines from rental items"""
        lines = []
        
        # Add rental item lines
        for item in self.item_ids:
            lines.append((0, 0, {
                'name': f'{item.equipment_id.name} - Rental ({self.duration_days} days)',
                'quantity': item.quantity,
                'price_unit': item.unit_price,
            }))
        
        # Add late fee if applicable
        if self.late_fee_amount > 0:
            lines.append((0, 0, {
                'name': f'Late Fee ({self.days_overdue} days overdue)',
                'quantity': 1,
                'price_unit': self.late_fee_amount,
            }))
        
        # Add damage fee if applicable
        if self.damage_fee > 0:
            lines.append((0, 0, {
                'name': 'Damage/Repair Fee',
                'quantity': 1,
                'price_unit': self.damage_fee,
            }))
        
        # Add discount if applicable
        if self.discount_amount > 0:
            lines.append((0, 0, {
                'name': 'Discount',
                'quantity': 1,
                'price_unit': -self.discount_amount,
            }))
        
        return lines
    
    def action_view_invoice(self):
        """Open the related invoice"""
        self.ensure_one()
        if not self.invoice_id:
            raise UserError(_('No invoice found for this project.'))
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Invoice'),
            'res_model': 'account.move',
            'res_id': self.invoice_id.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
        }