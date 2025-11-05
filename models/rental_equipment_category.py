# Key Features:

# Hierarchical structure - Categories can have parent/child relationships
# _parent_store - Optimizes hierarchical queries
# Attribute groups - Can be used as equipment attributes (from your categorygroup concept)
# Equipment count - Shows how many items in each category
# Recursive check - Prevents circular parent-child loops
# name_get - Shows full path (e.g., "Electronics / Laptops")

from odoo import models, fields, api


class RentalEquipmentCategory(models.Model):
    _name = 'rental.equipment.category'
    _description = 'Equipment Category'
    _order = 'sequence, name'
    _parent_name = 'parent_id'
    _parent_store = True
    
    name = fields.Char('Category Name', required=True, translate=True)
    parent_id = fields.Many2one(
        'rental.equipment.category', 
        'Parent Category', 
        ondelete='cascade',
        index=True
    )
    parent_path = fields.Char(index=True)
    child_ids = fields.One2many(
        'rental.equipment.category', 
        'parent_id', 
        'Sub-Categories'
    )
    
    description = fields.Text('Description', translate=True)
    image = fields.Binary('Image', attachment=True)
    image_filename = fields.Char('Image Filename')
    
    # Category Group Features (from your categorygroup table)
    is_attribute_group = fields.Boolean(
        'Is Attribute Group',
        help='Use as attribute group for equipment classification'
    )
    selection_mode = fields.Selection([
        ('single', 'Single Selection'),
        ('multiple', 'Multiple Selection')
    ], string='Selection Mode', default='multiple',
       help='When used as attribute group: allow single or multiple selection')
    
    # Equipment count
    equipment_count = fields.Integer(
        'Equipment Count',
        compute='_compute_equipment_count'
    )
    
    sequence = fields.Integer('Sequence', default=10)
    active = fields.Boolean('Active', default=True)
    
    @api.depends('parent_id')
    def _compute_equipment_count(self):
        """Count equipment in this category and subcategories"""
        for category in self:
            # Get all child category IDs (including self)
            child_ids = self.search([
                ('id', 'child_of', category.id)
            ]).ids
            
            # Count equipment in these categories
            category.equipment_count = self.env['rental.equipment'].search_count([
                ('category_ids', 'in', child_ids)
            ])
    
    @api.constrains('parent_id')
    def _check_category_recursion(self):
        """Prevent circular references"""
        if not self._check_recursion():
            raise models.ValidationError('You cannot create recursive categories.')
    
    def name_get(self):
        """Display full category path in selection fields"""
        result = []
        for category in self:
            if category.parent_id:
                name = f"{category.parent_id.name} / {category.name}"
            else:
                name = category.name
            result.append((category.id, name))
        return result