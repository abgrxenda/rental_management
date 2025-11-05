# Key Features:

# Complete history - Track every status change for equipment/serials
# User tracking - Who made each change
# Timestamp - When each change occurred
# Damage tracking - Severity, description, cost estimate
# Photo documentation - Attach photos to status changes
# Non-serialized support - Can track quantity for non-serialized items
# Audit trail - Full history for compliance/disputes
# Smart name_get - Shows equipment, serial, and status in displays

from odoo import models, fields, api


class RentalProjectItemStatus(models.Model):
    _name = 'rental.project.item.status'
    _description = 'Rental Item Status History'
    _order = 'create_date desc, id desc'
    _rec_name = 'status'
    
    project_id = fields.Many2one(
        'rental.project',
        'Project',
        required=True,
        ondelete='cascade',
        index=True
    )
    project_name = fields.Char(
        'Project',
        related='project_id.name',
        readonly=True,
        store=True
    )
    
    equipment_id = fields.Many2one(
        'rental.equipment',
        'Equipment',
        required=True,
        ondelete='restrict',
        index=True
    )
    equipment_name = fields.Char(
        'Equipment',
        related='equipment_id.name',
        readonly=True,
        store=True
    )
    
    serial_id = fields.Many2one(
        'rental.equipment.serial',
        'Serial Number',
        ondelete='restrict',
        index=True
    )
    serial_number = fields.Char(
        'Serial',
        related='serial_id.serial_number',
        readonly=True,
        store=True
    )
    
    # For non-serialized items
    quantity = fields.Integer(
        'Quantity',
        default=1,
        help='Quantity affected by this status change'
    )
    
    # Status tracking
    status = fields.Selection([
        ('reserved', 'Reserved'),
        ('rented', 'Rented'),
        ('returned', 'Returned'),
        ('damaged', 'Damaged'),
        ('repairing', 'Under Repair'),
        ('repaired', 'Repaired'),
        ('disposed', 'Disposed')
    ], string='Status', required=True, index=True)
    
    # Additional information
    notes = fields.Text('Notes')
    user_id = fields.Many2one(
        'res.users',
        'Changed By',
        default=lambda self: self.env.user,
        readonly=True
    )
    
    # Photos for this status change
    photo_ids = fields.Many2many(
        'ir.attachment',
        'rental_status_photo_rel',
        'status_id',
        'attachment_id',
        string='Photos'
    )
    
    # Damage assessment (if status is damaged)
    damage_description = fields.Text('Damage Description')
    damage_severity = fields.Selection([
        ('minor', 'Minor'),
        ('moderate', 'Moderate'),
        ('severe', 'Severe')
    ], string='Damage Severity')
    repair_cost_estimate = fields.Float('Estimated Repair Cost')
    
    create_date = fields.Datetime('Date', readonly=True, index=True)
    
    @api.model
    def create(self, vals):
        """Auto-set user on creation"""
        if 'user_id' not in vals:
            vals['user_id'] = self.env.user.id
        return super().create(vals)
    
    def name_get(self):
        """Custom display name"""
        result = []
        for record in self:
            if record.serial_id:
                name = f"[{record.equipment_name}] {record.serial_number} - {dict(record._fields['status'].selection).get(record.status)}"
            else:
                name = f"[{record.equipment_name}] Qty: {record.quantity} - {dict(record._fields['status'].selection).get(record.status)}"
            result.append((record.id, name))
        return result
    
    def action_view_photos(self):
        """View photos for this status entry"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Status Photos'),
            'res_model': 'ir.attachment',
            'view_mode': 'kanban,list,form',
            'domain': [('id', 'in', self.photo_ids.ids)],
        }