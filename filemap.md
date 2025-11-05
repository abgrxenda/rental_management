## **Module Structure: rental_management**

```
rental_management/
│
├── __init__.py
├── __manifest__.py
│
├── security/
│   ├── ir.model.access.csv
│   └── rental_security.xml
│
├── data/
│   ├── rental_sequence.xml
│   └── rental_data.xml
│
├── models/
│   ├── __init__.py
│   ├── rental_equipment.py
│   ├── rental_equipment_category.py
│   ├── rental_equipment_serial.py
│   ├── rental_project.py
│   ├── rental_project_item.py
│   ├── rental_project_item_status.py
│   └── res_config_settings.py
│
├── views/
│   ├── rental_equipment_views.xml
│   ├── rental_equipment_category_views.xml
│   ├── rental_equipment_serial_views.xml
│   ├── rental_project_views.xml
│   ├── rental_project_item_views.xml
│   ├── rental_menus.xml
│   └── res_config_settings_views.xml
│
├── wizards/
│   ├── __init__.py
│   ├── rental_return_wizard.py
│   └── rental_return_wizard_views.xml
│
├── controllers/
│   ├── __init__.py
│   └── main.py
│
├── static/
│   └── description/
│       ├── icon.png
│       └── index.html
│
└── README.md
```

---

## **File Purpose Summary**

### **Root Files**
- `__init__.py` - Loads models, controllers, wizards
- `__manifest__.py` - Module metadata, dependencies, data files

### **security/**
- `ir.model.access.csv` - Access rights for all models
- `rental_security.xml` - Security groups and rules

### **data/**
- `rental_sequence.xml` - Auto-numbering for projects (RENT/0001)
- `rental_data.xml` - Default data (item statuses, categories)

### **models/**
- `rental_equipment.py` - Main equipment/items
- `rental_equipment_category.py` - Categories and groups
- `rental_equipment_serial.py` - Serial number tracking
- `rental_project.py` - Rental projects/bookings
- `rental_project_item.py` - Line items in projects
- `rental_project_item_status.py` - Status history per serial
- `res_config_settings.py` - Settings (late fees, etc.)

### **views/**
- XML files for each model's UI (forms, lists, search)
- `rental_menus.xml` - Main menu structure

### **wizards/**
- `rental_return_wizard.py` - Return process with damage assessment
- Views for the wizard

### **controllers/**
- `main.py` - API endpoints (REST API)

### **static/**
- `description/icon.png` - Module icon
- `description/index.html` - Module description page

---

## **Installation Order**

When Odoo loads the module:
1. **security/** - First (access rights)
2. **data/** - Second (sequences, default data)
3. **models/** - Auto-loaded
4. **views/** - After models
5. **wizards/** - After views
6. **controllers/** - Last

