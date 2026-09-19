from .base_api import BaseERPClient
from .file_api import FileService
from .profile_api import ProfileService
from .tenant_api import TenantService
from .maintenance_api import MaintenanceService
from .visitor_api import VisitorService
from .guard_api import GuardService
from .notice_api import NoticeService
from .dues_api import DuesService
from .facility_api import FacilityService
from .staff_api import StaffService  
from .family_api import FamilyService  
from .work_permit_api import WorkPermitService # ? NEW
from api.vehicle_api import VehicleService

class ERPClient(BaseERPClient):
    def __init__(self):
        super().__init__()
        # Instantiate granular services
        self.file = FileService(self)
        self.profile = ProfileService(self)
        self.tenant = TenantService(self, self.file)
        self.maintenance = MaintenanceService(self, self.file)
        self.visitor = VisitorService(self)
        self.guard = GuardService(self)
        self.notice = NoticeService(self)
        self.dues = DuesService(self)
        self.facility = FacilityService(self)
        self.staff = StaffService(self) 
        self.family = FamilyService(self) 
        self.work_permit = WorkPermitService(self) # ? NEW
        self.vehicle = VehicleService(self)

    # --- Profile Wrappers ---
    def get_resident_profile(self, flat_number): return self.profile.get_resident_profile(flat_number)
    def get_profile_by_chat_id(self, chat_id): return self.profile.get_profile_by_chat_id(chat_id)
    def register_resident(self, flat_number, chat_id, user_id, role,phone): return self.profile.register_resident(flat_number, chat_id, user_id, role,phone)
    def logout_resident(self, flat_number, chat_id): return self.profile.logout_resident(flat_number, chat_id)
    def update_resident_field(self, flat_number, chat_id, field_type, new_value): return self.profile.update_resident_field(flat_number, chat_id, field_type, new_value)
    def get_resident_chat_id(self, flat_number): return self.profile.get_resident_chat_id(flat_number)
# --- Notification Wrapper ---
    def get_notification_chat_ids(self, flat_number): return self.profile.get_notification_chat_ids(flat_number)

    # --- Tenant Wrappers ---
    def upload_tenant_document(self, flat_number, file_data, file_name, mime_type): return self.tenant.upload_tenant_document(flat_number, file_data, file_name, mime_type)
    def create_active_tenant(self, flat_number, tenant_data): return self.tenant.create_active_tenant(flat_number, tenant_data)
    def deactivate_tenant(self, flat_number): return self.tenant.deactivate_tenant(flat_number)
    def update_tenant_details(self, flat_number, field_type, new_value): return self.tenant.update_tenant_details(flat_number, field_type, new_value)
    def get_previous_tenants(self, flat_number): return self.tenant.get_previous_tenants(flat_number)
    def reactivate_last_tenant(self, flat_number): return self.tenant.reactivate_last_tenant(flat_number)

    # --- Maintenance Wrappers ---
    def create_maintenance_ticket(self, flat_number, category, description): return self.maintenance.create_maintenance_ticket(flat_number, category, description)
    def get_user_tickets(self, flat_number, offset=0, status_filter="Open"): return self.maintenance.get_user_tickets(flat_number, offset, status_filter)
    def get_ticket_details(self, ticket_name): return self.maintenance.get_ticket_details(ticket_name)
    def upload_file_to_ticket(self, ticket_name, file_data): return self.maintenance.upload_file_to_ticket(ticket_name, file_data)

    # --- Visitor Wrappers ---
    def get_frequent_visitors(self, resident): return self.visitor.get_frequent_visitors(resident)
    def create_preapproved_visitor(self, *args, **kwargs): return self.visitor.create_preapproved_visitor(*args, **kwargs)
    def get_visitor_history(self, resident, offset_weeks=0): return self.visitor.get_visitor_history(resident, offset_weeks)
    def verify_visitor_passcode(self, passcode): return self.visitor.verify_visitor_passcode(passcode)
    def create_walkin_visitor(self, resident, visitor_name, purpose="Guest"): return self.visitor.create_walkin_visitor(resident, visitor_name, purpose)
    def update_visitor_status(self, docname, status): return self.visitor.update_visitor_status(docname, status)

    # ==========================
    # FAMILY WRAPPERS
    # ==========================
    def get_family_members(self, flat: str, status: str = "Active"):
        return self.family.get_family_members(flat, status=status)
        
    def verify_family_member(self, flat_number, mobile_no): 
        return self.family.verify_family_member(flat_number, mobile_no)
        
    def add_family_member(self, flat_number, name, relation, mobile_no): 
        return self.family.add_family_member(flat_number, name, relation, mobile_no)
    
    # ? ADD THIS METHOD
    def activate_family_member(self, member_id: str):
        return self.family.activate_family_member(member_id)
    
    def deactivate_family_member(self, member_id: str):
        return self.family.deactivate_family_member(member_id)
    # ==========================
    # STAFF WRAPPERS
    # ==========================
    def get_domestic_staff(self, flat_number): 
        return self.staff.get_domestic_staff(flat_number)
        
    def create_staff_pass(self, flat_number, staff_name, role): 
        return self.staff.create_staff_pass(flat_number, staff_name, role)

    def get_staff_by_category(self, category): 
        return self.staff.get_staff_by_category(category)

    def verify_staff_pass(self, staff_id): 
        return self.staff.verify_staff_pass(staff_id)
        
    def link_staff_to_flat(self, staff_id, flat_number): 
        return self.staff.link_staff_to_flat(staff_id, flat_number)
    def get_staff_details(self, staff_id):

        return self.staff.get_staff_details(staff_id)

    def unlink_staff_from_flat(self, staff_id, flat_number):
        return self.staff.unlink_staff_from_flat(staff_id, flat_number)

    def submit_staff_review(self, staff_id, flat, review_type, rating=0, comments=""):
        return self.staff.submit_staff_review(staff_id, flat, review_type, rating, comments)

    # --- Guard Wrapper ---
    def is_authorized_guard(self, chat_id, platform): return self.guard.is_authorized_guard(chat_id, platform)
   # ==========================
    # WORK PERMIT WRAPPERS
    # ==========================
    def create_work_permit(self, flat_number, chat_id, data):
        return self.work_permit.create_work_permit(flat_number, chat_id, data)

    def get_active_permits(self, flat_number):
        return self.work_permit.get_active_permits(flat_number)

    def create_worker_pass(self, work_permit_id, worker_name):
        return self.work_permit.create_worker_pass(work_permit_id, worker_name)

    def verify_worker_pass(self, worker_pass_id):
        return self.work_permit.verify_worker_pass(worker_pass_id)

    # ? UPDATED wrappers below ?
    def get_all_active_work_permits(self, block_prefix=None):
        return self.work_permit.get_all_active_work_permits(block_prefix)

    def report_permit_violation(self, permit_id, reported_by_flat, violation_type):
        return self.work_permit.report_permit_violation(permit_id, reported_by_flat, violation_type)
    # Ensure this method is updated in your Work Permit Wrappers section
    def create_violation_report(self, reported_by_flat, violation_type, permit_id, block, description):
        return self.work_permit.create_violation_report(reported_by_flat, violation_type, permit_id, block, description)
    def report_unknown_permit_violation(self, block, reported_by_flat, violation_type):
        return self.work_permit.report_unknown_permit_violation(block, reported_by_flat, violation_type)
    def get_violations_by_flat(self, flat_number):
        return self.work_permit.get_violations_by_flat(flat_number)
    def get_all_active_violations(self):
        return self.work_permit.get_all_active_violations()
    def get_violation_details(self, violation_id):
        return self.work_permit.get_violation_details(violation_id)
    # --- Facility, Notices & Dues ---
    def book_facility(self, facility, flat, date_str): return self.facility.book_facility(facility, flat, date_str)
    def get_active_notices(self): return self.notice.get_active_notices()
    def get_outstanding_dues(self, flat_number): return self.dues.get_outstanding_dues(flat_number)

    # --- Base Files Wrappers ---
    def upload_file(self, *args, **kwargs): return self.file.upload_file(*args, **kwargs)
    def get_attachments(self, doctype, docname): return self.file.get_attachments(doctype, docname)
    def download_file(self, file_name): return self.file.download_file(file_name)

    # In api/erp.py inside your ERPClient class
    # 👇 ADDED: order_by parameter (defaults to None)
    def get_list(self, doctype: str, filters: str = None, fields: str = None, limit: int = 100, order_by: str = None) -> dict:
        """Generic method to fetch a list of records from any ERPNext DocType."""
        import requests
        
        url = f"{self.base_url}/{doctype}"
        params = {"limit_page_length": limit}
        
        if filters:
            params["filters"] = filters
        if fields:
            params["fields"] = fields
        # 👇 NEW: Add the sorting parameter if provided
        if order_by:
            params["order_by"] = order_by
            
        try:
            response = requests.get(url, headers=self.headers, params=params)
            if response.status_code == 200:
                return response.json()
            else:
                from utils.logger import app_logger
                app_logger.error(f"API Error fetching {doctype} ({response.status_code}): {response.text}")
                return {}
        except Exception as e:
            from utils.logger import app_logger
            app_logger.error(f"Request failed for {doctype}: {str(e)}")
            return {}


    def create_document(self, doctype: str, data: dict) -> dict:
        """Generic method to create a new record in any ERPNext DocType."""
        import requests
        url = f"{self.base_url}/{doctype}"
        try:
            response = requests.post(url, headers=self.headers, json=data)
            if response.status_code == 200:
                return response.json().get("data", {})
            else:
                from utils.logger import app_logger
                app_logger.error(f"Failed to create {doctype}: {response.text}")
                return {}
        except Exception as e:
            return {}
    def update_document(self, doctype: str, docname: str, data: dict) -> bool:
        """Generic method to update fields in any ERPNext DocType."""
        import requests
        
        url = f"{self.base_url}/{doctype}/{docname}"
        try:
            # ERPNext uses PUT requests to update existing documents
            response = requests.put(url, headers=self.headers, json=data)
            if response.status_code == 200:
                return True
            else:
                from utils.logger import app_logger
                app_logger.error(f"Failed to update {doctype} {docname}: {response.text}")
                return False
        except Exception as e:
            return False


    def append_remark(self, doctype: str, docname: str, author: str, new_remark: str) -> bool:
        """Fetches existing remarks, appends the new one with a timestamp, and updates ERPNext."""
        from datetime import datetime
        import requests
        
        url = f"{self.base_url}/{doctype}/{docname}"
        try:
            # 1. Fetch current document to get existing remarks
            response = requests.get(url, headers=self.headers)
            if response.status_code == 200:
                data = response.json().get("data", {})
                existing_remarks = data.get("resolution_remarks", "") or ""
                
                # 2. Format the new string with Timestamp and Author
                timestamp = datetime.now().strftime("%d-%b-%Y %I:%M %p")
                formatted_addition = f"[{timestamp}] {author}:\n{new_remark}"
                
                # 3. Combine them safely
                if existing_remarks.strip():
                    final_remarks = existing_remarks.strip() + "\n\n" + formatted_addition
                else:
                    final_remarks = formatted_addition
                    
                # 4. Save it back using the update method we made earlier
                return self.update_document(doctype, docname, {"resolution_remarks": final_remarks})
        except Exception as e:
            from utils.logger import app_logger
            app_logger.error(f"Failed to append remark: {str(e)}")
            
        return False


    def get_staff_role(self, chat_id: str) -> str:
        """Checks if a user is an authorized staff member, returning their role."""
        import json, requests
        params = {
            "filters": json.dumps([["messenger_id", "=", str(chat_id)], ["is_active", "=", 1]]),
            "fields": '["device_role"]'
        }
        res = requests.get(f"{self.base_url}/Authorized Bot Device", headers=self.headers, params=params)
        
        if res.status_code == 200 and res.json().get("data"):
            return res.json()["data"][0].get("device_role")
        return None
