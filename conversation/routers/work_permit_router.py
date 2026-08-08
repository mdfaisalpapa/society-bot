class WorkPermitRouter:
    def __init__(self, work_permit_ctrl, session_manager):
        self.wp_ctrl = work_permit_ctrl
        self.session = session_manager

    def handle(self, platform, chat_id, text, message, current_session, active_profile):
        
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
            
        # ? NEW: Catch the specific violation button click
        if text.startswith("/my_viol_"):
            violation_id = text.replace("/my_viol_", "")
            self.wp_ctrl.view_violation_details(platform, chat_id, violation_id)
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