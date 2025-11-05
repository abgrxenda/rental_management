# Key Features:

# Full API key authentication - Using Odoo's native API keys
# Equipment endpoints - List, get details, check availability
# Project CRUD - Create, read, list projects
# Project lifecycle - Reserve, start, return, invoice
# SERIAL ENDPOINTS - Check status, quick rent, quick return via Serial Number (for scanner integration)
# Error handling - Comprehensive try-catch blocks
# Standard responses - Consistent success/error format
# Date serialization - Custom JSON encoder for dates
# Logging - All operations logged
# Flexible input - Accepts JSON or form data
# User context - All actions attributed to authenticated user

from odoo import http, fields, _
from odoo.http import request
import json
import logging
from datetime import date, datetime
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)


class DateTimeEncoder(json.JSONEncoder):
    """Custom JSON encoder for date/datetime objects"""
    def default(self, obj):
        if isinstance(obj, (date, datetime)):
            return obj.isoformat()
        return super().default(obj)


class RentalAPI(http.Controller):

    # ==================== Utilities and Authentication ====================

    def _verify_api_key(self, api_key):
        """Verify API key against Odoo user's API keys"""
        if not api_key:
            return False

        try:
            # Direct database query to get non-expired API keys
            request.env.cr.execute("""
                SELECT id, user_id, key, name, expiration_date
                FROM res_users_apikeys
                WHERE key = %s
                  AND (expiration_date IS NULL OR expiration_date >= current_timestamp)
            """, [api_key])
            result = request.env.cr.fetchone()
            
            if result:
                api_key_id, user_id, key, name, expiration_date = result
                # Log in the user associated with the API key
                request.session.authenticate(request.session.db, user_id, api_key) 
                return request.env['res.users'].sudo().browse(user_id)
            
            return False

        except Exception as e:
            _logger.error("API Key Verification Error: %s", str(e))
            return False

    def _check_auth(self):
        """
        Extracts API key from headers and verifies it.
        Returns error response if verification fails, otherwise None.
        """
        api_key = request.httprequest.headers.get('X-Api-Key')
        user = self._verify_api_key(api_key)
        
        if not user or not user.exists():
            return self._error_response('Authentication failed. Invalid or missing X-Api-Key.', 401)
        
        request.env.user = user.sudo()  # Set the current user context
        return None

    def _get_input_data(self):
        """Helper to get JSON data from the request body."""
        if request.httprequest.content_type == 'application/json':
            return json.loads(request.httprequest.data)
        return request.params

    def _success_response(self, data=None, message='Success', status=200):
        """Standard success JSON response."""
        return request.make_response(
            json.dumps({
                'status': 'success',
                'message': message,
                'data': data or {}
            }, cls=DateTimeEncoder),
            headers={'Content-Type': 'application/json'},
            status=status
        )

    def _error_response(self, message, status=400):
        """Standard error JSON response."""
        return request.make_response(
            json.dumps({
                'status': 'error',
                'message': message,
                'data': {}
            }, cls=DateTimeEncoder),
            headers={'Content-Type': 'application/json'},
            status=status
        )

    # ==================== Serial Number Endpoints (NEW FOR SCANNER) ====================
    
    @http.route('/api/rental/serial/<string:serial_number>', type='http', auth='public', methods=['GET'])
    def serial_get_status(self, serial_number, **kwargs):
        """Get detailed status and current project of a single serial number."""
        auth_error = self._check_auth()
        if auth_error:
            return auth_error
        
        try:
            Serial = request.env['rental.equipment.serial'].sudo()
            serial = Serial.search([('serial_number', '=', serial_number)], limit=1)
            
            if not serial:
                return self._error_response(f'Serial number {serial_number} not found', 404)
            
            data = {
                'id': serial.id,
                'serial_number': serial.serial_number,
                'equipment_name': serial.equipment_name,
                'status': serial.status,
                'status_label': dict(serial._fields['status'].selection).get(serial.status, serial.status),
                'current_project': {
                    'id': serial.current_project_id.id,
                    'name': serial.current_project_id.name,
                    'state': serial.current_project_id.state,
                } if serial.current_project_id else None
            }
            
            return self._success_response(data=data, message='Serial status retrieved successfully')
            
        except Exception as e:
            _logger.error(f"Error in serial_get_status: {str(e)}", exc_info=True)
            return self._error_response(str(e))

    @http.route('/api/rental/serial/rent', type='http', auth='public', methods=['POST'], csrf=False)
    def serial_quick_rent(self, **kwargs):
        """Quickly mark a serial number as 'rented' and assign it to a project."""
        auth_error = self._check_auth()
        if auth_error:
            return auth_error
        
        data = self._get_input_data()
        serial_number = data.get('serial_number')
        project_id = data.get('project_id')
        
        if not serial_number or not project_id:
            return self._error_response('Missing serial_number or project_id in request body.')

        try:
            Serial = request.env['rental.equipment.serial'].sudo()
            serial = Serial.search([('serial_number', '=', serial_number)], limit=1)
            project = request.env['rental.project'].sudo().browse(project_id)

            if not serial.exists():
                return self._error_response(f'Serial number {serial_number} not found', 404)
            if not project.exists():
                return self._error_response(f'Project ID {project_id} not found', 404)
            if project.state not in ['reserved', 'ongoing']:
                return self._error_response(f'Project {project.name} is not reserved or ongoing.', 400)
                
            # Find the corresponding item line in the project
            project_item = request.env['rental.project.item'].sudo().search([
                ('project_id', '=', project.id),
                ('equipment_id', '=', serial.equipment_id.id)
            ], limit=1)
            
            if not project_item.exists():
                return self._error_response(f"Equipment '{serial.equipment_name}' is not listed in project {project.name}.", 400)

            # Assign and set status to rented
            serial.write({
                'status': 'rented', 
                'current_project_id': project.id
            })
            
            # Link the serial to the project line item (if not already linked)
            project_item.write({'assigned_serial_ids': [(4, serial.id)]})

            return self._success_response(
                data={'serial_id': serial.id, 'project_id': project.id},
                message=f'Serial {serial_number} successfully rented and linked to project {project.name}'
            )

        except UserError as e:
            return self._error_response(str(e), 400)
        except Exception as e:
            _logger.error(f"Error in serial_quick_rent: {str(e)}", exc_info=True)
            return self._error_response(str(e))

    @http.route('/api/rental/serial/return', type='http', auth='public', methods=['POST'], csrf=False)
    def serial_quick_return(self, **kwargs):
        """Quickly mark a serial number as 'available' or 'damaged' and remove from project."""
        auth_error = self._check_auth()
        if auth_error:
            return auth_error
        
        data = self._get_input_data()
        serial_number = data.get('serial_number')
        damage_status = data.get('damage_status', 'available') # 'available' or 'damaged'
        damage_desc = data.get('damage_description', False)
        
        if not serial_number:
            return self._error_response('Missing serial_number in request body.')

        try:
            Serial = request.env['rental.equipment.serial'].sudo()
            serial = Serial.search([('serial_number', '=', serial_number)], limit=1)

            if not serial.exists():
                return self._error_response(f'Serial number {serial_number} not found', 404)

            # Get the current project to update
            project_id = serial.current_project_id.id
            project_name = serial.current_project_id.name
            
            new_status = 'available'
            
            if damage_status == 'damaged':
                new_status = 'damaged'
            elif damage_status == 'lost':
                new_status = 'lost'

            # 1. Update Serial Status and remove project link
            serial.write({
                'status': new_status,
                'current_project_id': False # Clear association
            })
            
            # 2. Log status change with damage info if applicable
            if new_status in ['damaged', 'lost']:
                request.env['rental.project.item.status'].sudo().create({
                    'project_id': project_id,
                    'equipment_id': serial.equipment_id.id,
                    'serial_id': serial.id,
                    'status': new_status,
                    'damage_description': damage_desc if new_status == 'damaged' else f'Marked as {new_status.upper()} via API',
                })
            
            message = f"Serial {serial_number} returned as '{new_status.upper()}'."
            if project_name:
                message += f" (Removed from project {project_name})"

            return self._success_response(
                data={'serial_id': serial.id, 'new_status': new_status},
                message=message
            )

        except UserError as e:
            return self._error_response(str(e), 400)
        except Exception as e:
            _logger.error(f"Error in serial_quick_return: {str(e)}", exc_info=True)
            return self._error_response(str(e))

    # ==================== Equipment Endpoints ====================

    @http.route('/api/rental/equipment/list', type='http', auth='public', methods=['GET'])
    def equipment_list(self, **kwargs):
        """List all available equipment."""
        auth_error = self._check_auth()
        if auth_error:
            return auth_error
        
        try:
            Equipment = request.env['rental.equipment'].sudo()
            equipment_records = Equipment.search([])
            
            data = [{
                'id': eq.id,
                'code': eq.code,
                'name': eq.name,
                'category': eq.category_id.name,
                'total_stock': eq.total_stock,
                'available_stock': eq.available_stock,
            } for eq in equipment_records]
            
            return self._success_response(data=data, message='Equipment list retrieved successfully')
            
        except Exception as e:
            _logger.error(f"Error in equipment_list: {str(e)}", exc_info=True)
            return self._error_response(str(e))

    @http.route('/api/rental/equipment/<int:equipment_id>', type='http', auth='public', methods=['GET'])
    def equipment_details(self, equipment_id, **kwargs):
        """Get details of a specific equipment item."""
        auth_error = self._check_auth()
        if auth_error:
            return auth_error
        
        try:
            Equipment = request.env['rental.equipment'].sudo()
            eq = Equipment.browse(equipment_id)
            
            if not eq.exists():
                return self._error_response('Equipment not found', 404)
            
            data = {
                'id': eq.id,
                'code': eq.code,
                'name': eq.name,
                'description': eq.description,
                'category': eq.category_id.name,
                'is_serialized': eq.is_serialized,
                'rate_day': eq.rate_day,
                'rate_week': eq.rate_week,
                'rate_month': eq.rate_month,
                'total_stock': eq.total_stock,
                'available_stock': eq.available_stock,
                'serials': [{'id': s.id, 'serial_number': s.serial_number, 'status': s.status} for s in eq.serial_ids],
            }
            
            return self._success_response(data=data, message='Equipment details retrieved successfully')
            
        except Exception as e:
            _logger.error(f"Error in equipment_details: {str(e)}", exc_info=True)
            return self._error_response(str(e))
            
    # ==================== Project Endpoints ====================

    @http.route('/api/rental/project/list', type='http', auth='public', methods=['GET'])
    def project_list(self, **kwargs):
        """List all rental projects."""
        auth_error = self._check_auth()
        if auth_error:
            return auth_error
        
        try:
            Project = request.env['rental.project'].sudo()
            projects = Project.search([], order='start_date desc')
            
            data = [{
                'id': p.id,
                'name': p.name,
                'customer': p.partner_id.name,
                'state': p.state,
                'start_date': p.start_date,
                'end_date': p.end_date,
                'grand_total': p.grand_total,
            } for p in projects]
            
            return self._success_response(data=data, message='Project list retrieved successfully')
            
        except Exception as e:
            _logger.error(f"Error in project_list: {str(e)}", exc_info=True)
            return self._error_response(str(e))

    @http.route('/api/rental/project/create', type='http', auth='public', methods=['POST'], csrf=False)
    def project_create(self, **kwargs):
        """Create a new rental project (Draft state)."""
        auth_error = self._check_auth()
        if auth_error:
            return auth_error
        
        data = self._get_input_data()
        
        try:
            # Required fields: partner_id, project_item_ids (list of dicts)
            
            # Simple validation for required fields
            if not data.get('partner_id') or not data.get('project_item_ids'):
                 return self._error_response('Missing required fields: partner_id and project_item_ids', 400)
            
            # Prepare line items: convert list of dicts to Odoo command (0, 0, vals)
            project_items = []
            for item in data.pop('project_item_ids', []):
                project_items.append((0, 0, item))
                
            project_vals = {
                'partner_id': data.get('partner_id'),
                'start_date': data.get('start_date', fields.Date.today()),
                'end_date': data.get('end_date'),
                'reference': data.get('reference'),
                'project_item_ids': project_items,
                'user_id': request.env.user.id
            }

            Project = request.env['rental.project'].sudo()
            new_project = Project.create(project_vals)
            
            return self._success_response(
                data={'id': new_project.id, 'name': new_project.name, 'state': new_project.state},
                message=f'Project {new_project.name} created successfully'
            )
            
        except UserError as e:
            return self._error_response(str(e), 400)
        except Exception as e:
            _logger.error(f"Error in project_create: {str(e)}", exc_info=True)
            return self._error_response(str(e))
    
    @http.route('/api/rental/project/<int:project_id>/reserve', type='http', auth='public', methods=['POST'], csrf=False)
    def project_reserve(self, project_id, **kwargs):
        """Move project to Reserved status and assign serials."""
        auth_error = self._check_auth()
        if auth_error:
            return auth_error
        
        try:
            Project = request.env['rental.project'].sudo()
            project = Project.browse(project_id)
            if not project.exists():
                return self._error_response('Project not found', 404)
            
            project.action_reserve()
            
            return self._success_response(
                data={'id': project.id, 'state': project.state},
                message=f'Project {project.name} reserved successfully'
            )
            
        except UserError as e:
            return self._error_response(str(e), 400)
        except Exception as e:
            _logger.error(f"Error in project_reserve: {str(e)}", exc_info=True)
            return self._error_response(str(e))
            
    @http.route('/api/rental/project/<int:project_id>/start', type='http', auth='public', methods=['POST'], csrf=False)
    def project_start(self, project_id, **kwargs):
        """Move project to Ongoing status."""
        auth_error = self._check_auth()
        if auth_error:
            return auth_error
        
        try:
            Project = request.env['rental.project'].sudo()
            project = Project.browse(project_id)
            if not project.exists():
                return self._error_response('Project not found', 404)
            
            project.action_start()
            
            return self._success_response(
                data={'id': project.id, 'state': project.state},
                message=f'Project {project.name} started (Ongoing) successfully'
            )
            
        except UserError as e:
            return self._error_response(str(e), 400)
        except Exception as e:
            _logger.error(f"Error in project_start: {str(e)}", exc_info=True)
            return self._error_response(str(e))

    @http.route('/api/rental/project/<int:project_id>/return', type='http', auth='public', methods=['POST'], csrf=False)
    def project_return(self, project_id, **kwargs):
        """Move project to Returned status (Does NOT handle damage/return wizard)"""
        auth_error = self._check_auth()
        if auth_error:
            return auth_error
        
        try:
            Project = request.env['rental.project'].sudo()
            project = Project.browse(project_id)
            if not project.exists():
                return self._error_response('Project not found', 404)
            
            # This uses the action_return, which sets status to 'returned' and unlinks serials.
            project.action_return()
            
            return self._success_response(
                data={
                    'id': project.id, 
                    'state': project.state,
                    'grand_total': project.grand_total,
                    'late_fee': project.late_fee_amount
                },
                message=f'Project {project.name} returned successfully'
            )
            
        except UserError as e:
            return self._error_response(str(e), 400)
        except Exception as e:
            _logger.error(f"Error in project_return: {str(e)}", exc_info=True)
            return self._error_response(str(e))
    
    @http.route('/api/rental/project/<int:project_id>/invoice', type='http', auth='public', methods=['POST'], csrf=False)
    def project_create_invoice(self, project_id, **kwargs):
        """Create invoice for project"""
        auth_error = self._check_auth()
        if auth_error:
            return auth_error
        
        try:
            Project = request.env['rental.project'].sudo()
            project = Project.browse(project_id)
            if not project.exists():
                return self._error_response('Project not found', 404)
            
            project.action_create_invoice()
            
            return self._success_response(
                data={
                    'invoice_id': project.invoice_id.id,
                    'invoice_name': project.invoice_id.name
                },
                message='Invoice created successfully'
            )
            
        except UserError as e:
            return self._error_response(str(e), 400)
        except Exception as e:
            _logger.error(f"Error in project_create_invoice: {str(e)}", exc_info=True)
            return self._error_response(str(e))
