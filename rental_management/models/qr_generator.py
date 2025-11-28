# """
# QR Code Generator with Custom Design
# Replicates the PHP design: circular dots, rounded position markers, and logo overlay
# """
# Error
# Failed to regenerate QR code(s). Check server logs. Failed to generate QR code for EQ-0001-0002: module 'odoo.addons.rental_management.models.qr_generator' has no attribute 'generate_qr_code

import qrcode
from PIL import Image, ImageDraw
from io import BytesIO
import base64
import logging

_logger = logging.getLogger(__name__)

class QRCodeGenerator:
    """Generate QR codes with circular dots and rounded corners"""
    
    def __init__(self, data, logo_path=None, output_size=1080):
        self.data = data
        self.logo_path = logo_path
        self.output_size = output_size
        self.qr_size = 1100
        self.margin = 60
        
    def generate(self):
        """Main generation method"""
        # Step 1: Generate base QR code matrix
        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=10,
            border=0,
        )
        qr.add_data(self.data)
        qr.make(fit=True)
        
        matrix = qr.get_matrix()
        block_count = len(matrix)
        
        # Calculate block size to fit into qr_size with margin
        available_size = self.qr_size - (2 * self.margin)
        block_size = available_size / block_count
        
        # Step 2: Create blank image
        scale = self.output_size / self.qr_size
        img = Image.new('RGB', (self.output_size, self.output_size), 'white')
        draw = ImageDraw.Draw(img)
        
        # Step 3: Draw circular dots (skip position markers)
        for row in range(block_count):
            for col in range(block_count):
                if not matrix[row][col]:
                    continue
                    
                # Skip position markers
                if self._is_in_position_marker(row, col, block_count):
                    continue
                
                # Calculate center position
                center_x = self.margin + (col + 0.5) * block_size
                center_y = self.margin + (row + 0.5) * block_size
                
                # Scale to output size
                center_x = int(center_x * scale)
                center_y = int(center_y * scale)
                radius = int(block_size * scale * 0.5)
                
                # Draw circle
                draw.ellipse(
                    [center_x - radius, center_y - radius,
                     center_x + radius, center_y + radius],
                    fill='black'
                )
        
        # Step 4: Draw position markers with rounded corners
        self._draw_position_marker(draw, 0, 0, block_count, block_size, scale)
        self._draw_position_marker(draw, block_count - 7, 0, block_count, block_size, scale)
        self._draw_position_marker(draw, 0, block_count - 7, block_count, block_size, scale)
        
        # Step 5: Add logo if provided
        # if self.logo_path:
            # self._add_logo(img)
        
        return img
    
    def _is_in_position_marker(self, row, col, size):
        """Check if block is within a position marker"""
        marker_size = 7
        return (
            (row < marker_size and col < marker_size) or
            (row < marker_size and col >= size - marker_size) or
            (row >= size - marker_size and col < marker_size)
        )
    
    def _draw_position_marker(self, draw, start_col, start_row, block_count, block_size, scale):
        """Draw 7x7 position marker with rounded outer corners"""
        marker_size = 7
        
        # Determine which marker this is for corner rounding
        is_top_left = (start_col == 0 and start_row == 0)
        is_top_right = (start_col != 0 and start_row == 0)
        is_bottom_left = (start_col == 0 and start_row != 0)
        
        for layer in range(3):
            offset = layer
            inner_size = marker_size - 2 * layer
            
            for r in range(inner_size):
                for c in range(inner_size):
                    row = start_row + offset + r
                    col = start_col + offset + c
                    
                    # Calculate block position
                    x1 = self.margin + col * block_size
                    y1 = self.margin + row * block_size
                    
                    # Scale to output size
                    x1 = int(x1 * scale)
                    y1 = int(y1 * scale)
                    w = int(block_size * scale)
                    h = int(block_size * scale)
                    
                    color = 'white' if layer == 1 else 'black'
                    
                    # Check if this is a corner block of the outer layer
                    is_outer_layer = (layer == 0)
                    is_corner = False
                    corner_type = None
                    
                    # if is_outer_layer:
                    if is_top_left:
                        if r == 0 and c == 0:
                            is_corner = True
                            corner_type = 'top_left'
                        elif r == 0 and c == inner_size - 1:
                            is_corner = True
                            corner_type = 'top_right'
                        elif r == inner_size - 1 and c == 0:
                            is_corner = True
                            corner_type = 'bottom_left'
                    elif is_top_right:
                        if r == 0 and c == 0:
                            is_corner = True
                            corner_type = 'top_left'
                        elif r == 0 and c == inner_size - 1:
                            is_corner = True
                            corner_type = 'top_right'
                        elif r == inner_size - 1 and c == inner_size - 1:
                            is_corner = True
                            corner_type = 'bottom_right'
                    elif is_bottom_left:
                        if r == 0 and c == 0:
                            is_corner = True
                            corner_type = 'top_left'
                        elif r == inner_size - 1 and c == 0:
                            is_corner = True
                            corner_type = 'bottom_left'
                        elif r == inner_size - 1 and c == inner_size - 1:
                            is_corner = True
                            corner_type = 'bottom_right'
                    
                    if is_corner:
                        self._draw_rounded_corner(draw, x1, y1, w, h, color, corner_type)
                    else:
                        draw.rectangle([x1, y1, x1 + w, y1 + h], fill=color)
    
    def _draw_rounded_corner(self, draw, x1, y1, w, h, color, corner_type):
        """Draw a rounded corner block"""
        radius = max(w, h)
        
        if corner_type == 'top_left':
            draw.pieslice([x1, y1, x1 + radius * 2, y1 + radius * 2], 180, 270, fill=color)
        elif corner_type == 'top_right':
            draw.pieslice([x1 - radius, y1, x1 + radius, y1 + radius * 2], 270, 360, fill=color)
        elif corner_type == 'bottom_left':
            draw.pieslice([x1, y1 - radius, x1 + radius * 2, y1 + radius], 90, 180, fill=color)
        elif corner_type == 'bottom_right':
            draw.pieslice([x1 - radius, y1 - radius, x1 + radius, y1 + radius], 0, 90, fill=color)
    
    def _add_logo(self, img):
        """Add logo to center of QR code"""
        try:
            # Load logo (can be file path or binary data)
            if isinstance(self.logo_path, bytes):
                logo = Image.open(io.BytesIO(self.logo_path))
            else:
                logo = Image.open(self.logo_path)
            
            # Convert to RGBA if needed
            if logo.mode != 'RGBA':
                logo = logo.convert('RGBA')
            
            # Resize logo to 15% of QR code size
            max_logo_size = int(self.output_size * 0.15)
            logo.thumbnail((max_logo_size, max_logo_size), Image.Resampling.LANCZOS)
            
            # Calculate center position
            logo_x = (self.output_size - logo.width) // 2
            logo_y = (self.output_size - logo.height) // 2
            
            # Paste logo onto QR code
            img.paste(logo, (logo_x, logo_y), logo)
        except Exception as e:
            # If logo fails, continue without it
            pass
    
    def get_base64(self):
        """Generate and return base64 encoded PNG"""
        img = self.generate()
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        return base64.b64encode(buffer.getvalue()).decode()
    
    def save(self, filepath):
        """Generate and save to file"""
        img = self.generate()
        img.save(filepath, 'PNG')

def generate_qr_code(data, logo_binary=None, size=1080):
    """
    Generate a QR code image with optional logo overlay.
    
    Args:
        data (str): Data to encode in QR code (e.g., serial number)
        logo_binary (bytes): Optional logo image as binary data
        size (int): Size of the QR code in pixels (default: 300)
        
    Returns:
        str: Base64 encoded PNG image
    """
    try:
        # Create QR code instance
        # qr = qrcode.QRCode(
        #     version=1,  # Controls the size of the QR code
        #     error_correction=qrcode.constants.ERROR_CORRECT_H,  # High error correction
        #     box_size=10,  # Size of each box in pixels
        #     border=4,  # Border size in boxes
        # )
        
        # # Add data
        # qr.add_data(data)
        # qr.make(fit=True)
        
        # # Create image
        # img = qr.make_image(fill_color="black", back_color="white")
        
        # # Resize to desired size
        # img = img.resize((size, size))

        generator = QRCodeGenerator(data, logo_binary)
        img = generator.generate()
        
        # Add logo if provided
        if logo_binary:
            try:
                from PIL import Image
                logo = Image.open(BytesIO(logo_binary))
                
                # Calculate logo size (20% of QR code)
                logo_size = int(size * 0.15)
                logo = logo.resize((logo_size, logo_size))
                
                # Calculate position (center)
                logo_pos = ((size - logo_size) // 2, (size - logo_size) // 2)
                
                # Paste logo onto QR code
                img.paste(logo, logo_pos)
            except Exception as e:
                _logger.warning(f"Could not add logo to QR code: {str(e)}")
                # Continue without logo
        
        # Convert to base64
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        img_base64 = base64.b64encode(buffer.getvalue()).decode()
        
        return img_base64
        
    except Exception as e:
        _logger.error(f"Error generating QR code: {str(e)}")
        return False
