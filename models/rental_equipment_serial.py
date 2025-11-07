# Key Features:

# Unique serial numbers - SQL constraint enforces uniqueness
# Auto-generation - Can auto-generate serials based on equipment code
# Status workflow - 7 statuses (Available → Reserved → Rented → Returned → etc.)
# Status history - Automatic logging when status changes
# Current project tracking - Know which project has this serial
# Action buttons - Quick status changes (Set Available, Set Damaged, etc.)
# Validation - Status must match project assignment
# Smart name_get - Shows equipment name and status in selections

# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

import base64
import logging
_logger = logging.getLogger(__name__)

class RentalEquipmentSerial(models.Model):
    _name = 'rental.equipment.serial'
    _description = 'Equipment Serial Number'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'serial_number'
    _order = 'sequence, serial_number'
        # NEW: Per-serial rental tracking
    actual_pickup_date = fields.Date(
        'Actual Pickup Date',
        help='When customer actually picked up this serial'
    )
    actual_return_date = fields.Date(
        'Actual Return Date',
        help='When customer actually returned this serial'
    )
    rental_days = fields.Integer(
        'Rental Days',
        compute='_compute_rental_days',
        store=True,
        help='Actual number of days this serial was rented'
    )
    rental_charge = fields.Float(
        'Rental Charge',
        compute='_compute_rental_charge',
        store=True,
        help='Total charge for this serial rental'
    )
    
    equipment_id = fields.Many2one(
        'rental.equipment',
        'Equipment',
        required=True,
        ondelete='cascade',
        index=True
    )
    equipment_name = fields.Char(
        'Equipment Name',
        related='equipment_id.name',
        store=True,
        readonly=True
    )
    
    serial_number = fields.Char(
        'Serial Number',
        required=True,
        copy=False,
        index=True
    )
    programming_config = fields.Text(
        'Special Programming/Configuration',
        help='Custom settings or programming for this specific unit'
    )
    
    # Status Tracking
    status = fields.Selection([
        ('available', 'Available'),
        ('reserved', 'Reserved'),
        ('rented', 'Rented'),
        ('returned', 'Returned'),
        ('damaged', 'Damaged'),
        ('repairing', 'Under Repair'),
        ('disposed', 'Disposed')
    ], string='Status', default='available', required=True, tracking=True, index=True)
    
    # Current rental information
    current_project_id = fields.Many2one(
        'rental.project',
        'Current Project',
        help='Project this serial is currently assigned to'
    )
    current_project_name = fields.Char(
        'Current Project',
        related='current_project_id.name',
        readonly=True
    )
    
    # Status history
    status_history_ids = fields.One2many(
        'rental.project.item.status',
        'serial_id',
        'Status History'
    )
    
    # Notes and images
    notes = fields.Text('Notes')
    # image = fields.Binary('Photo', attachment=True)
    # image_filename = fields.Char('Image Filename')
    
    sequence = fields.Integer('Sequence', default=10)
    active = fields.Boolean('Active', default=True)
    
    # SQL constraint for unique serial numbers
    _sql_constraints = [
        ('serial_unique', 'unique(serial_number)', 'Serial number must be unique!')
    ]
    
    qr_code = fields.Binary(
        string='QR Code',
        attachment=True,
        readonly=True,
        help='Automatically generated QR code for this serial number'
    )
    
    qr_code_filename = fields.Char(
        string='QR Code Filename',
        compute='_compute_qr_code_filename',
        store=True
    )

    @api.model
    def create(self, vals):
        """Auto-generate serial number if not provided and equipment has auto-generation enabled"""
        if not vals.get('serial_number'):
            equipment = self.env['rental.equipment'].browse(vals.get('equipment_id'))
            if equipment.auto_generate_serials:
                # Generate serial: EQUIPMENT_CODE-XXXX
                code = equipment.code or 'EQ'
                sequence = len(equipment.serial_ids) + 1
                vals['serial_number'] = f"{code}-{sequence:04d}"
        
        return super().create(vals)
    
    def write(self, vals):
        """Track status changes"""
        result = super().write(vals)
        
        # If status changed, log it in history
        if 'status' in vals:
            for serial in self:
                if serial.current_project_id:
                    # Create status history entry
                    self.env['rental.project.item.status'].create({
                        'project_id': serial.current_project_id.id,
                        'equipment_id': serial.equipment_id.id,
                        'serial_id': serial.id,
                        'status': vals['status'],
                        'notes': f"Status changed to {dict(self._fields['status'].selection).get(vals['status'])}"
                    })
        
        return result

    # NEW METHODS - Add these right after write()
    def unlink(self):
        """
        Prevent deletion of serials that have been used in projects.
        Override default delete behavior.
        """
        for serial in self:
            # Check if serial has any history (has been used in projects)
            if serial.status_history_ids:
                raise UserError(_(
                    'Cannot delete serial number "%s" because it has been used in projects.\n\n'
                    'History found: %d record(s)\n\n'
                    'You can deactivate it instead by clicking "Archive" or using the "Smart Delete" action.'
                ) % (serial.serial_number, len(serial.status_history_ids)))
            
            # Check if currently assigned to a project
            if serial.current_project_id:
                raise UserError(_(
                    'Cannot delete serial number "%s" because it is currently assigned to project "%s".\n\n'
                    'Please remove it from the project first or deactivate it instead.'
                ) % (serial.serial_number, serial.current_project_id.name))
            
            # Check if serial is not available (rented, damaged, etc.)
            if serial.status != 'available':
                raise UserError(_(
                    'Cannot delete serial number "%s" because its status is "%s".\n\n'
                    'Only available serials can be deleted. Please set it to available first or deactivate it.'
                ) % (serial.serial_number, dict(self._fields['status'].selection).get(serial.status)))
        
        return super().unlink()
    
    def action_smart_delete(self):
        """
        Smart delete: If serial has history, deactivate it. Otherwise, delete it.
        This is the recommended way to remove serials.
        """
        self.ensure_one()
        
        # Check if serial has been used
        has_history = bool(serial.status_history_ids)
        is_in_project = bool(serial.current_project_id)
        is_not_available = serial.status != 'available'
        
        if has_history or is_in_project or is_not_available:
            # Deactivate instead of delete
            self.write({
                'active': False,
                'status': 'disposed'
            })
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Serial Archived'),
                    'message': _(
                        'Serial "%s" has been archived (deactivated) because it has usage history.\n'
                        'It can no longer be used but its history is preserved.'
                    ) % self.serial_number,
                    'type': 'success',
                    'sticky': False,
                }
            }
        else:
            # Safe to delete - show confirmation
            return {
                'type': 'ir.actions.act_window',
                'name': _('Confirm Deletion'),
                'res_model': 'serial.delete.confirm.wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_serial_id': self.id,
                }
            }
        
    def action_set_available(self):
        """Mark serial as available"""
        self.write({
            'status': 'available',
            'current_project_id': False
        })
    
    def action_set_damaged(self):
        """Mark serial as damaged"""
        self.write({'status': 'damaged'})
    
    def action_set_repairing(self):
        """Mark serial as under repair"""
        self.write({'status': 'repairing'})
    
    def action_set_disposed(self):
        """Mark serial as disposed"""
        self.write({
            'status': 'disposed',
            'active': False
        })
    
    def action_view_status_history(self):
        """View status history for this serial"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Status History'),
            'res_model': 'rental.project.item.status',
            'view_mode': 'list,form',
            'domain': [('serial_id', '=', self.id)],
            'context': {'default_serial_id': self.id}
        }
    
    @api.constrains('status', 'current_project_id')
    def _check_status_consistency(self):
        """Ensure status is consistent with project assignment"""
        for serial in self:
            if serial.status in ['reserved', 'rented'] and not serial.current_project_id:
                raise ValidationError(_(
                    'Serial %s is marked as %s but not assigned to any project.'
                ) % (serial.serial_number, serial.status))
            
            if serial.status == 'available' and serial.current_project_id:
                raise ValidationError(_(
                    'Serial %s is marked as available but is still assigned to project %s.'
                ) % (serial.serial_number, serial.current_project_id.name))
    
    def name_get(self):
        """Display serial with equipment name"""
        result = []
        for serial in self:
            name = f"[{serial.equipment_name}] {serial.serial_number}"
            if serial.status != 'available':
                status_label = dict(self._fields['status'].selection).get(serial.status)
                name += f" ({status_label})"
            result.append((serial.id, name))
        return result

    @api.depends('actual_pickup_date', 'actual_return_date')
    def _compute_rental_days(self):
        for serial in self:
            if serial.actual_pickup_date and serial.actual_return_date:
                delta = serial.actual_return_date - serial.actual_pickup_date
                serial.rental_days = delta.days + 1  # Include both days
            elif serial.actual_pickup_date:
                # Still out - calculate to today
                delta = fields.Date.today() - serial.actual_pickup_date
                serial.rental_days = delta.days + 1
            else:
                serial.rental_days = 0
    
    @api.depends('rental_days', 'equipment_id.daily_rate')
    def _compute_rental_charge(self):
        for serial in self:
            if serial.rental_days > 0 and serial.equipment_id:
                serial.rental_charge = serial.rental_days * serial.equipment_id.daily_rate
            else:
                serial.rental_charge = 0.0
# ========== QR CODE METHODS ==========
    
    @api.depends('serial_number')
    def _compute_qr_code_filename(self):
        """Generate filename for QR code"""
        for record in self:
            if record.serial_number:
                # Sanitize filename
                safe_name = str(record.serial_number).replace('/', '-').replace(' ', '_')
                record.qr_code_filename = f"QR_{safe_name}.png"
            else:
                record.qr_code_filename = "QR_code.png"
    
    @api.model_create_multi
    def create(self, vals_list):
        """Override create to generate QR code automatically"""
        records = super(RentalEquipmentSerial, self).create(vals_list)
        
        # Generate QR codes for all new records
        for record in records:
            if record.serial_number:
                record._generate_qr_code()
        
        return records
    
    def write(self, vals):
        """Regenerate QR code if serial number changes"""
        result = super(RentalEquipmentSerial, self).write(vals)
        
        # Regenerate QR if serial_number changes
        if 'serial_number' in vals:
            for record in self:
                if record.serial_number:
                    record._generate_qr_code()
        
        return result
    
    def _generate_qr_code(self):
        """Generate QR code for this serial number"""
        self.ensure_one()
        
        if not self.serial_number:
            _logger.warning(f"Cannot generate QR code: no serial number for record {self.id}")
            return False
        
        try:
            # Import the QR generator
            from . import qr_generator
            
            # Get company logo if enabled
            logo_binary = None
            company = self.env.company
            
            if hasattr(company, 'use_qr_logo') and company.use_qr_logo and company.qr_logo:
                try:
                    logo_binary = base64.b64decode(company.qr_logo)
                except Exception as e:
                    _logger.warning(f"Could not decode company logo: {str(e)}")
            
            # Generate QR code (300x300 pixels)
            qr_base64 = qr_generator.generate_qr_code(
                data=str(self.serial_number),
                logo_binary=logo_binary,
                size=1080
            )
            
            if qr_base64:
                # Save to record
                self.qr_code = qr_base64
                _logger.info(f"QR code generated successfully for serial: {self.serial_number}")
                return True
            else:
                _logger.error(f"QR code generation failed for serial: {self.serial_number}")
                return False
            
        except ImportError as e:
            _logger.error(f"QR generator module not found: {str(e)}")
            return False
        except Exception as e:
            _logger.error(f"Failed to generate QR code for {self.serial_number}: {str(e)}")
            return False
    
    def action_regenerate_qr_code(self):
        """Manual action to regenerate QR code"""
        success_count = 0
        error_count = 0
        
        for record in self:
            if record._generate_qr_code():
                success_count += 1
            else:
                error_count += 1
        
        if success_count > 0:
            message = f'Successfully regenerated {success_count} QR code(s)'
            if error_count > 0:
                message += f' ({error_count} failed)'
            
            # return {
            #     'type': 'ir.actions.client',
            #     'tag': 'display_notification',
            #     'params': {
            #         'title': _('Success'),
            #         'message': message,
            #         'type': 'success',
            #         'sticky': False,
            #     }
            # }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': f'Failed to regenerate QR code(s). Check server logs. {record._generate_qr_code()}',
                    'type': 'danger',
                    'sticky': True,
                }
            }
    
    def action_download_qr_code(self):
        """Download QR code as PNG file"""
        self.ensure_one()
        
        if not self.qr_code:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Warning'),
                    'message': _('No QR code available. Please generate one first.'),
                    'type': 'warning',
                }
            }
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/rental.equipment.serial/{self.id}/qr_code/{self.qr_code_filename}?download=true',
            'target': 'self',
        }
    
    def action_print_qr_code(self):
        """Print QR code label"""
        self.ensure_one()
        
        # Generate QR if missing
        if not self.qr_code:
            self._generate_qr_code()
        
        # Check if QR code exists after generation attempt
        if not self.qr_code:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': _('Failed to generate QR code. Please check server logs.'),
                    'type': 'danger',
                    'sticky': True,
                }
            }
        
        # Return report action
        return self.env.ref('rental_management.action_report_qr_code_label').report_action(self)

# ========== USAGE INSTRUCTIONS ==========
# 
# 1. Find your existing rental_equipment_serial.py file
# 2. Add the imports at the top (if not there):
#    import base64
#    import logging
#    _logger = logging.getLogger(__name__)
#
# 3. Add the fields and methods to your existing class
# 4. Adjust the field name in @api.depends if needed
# 
# =========================================