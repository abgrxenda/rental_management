# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class SerialSelectionWizard(models.TransientModel):
    _name = 'serial.selection.wizard'
    _description = 'Serial Number Selection Wizard'
    
    project_item_id = fields.Many2one(
        'rental.project.item',
        string='Project Item',
        required=True,
        readonly=True
    )
    
    equipment_id = fields.Many2one(
        'rental.equipment',
        string='Equipment',
        related='project_item_id.equipment_id',
        readonly=True
    )
    
    quantity_needed = fields.Integer(
        string='Quantity Needed',
        readonly=True
    )
    
    currently_assigned_ids = fields.Many2many(
        'rental.equipment.serial',
        'wizard_current_serial_rel',
        'wizard_id',
        'serial_id',
        string='Currently Assigned',
        help='Serials currently assigned to this item'
    )
    
    available_serial_ids = fields.Many2many(
        'rental.equipment.serial',
        'wizard_available_serial_rel',
        'wizard_id',
        'serial_id',
        string='Available Serials',
        domain="[('equipment_id', '=', equipment_id), '|', ('status', '=', 'available'), ('id', 'in', currently_assigned_ids)]",
        help='Select serial numbers to assign'
    )
    
    selected_count = fields.Integer(
        string='Selected',
        compute='_compute_selected_count'
    )
    
    warning_message = fields.Char(
        string='Warning',
        compute='_compute_warning'
    )
    
    @api.depends('available_serial_ids')
    def _compute_selected_count(self):
        for wizard in self:
            wizard.selected_count = len(wizard.available_serial_ids)
    
    @api.depends('available_serial_ids', 'quantity_needed')
    def _compute_warning(self):
        for wizard in self:
            selected = len(wizard.available_serial_ids)
            needed = wizard.quantity_needed
            
            if selected < needed:
                wizard.warning_message = f'⚠️ You selected {selected} serials but need {needed}. Please select {needed - selected} more.'
            elif selected > needed:
                wizard.warning_message = f'⚠️ You selected {selected} serials but only need {needed}. Please remove {selected - needed} serials.'
            else:
                wizard.warning_message = f'✓ Perfect! You have selected exactly {needed} serial(s).'
    
    @api.model
    def default_get(self, fields_list):
        """Set default available serials from context"""
        res = super().default_get(fields_list)
        
        if self._context.get('available_serial_ids'):
            # Set available serials in the selection
            res['currently_assigned_ids'] = [(6, 0, self._context.get('default_currently_assigned_ids', [[]])[0][2])]
            # Pre-select currently assigned serials
            res['available_serial_ids'] = [(6, 0, self._context.get('default_currently_assigned_ids', [[]])[0][2])]
        
        return res
    
    def action_assign_selected(self):
        """Assign the selected serials to the project item"""
        self.ensure_one()
        
        # Validate selection count matches quantity needed
        if len(self.available_serial_ids) != self.quantity_needed:
            raise ValidationError(_(
                'You must select exactly %d serial(s). You selected %d.'
            ) % (self.quantity_needed, len(self.available_serial_ids)))
        
        # Update project item with selected serials
        self.project_item_id.write({
            'assigned_serial_ids': [(6, 0, self.available_serial_ids.ids)]
        })
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Serials Assigned'),
                'message': _('%d serial number(s) successfully assigned.') % len(self.available_serial_ids),
                'type': 'success',
                'sticky': False,
                'next': {
                    'type': 'ir.actions.act_window_close'
                }
            }
        }
    
    def action_auto_assign(self):
        """Automatically assign available serials"""
        self.ensure_one()
        
        # Get available serials
        available = self.equipment_id.serial_ids.filtered(
            lambda s: s.status == 'available'
        )
        
        if len(available) < self.quantity_needed:
            raise ValidationError(_(
                'Not enough available serials. Need %d, found %d.\n'
                'Please generate more serials first.'
            ) % (self.quantity_needed, len(available)))
        
        # Auto-select first N available
        self.available_serial_ids = [(6, 0, available[:self.quantity_needed].ids)]
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Auto-Assigned'),
                'message': _('%d serials automatically selected.') % self.quantity_needed,
                'type': 'info',
                'sticky': False,
            }
        }