# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class RentalPartialReturnWizard(models.TransientModel):
    _name = 'rental.partial.return.wizard'
    _description = 'Partial Equipment Return Wizard'
    
    project_id = fields.Many2one(
        'rental.project',
        'Project',
        required=True,
        readonly=True
    )
    return_date = fields.Date(
        'Return Date',
        required=True,
        default=fields.Date.today
    )
    line_ids = fields.One2many(
        'rental.partial.return.wizard.line',
        'wizard_id',
        'Items to Return'
    )
    total_charge = fields.Float(
        'Total Charge for This Return',
        compute='_compute_total_charge'
    )
    # Return signature and photos
    return_signature = fields.Binary('Customer Signature')
    return_photos = fields.Many2many(
        'ir.attachment',
        'return_wizard_photo_rel',
        'wizard_id',
        'attachment_id',
        string='Return Photos'
    )

    notes = fields.Text('Return Notes')
    # Overall assessment
    has_damage = fields.Boolean('Has Damage')
    total_damage_fee = fields.Float(
        'Total Damage Fee',
        compute='_compute_total_damage_fee'
    )

    @api.depends('line_ids.damage_fee')
    def _compute_total_damage_fee(self):
        for wizard in self:
            wizard.total_damage_fee = sum(wizard.line_ids.mapped('damage_fee'))

    @api.depends('line_ids.rental_charge')
    def _compute_total_charge(self):
        for wizard in self:
            wizard.total_charge = sum(wizard.line_ids.mapped('rental_charge'))
    
    @api.model
    def default_get(self, fields_list):
        """Pre-populate with rented serials"""
        res = super().default_get(fields_list)
        
        project_id = self.env.context.get('default_project_id')
        if project_id:
            project = self.env['rental.project'].browse(project_id)
            
            # Get all rented serials for this project
            rented_serials = self.env['rental.equipment.serial'].search([
                ('current_project_id', '=', project.id),
                ('status', '=', 'rented')
            ])
            
            lines = []
            for serial in rented_serials:
                lines.append((0, 0, {
                    'serial_id': serial.id,
                    'equipment_id': serial.equipment_id.id,
                    'condition': 'good',
                    'to_return': True,  # Select all by default
                }))
            
            res['line_ids'] = lines
        
        return res
    
    def action_confirm_return(self):
        """Process partial return"""
        self.ensure_one()
        
        lines_to_return = self.line_ids.filtered('to_return')
        
        if not lines_to_return:
            raise UserError(_('Please select at least one serial to return.'))
        
        # Validate return date
        if self.return_date > self.project_id.end_date:
            raise ValidationError(_(
                'Return date cannot be after project end date (%s).'
            ) % self.project_id.end_date)
        
                # Check if any items have damage
        has_any_damage = any(line.condition != 'good' for line in self.line_ids)
        
        # Update project with return information
        self.project_id.write({
            'damage_fee': self.total_damage_fee,
            'has_damage': has_any_damage,  # NEW: Set has_damage flag
            'return_signature': self.return_signature,
            'return_photos': [(6, 0, self.return_photos.ids)]
        })
        
        # Process each return
        for line in lines_to_return:
            line.action_process_return(self.return_date)
        
        # Check if all items returned
        remaining_rented = self.env['rental.equipment.serial'].search_count([
            ('current_project_id', '=', self.project_id.id),
            ('status', '=', 'rented')
        ])
        remaining_reserved = self.env['rental.equipment.serial'].search_count([
            ('current_project_id', '=', self.project_id.id),
            ('status', '=', 'reserved')
        ])
        
        if remaining_rented == 0 and remaining_reserved == 0:
            # All returned - mark project as returned
            self.project_id.write({
                'state': 'returned',
                'actual_return_date': self.return_date
            })
        # IMPORTANT: Return action to reload the form with updated values
        return {
            'type': 'ir.actions.act_window',
            'name': _('Return Confirmed'),
            'res_model': 'rental.partial.return.wizard',
            'res_id': self.id,  # Keep the same wizard record
            'view_mode': 'form',
            'target': 'new',
            'context': self.env.context,
        }



class RentalPartialReturnWizardLine(models.TransientModel):
    _name = 'rental.partial.return.wizard.line'
    _description = 'Partial Return Line'
    
    wizard_id = fields.Many2one(
        'rental.partial.return.wizard',
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
        required=True
    )
    to_return = fields.Boolean('Return This Item', default=True)
    
    # Return assessment
    condition = fields.Selection([
        ('good', 'Good Condition'),
        ('minor_damage', 'Minor Damage'),
        ('damaged', 'Damaged'),
        ('lost', 'Lost')
    ], string='Condition', default='good', required=True)
    
    damage_description = fields.Text('Damage Description')
    damage_fee = fields.Float('Damage Fee')
    
    # Auto-calculated rental info
    pickup_date = fields.Date(
        'Pickup Date',
        related='serial_id.actual_pickup_date',
        readonly=True
    )
    rental_days = fields.Integer(
        'Days Rented',
        compute='_compute_rental_info'
    )
    daily_rate = fields.Float(
        'Daily Rate',
        related='equipment_id.daily_rate',
        readonly=True
    )
    rental_charge = fields.Float(
        'Rental Charge',
        compute='_compute_rental_info'
    )
    
    @api.depends('pickup_date', 'wizard_id.return_date', 'daily_rate', 'to_return')
    def _compute_rental_info(self):
        for line in self:
            if line.to_return and line.pickup_date and line.wizard_id.return_date:
                delta = line.wizard_id.return_date - line.pickup_date
                line.rental_days = delta.days + 1
                line.rental_charge = line.rental_days * line.daily_rate
            else:
                line.rental_days = 0
                line.rental_charge = 0.0
    
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
    
    def action_process_return(self, return_date):
        """Process this return line"""
        self.ensure_one()
        
        # Determine new status
        if self.condition == 'good':
            new_status = 'returned'
        elif self.condition == 'minor_damage':
            new_status = 'damaged'
        elif self.condition == 'damaged':
            new_status = 'repairing'
        else:  # lost
            new_status = 'disposed'
        
        # Update serial
        self.serial_id.write({
            'status': new_status,
            'actual_return_date': return_date,
            'current_project_id': False if new_status in ['returned', 'disposed'] else self.serial_id.current_project_id.id
        })
        
        # Update wizard's has_damage flag
        if self.condition != 'good':
            self.wizard_id.has_damage = True

        # Log status history
        self.env['rental.project.item.status'].create({
            'project_id': self.wizard_id.project_id.id,
            'equipment_id': self.equipment_id.id,
            'serial_id': self.serial_id.id,
            'status': new_status,
            'notes': f'Returned on {return_date}. Condition: {self.condition}. Days rented: {self.rental_days}. Charge: ${self.rental_charge}',
            'damage_description': self.damage_description,
            'damage_severity': 'minor' if self.condition == 'minor_damage' else 'severe' if self.condition in ['damaged', 'lost'] else None,
            'repair_cost_estimate': self.damage_fee
        })