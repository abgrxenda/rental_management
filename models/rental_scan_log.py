# -*- coding: utf-8 -*-

from odoo import models, fields, api


class RentalScanLog(models.Model):
    _name = 'rental.scan.log'
    _description = 'Rental Equipment Scan Log'
    _order = 'scan_datetime desc'
    _rec_name = 'serial_number_id'
    
    serial_number_id = fields.Many2one(
        'rental.equipment.serial',
        string='Serial Number',
        required=True,
        ondelete='cascade',
        index=True
    )
    
    equipment_id = fields.Many2one(
        'rental.equipment',
        string='Equipment',
        related='serial_number_id.equipment_id',
        store=True,
        readonly=True
    )
    
    scan_datetime = fields.Datetime(
        string='Scan Date & Time',
        required=True,
        default=fields.Datetime.now,
        index=True
    )
    
    scan_type = fields.Selection([
        ('add_to_project', 'Add to Project'),
        ('handover', 'Handover to Customer'),
        ('return', 'Return from Customer'),
        ('damaged', 'Report Damaged'),
        ('repair', 'Send to Repair'),
        ('verify', 'Verify Item'),
        ('other', 'Other')
    ], string='Scan Type', required=True, index=True)
    
    user_id = fields.Many2one(
        'res.users',
        string='Scanned By',
        required=True,
        default=lambda self: self.env.user,
        ondelete='restrict'
    )
    
    project_id = fields.Many2one(
        'rental.project',
        string='Related Project',
        ondelete='set null'
    )
    
    notes = fields.Text(string='Notes')
    
    location = fields.Char(string='Scan Location')
    
    previous_status = fields.Char(string='Previous Status')
    
    new_status = fields.Char(string='New Status')
    
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company
    )
    
    @api.model
    def log_scan(self, serial_number_id, scan_type, project_id=None, 
                 notes=None, location=None, previous_status=None, new_status=None):
        """
        Helper method to log a scan event
        
        Args:
            serial_number_id (int): ID of the serial number
            scan_type (str): Type of scan action
            project_id (int): Optional project ID
            notes (str): Optional notes
            location (str): Optional location info
            previous_status (str): Previous status before scan
            new_status (str): New status after scan
            
        Returns:
            rental.scan.log: Created log record
        """
        values = {
            'serial_number_id': serial_number_id,
            'scan_type': scan_type,
            'project_id': project_id,
            'notes': notes,
            'location': location,
            'previous_status': previous_status,
            'new_status': new_status,
        }
        
        return self.create(values)
    
    def name_get(self):
        """Custom display name"""
        result = []
        for record in self:
            scan_type_label = dict(self._fields['scan_type'].selection).get(record.scan_type, record.scan_type)
            name = f"{record.serial_number_id.name} - {scan_type_label}"
            result.append((record.id, name))
        return result