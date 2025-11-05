# -*- coding: utf-8 -*-

# Import Order Matters!
# 1. Models with no dependencies first
# 2. Models that depend on others last
# 3. Utilities before models that use them

# STEP 1: Import utility modules (no Odoo model dependencies)
from . import qr_generator  # Pure utility - no model imports

# STEP 2: Import base models (no dependencies on other rental models)
from . import rental_equipment_category  # No dependencies

# STEP 3: Import models with single-level dependencies
from . import rental_equipment  # Depends on: category

# STEP 4: Import models that depend on equipment
from . import rental_equipment_serial  # Depends on: equipment, qr_generator

# STEP 5: Import project-related models
from . import rental_project  # Depends on: equipment

# STEP 6: Import models that connect projects and equipment
from . import rental_project_item  # Depends on: project, equipment, serial

# STEP 7: Import status tracking models (depends on multiple models)
from . import rental_project_item_status  # Depends on: project, equipment, serial

# STEP 8: Import scan log (depends on serial and equipment)
from . import rental_scan_log  # Depends on: equipment, serial, project

# STEP 9: Import configuration/settings (can reference any model)
from . import res_config_settings  # Can reference company, etc.

from . import company_qr_extension  # If you have company logo feature