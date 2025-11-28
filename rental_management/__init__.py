# This root __init__.py file:

# Imports the three main module folders (models, controllers, wizards)
# Includes a post_init_hook function (referenced in manifest)
# The hook runs once after module installation

# -*- coding: utf-8 -*-

# Import modules AFTER checking dependencies
# This prevents circular import issues

import logging
import subprocess
import sys

_logger = logging.getLogger(__name__)


def _install_python_dependencies():
    """
    Attempt to install required Python packages
    This runs during module installation
    """
    required_packages = {
        'qrcode': 'qrcode[pil]>=7.4.2',
        'PIL': 'Pillow>=10.0.0',
    }
    
    missing_packages = []
    
    # Check which packages are missing
    for import_name, package_spec in required_packages.items():
        try:
            __import__(import_name)
        except ImportError:
            missing_packages.append(package_spec)
    
    if not missing_packages:
        _logger.info("✅ All Python dependencies are already installed")
        return True
    
    # Try to install missing packages
    _logger.warning(f"⚠️  Missing Python packages: {', '.join(missing_packages)}")
    _logger.info("📦 Attempting to install missing packages automatically...")
    
    try:
        # Install packages using pip
        subprocess.check_call([
            sys.executable, '-m', 'pip', 'install', '--quiet'
        ] + missing_packages)
        
        _logger.info("✅ Successfully installed all missing Python packages")
        return True
        
    except subprocess.CalledProcessError as e:
        _logger.error(f"❌ Failed to install Python dependencies: {str(e)}")
        _logger.error("👉 Please manually install: pip install qrcode[pil] Pillow")
        return False
    except Exception as e:
        _logger.error(f"❌ Unexpected error installing dependencies: {str(e)}")
        _logger.error("👉 Please manually install: pip install qrcode[pil] Pillow")
        return False


# Import sub-modules AFTER dependency check
# This is IMPORTANT to avoid circular imports
from . import models
from . import controllers
from . import wizards


def post_init_hook(env):
    """
    Post-installation hook
    1. Install Python dependencies if missing
    2. Generate QR codes for existing serial numbers
    """
    _logger.info("=" * 60)
    _logger.info("🚀 Running post-installation hook for Rental Management...")
    _logger.info("=" * 60)
    
    # Step 1: Install dependencies
    deps_installed = _install_python_dependencies()
    
    if not deps_installed:
        _logger.warning(
            "⚠️  QR code generation may fail. "
            "Please manually install: pip install qrcode[pil] Pillow"
        )
        # Don't return - still try to generate QR codes in case packages exist
    
    # Step 2: Generate QR codes for existing serials
    try:
        _logger.info("📋 Checking for serial numbers without QR codes...")
        
        SerialNumber = env['rental.equipment.serial']
        serials_without_qr = SerialNumber.search([
            ('qr_code', '=', False),
            ('name', '!=', False)
        ])
        
        total = len(serials_without_qr)
        if total == 0:
            _logger.info("✅ No serial numbers need QR code generation")
            _logger.info("=" * 60)
            return
        
        _logger.info(f"📊 Found {total} serial numbers without QR codes")
        _logger.info("🔄 Starting QR code generation...")
        
        # Generate QR codes in batches
        batch_size = 50
        generated = 0
        failed = 0
        
        for i in range(0, total, batch_size):
            batch = serials_without_qr[i:i+batch_size]
            
            for serial in batch:
                try:
                    serial._generate_qr_code()
                    generated += 1
                    
                    if generated % 10 == 0:
                        _logger.info(f"  ⏳ Progress: {generated}/{total} QR codes generated...")
                        
                except Exception as e:
                    failed += 1
                    _logger.error(f"  ❌ Failed to generate QR for {serial.name}: {str(e)}")
            
            # Commit after each batch
            env.cr.commit()
        
        _logger.info("=" * 60)
        _logger.info(f"✅ Successfully generated {generated} QR codes")
        if failed > 0:
            _logger.warning(f"⚠️  Failed to generate {failed} QR codes")
        _logger.info("=" * 60)
        
    except Exception as e:
        _logger.error(f"❌ Error in post_init_hook: {str(e)}")
        _logger.info("=" * 60)