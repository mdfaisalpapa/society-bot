class WorkPermitRouter:
    def __init__(self, work_permit_ctrl, session_manager):
        self.wp_ctrl = work_permit_ctrl
        self.session = session_manager

    def handle(self, platform, chat_id, text, message, current_session, active_profile):
        
        # ? GLOBAL GATEKEEPER: Block non-owners from Work Permit commands
        wp_commands = ("/work_permit", "/apply_permit", "/manage_workers", "/report_violation", "/my_violations", "/my_viol_", "/addworker_", "/confirm_permit")
        
        if text and str(text).startswith(wp_commands):
            if getattr(active_profile, 'role', '') != "Owner":
                from services.messenger import Messenger
                Messenger.send(platform, chat_id, "? *Access Denied*\n\nOnly Flat Owners can manage Work Permits.")
                return True # Stop processing instantly

        # ... (Your existing routing logic continues below) ...    
        # 1. Direct Commands / Menu Button Clicks
        if text == "/work_permit":
            # Safety check just in case
            if not active_profile: return False 
            self.wp_ctrl.show_main_menu(platform, chat_id, active_profile.flat_number, active_profile)
            return True
            
        if text == "/apply_permit":
            self.wp_ctrl.start_wizard(platform, chat_id, active_profile.flat_number, active_profile)
            return True
            
        if text == "/manage_workers":
            self.wp_ctrl.show_active_permits(platform, chat_id, active_profile.flat_number)
            return True
            
        if text == "/report_violation":
            self.wp_ctrl.start_violation_report(platform, chat_id, active_profile.flat_number)
            return True
            
        if text == "/my_violations":
            self.wp_ctrl.show_my_violations(platform, chat_id, active_profile.flat_number)
            return True
        if text == "/my_permits":
            self.wp_ctrl.show_my_permits(platform, chat_id, active_profile.flat_number)
            return True

        # Add these alongside your other direct commands
        
        if text and text.startswith("/aoa_wp_list_"):
            status = text.replace("/aoa_wp_list_", "")
            self.wp_ctrl.aoa_show_permits_list(platform, chat_id, status)
            return True
            
        if text and text.startswith("/aoa_wpview_"):
            permit_id = text.replace("/aoa_wpview_", "")
            self.wp_ctrl.aoa_view_permit(platform, chat_id, permit_id)
            return True
            
        if text and text.startswith("/aoa_wpact_"):
            parts = text.replace("/aoa_wpact_", "").split("_")
            if len(parts) == 2:
                permit_id, status = parts[0], parts[1]
                self.wp_ctrl.aoa_update_permit(platform, chat_id, permit_id, status)
            return True
            
        # ? NEW: Catch the specific violation button click
        if text.startswith("/my_viol_"):
            violation_id = text.replace("/my_viol_", "")
            self.wp_ctrl.view_violation_details(platform, chat_id, violation_id)
            return True
        
        if text.startswith("/wp_view_"):
            permit_id = text.replace("/wp_view_", "")
            self.wp_ctrl.view_permit_details(platform, chat_id, permit_id)
            return True
            
        # 2. Wizard Session Handling
        if current_session and current_session.get("module") == "report_violation":
            # 👇 FIXED: Changed resident_controller to wp_ctrl
            self.wp_ctrl.process_violation_wizard(platform, chat_id, text, current_session, message)
            return True

        if str(text).startswith("/addworker_"):
            permit_id = text.replace("/addworker_", "")
            self.wp_ctrl.start_worker_pass_wizard(platform, chat_id, permit_id)
            return True
            
        if text == "/confirm_permit":
            self.wp_ctrl.submit_permit(platform, chat_id, current_session)
            return True

        # 3. Active Wizard Sessions (Text & Photo Inputs)
        module = current_session.get("module")
        
        if module == "work_permit":
            self.wp_ctrl.process_wizard(platform, chat_id, text, current_session)
            return True
            
        if module == "add_worker":
            # We pass the raw 'message' here so the controller can extract the uploaded photo
            self.wp_ctrl.process_worker_wizard(platform, chat_id, text, current_session, message)
            return True

        # Return False if this router didn't handle the request
        return False