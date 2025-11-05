# -*- coding: utf-8 -*-
{
    'name': 'Rental Management with QR Code Scanner',
    'version': '18.0.1.0.0',
    'category': 'Services/Rental',
    'summary': 'Complete rental management system with QR code generation and mobile scanning',
    'description': """
Rental Management System with Advanced QR Features
===================================================

Features:
---------
* Complete rental item and project management
* Automatic QR code generation for serial numbers
* Company-branded QR codes with logo overlay
* Mobile-friendly web-based QR scanner (uses device camera)
* Context-aware scanning (project, rental, maintenance workflows)
* Comprehensive scan logging and tracking
* Printable QR code labels
* Real-time item status updates via scanning
* Multi-camera support for mobile devices

QR Code Design:
---------------
* Circular dots instead of square blocks
* Rounded position markers
* Customizable company logo overlay
* High error correction level
* 1080x1080px output size

Scanning Workflows:
-------------------
* Add items to projects
* Handover to customers
* Return from customers
* Report damaged items
* Send to repair
* Item verification

Requirements:
-------------
* Python: qrcode, Pillow (PIL)
* JavaScript: jsQR library (included)
* Mobile device with camera for scanning
    """,
    'author': 'ÖMER KADİR | ÖMER TEKNOLOJİ',
    'website': 'https://omertek.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'web',
        'sale_management',
        'stock',
        'account',
        'contacts',
    ],
    'external_dependencies': {
        'python': ['qrcode', 'PIL'],
    },
    'data': [
        # Security
        'security/rental_security.xml',
        'security/ir.model.access.csv',
        
        # Data
        'data/rental_sequence.xml',
        'data/rental_data.xml',
        
        # Views - QR Features
        'views/qr_scanner_views.xml',

        # Views - Equipment/Items
        'views/rental_equipment_views.xml',
        'views/rental_equipment_category_views.xml',
        'views/rental_equipment_serial_views.xml',
        
        # Views - Projects
        'views/rental_project_views.xml',
        'views/rental_project_item_views.xml',
        
        # Views - Settings
        'views/res_config_settings_views.xml',
        
        # Wizards
        'wizards/rental_return_wizard_views.xml',
        'wizards/bulk_serial_wizard_views.xml',  # NEW - Add this line
        'wizards/serial_delete_confirm_wizard_views.xml',  # NEW - Add this line
        'wizards/serial_selection_wizard_views.xml',  # NEW - Add this line
        
        # Reports
        'reports/qr_label_report.xml',  # Make sure this line exists
        
        # Menus
        'views/rental_menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            # CSS
            # 'rental_management/static/src/css/qr_scanner.css',
            
            # JavaScript Libraries
            'rental_management/static/lib/jsQR/jsQR.js',
            
            # JavaScript Components
            # 'rental_management/static/src/js/qr_scanner.js',
            # 'rental_management/static/src/xml/qr_scanner_template.xml',
        ],
        # 'web.assets_frontend': [
        #     'rental_management/static/src/css/qr_scanner.css',
        # ],
    },
    'demo': [],
    'images': [
        'static/description/icon.png',
        'static/description/index.html',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'post_init_hook': 'post_init_hook',
}
