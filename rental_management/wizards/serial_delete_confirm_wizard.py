# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class SerialDeleteConfirmWizard(models.TransientModel):
    _name = 'serial.delete.confirm.wizard'
    _description = 'Serial Number Delete Confirmation'
    
    serial_id = fields.Many2one(
        'rental.equipment.serial',
        string='Serial Number',
        required=True,
        readonly=True
    )
    
    serial_number = fields.Char(
        related='serial_id.serial_number',
        string='Serial',
        readonly=True
    )
    
    equipment_name = fields.Char(
        related='serial_id.equipment_name',
        string='Equipment',
        readonly=True
    )
    
    confirm_text = fields.Char(
        string='Type "DELETE" to confirm',
        help='Type DELETE (in capital letters) to confirm deletion'
    )
    
    def action_confirm_delete(self):
        """Confirm and delete the serial"""
        self.ensure_one()
        
        if self.confirm_text != 'DELETE':
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Confirmation Required'),
                    'message': _('Please type "DELETE" exactly to confirm.'),
                    'type': 'warning',
                    'sticky': False,
                }
            }
        
        serial_number = self.serial_id.serial_number
        
        # Delete the serial
        self.serial_id.unlink()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Serial Deleted'),
                'message': _('Serial number "%s" has been permanently deleted.') % serial_number,
                'type': 'success',
                'sticky': False,
                'next': {
                    'type': 'ir.actions.act_window_close'
                }
            }
        }