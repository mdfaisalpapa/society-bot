from utils.logger import app_logger

class AdminRouter:
    def __init__(self, admin_controller):
        self.controller = admin_controller

    def handle(self, platform, chat_id, text, message, current_session, active_profile):
        role = getattr(active_profile, 'role', '')
        
        # ? FIX: Added .base_client right after .erp
        #staff_role = self.controller.erp.base_client.get_staff_role(chat_id)
        # ✅ FIX: Call the method directly on the ERPClient
        staff_role = self.controller.erp.get_staff_role(chat_id)
        
        if role not in ["Office Admin", "Estate Manager", "Doc Verifier"] and staff_role not in ["Office Admin", "Estate Manager", "Doc Verifier"]:
            return False
            
        # ... rest of your admin routing ...
            
        # ... rest of your admin routing ...
        # ? NEW: Document Verification Routing
        if text.startswith("/doc_act_"):
            parts = text.replace("/doc_act_", "").split("_")
            action = parts[0]
            flat_number = parts[1]
            self.controller.process_doc_verification(platform, chat_id, action, flat_number)
            return True
            
        # ? ADD THIS: Route for Admin viewing the uploaded deed
        # ? CHANGED: Changed from /v_tdoc_ to /adm_seefile_
        if text.startswith("/adm_seefile_"):
            file_name = text.replace("/adm_seefile_", "")
            self.controller.view_uploaded_document(platform, chat_id, file_name)
            return True
        # ==========================================
        # ? WORK PERMIT ROUTING
        # ==========================================
        # ==========================================
        # ? WORK PERMIT ROUTING
        # ==========================================
        
        # ? NEW: Handle the Admin Violations Menu
        if text == "/admin_violations":
            self.controller.list_violations(platform, chat_id)
            return True
        if text == "/admin_wp":
            self.controller.show_wp_status_filters(platform, chat_id)
            return True
            
        # List Permits for Status
        if text.startswith("/adm_wpsel_"):
            status = text.replace("/adm_wpsel_", "")
            self.controller.list_wp_by_status(platform, chat_id, status)
            return True

        # View specific permit
        if text.startswith("/adm_wpview_"):
            permit_id = text.replace("/adm_wpview_", "")
            self.controller.view_permit_details(platform, chat_id, permit_id)
            return True
            
        # ... (Inside handle method)

        # Execute Approve or Reject action -> Now prompts for remark
        if text.startswith("/adm_wpact_"):
            clean_text = text.replace("/adm_wpact_", "")
            permit_id, status = clean_text.rsplit("_", 1)
            self.controller.prompt_permit_remark(platform, chat_id, permit_id, status)
            return True

        # Handle Typed Remarks for Work Permits
        if current_session.get("module") == "admin" and current_session.get("step") == "awaiting_permit_remark":
            if text and not text.startswith("/"):
                self.controller.save_permit_remark(platform, chat_id, text, active_profile)
                return True

        # ? NEW: Catch the Verifier Menu Clicks
        if text == "/v_queue_owners":
            # This is where you will call the method to list pending owners
            self.controller.list_pending_owners(platform, chat_id)
            return True
            
        if text == "/v_queue_tenants":
            # self.controller.list_pending_tenants(platform, chat_id)
            Messenger.send(platform, chat_id, "? Tenant Verification Queue is empty or under construction.")
            return True
            
        if text == "/v_queue_pets":
            Messenger.send(platform, chat_id, "? Pet Verification module is coming soon!")
            return True
        # ==========================================
        # 🎫 MAINTENANCE TICKET ROUTING
        # ==========================================
        # Step 1 - Open Status Filters
        if text == "/admin_tickets":
            self.controller.show_ticket_status_filters(platform, chat_id)
            return True
        # 👇 NEW: Intercept PDF Download Request
        if text == "/adm_tkt_pdf":
            self.controller.download_open_tickets_report(platform, chat_id)
            return True
            
        # Step 2 - Open Category Filters (Extracts the selected status)
        if text.startswith("/adm_tstat_"):
            status = text.replace("/adm_tstat_", "")
            self.controller.show_ticket_category_filters(platform, chat_id, status)
            return True
            
        # Step 3 - List Tickets (Extracts both Status and Category)
        if text.startswith("/adm_tcat_"):
            clean_text = text.replace("/adm_tcat_", "")
            status, category = clean_text.split("_", 1) 
            self.controller.list_tickets(platform, chat_id, status, category)
            return True
            
        # Handle Status Change Prompt
        if text.startswith("/admin_stat_"):
            ticket_id = text.replace("/admin_stat_", "")
            self.controller.prompt_status_update(platform, chat_id, ticket_id)
            return True
            
        # Execute Status Change
        if text.startswith("/admin_set_"):
            parts = text.split("_")
            ticket_id, status = parts[2], parts[3]
            self.controller.set_ticket_status(platform, chat_id, ticket_id, status)
            return True
            
        # Handle Remarks Prompt
        if text.startswith("/admin_rem_"):
            ticket_id = text.replace("/admin_rem_", "")
            self.controller.prompt_remark(platform, chat_id, ticket_id)
            return True
            
        # Handle Typed Remarks to pass active_profile
        if current_session.get("module") == "admin" and current_session.get("step") == "awaiting_remark":
            if text and not text.startswith("/"):
                self.controller.save_remark(platform, chat_id, text, active_profile)
                return True
                
        return False
