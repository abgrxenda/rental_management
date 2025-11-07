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
    return_signature = fields.Binary('Customer Signature')
    notes = fields.Text('Return Notes')
    
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
        
        # Process each return
        for line in lines_to_return:
            line.action_process_return(self.return_date)
        
        # Check if all items returned
        remaining_rented = self.env['rental.equipment.serial'].search_count([
            ('current_project_id', '=', self.project_id.id),
            ('status', '=', 'rented')
        ])
        
        if remaining_rented == 0:
            # All returned - mark project as returned
            self.project_id.write({
                'state': 'returned',
                'actual_return_date': self.return_date
            })
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Return Confirmed'),
                'message': _('%d serial(s) returned. Total charge: $%.2f') % (
                    len(lines_to_return), 
                    self.total_charge
                ),
                'type': 'success',
                'sticky': False,
            }
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
    
    def action_process_return(self, return_date):
        """Process this return line"""
        self.ensure_one()
        
        # Determine new status
        if self.condition == 'good':
            new_status = 'available'
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
            'current_project_id': False if new_status in ['available', 'disposed'] else self.serial_id.current_project_id.id
        })
        
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