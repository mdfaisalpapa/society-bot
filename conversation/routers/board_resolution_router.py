class BoardResolutionRouter:
    def __init__(self, controller):
        self.controller = controller

    def handle(self, platform, chat_id, text, message, current_session, active_profile):
        if not text:
            return False
            
        if not getattr(active_profile, 'is_aoa_member', False):
            if text.startswith(("/aoa_resolutions", "/aoa_res_view_", "/aoa_res_sign_", "/aoa_res_create", "/aoa_res_draft", "/aoa_res_queue_", "/aoa_res_edit", "/aoa_res_del", "/aoa_res_withdraw")):
                from services.messenger import Messenger
                Messenger.send(platform, chat_id, "❌ Unauthorized. You do not have AOA Committee privileges.")
                return True
            return False

        # 1. Handle Active Wizard Sessions
        if current_session and current_session.get("module") == "board_resolution":
            step = current_session.get("step")
            
            # 👇 Added "decline_reason" to the intercepted steps
            if step in ["title", "text", "confirm", "editing_draft", "decline_reason"]:
                if text == "/aoa_resolutions":
                    self.controller.session.clear_session(chat_id)
                    self.controller.show_resolution_hub(platform, chat_id)
                    return True
                    
                # Clear session gracefully if they cancel a prompt
                if text.startswith(("/aoa_res_edit_", "/aoa_res_draft_view_", "/aoa_res_view_")):
                    self.controller.session.clear_session(chat_id)
                else:
                    self.controller.process_wizard(platform, chat_id, text, current_session, active_profile)
                    return True

        # 2. Handle Base Commands
        if text == "/aoa_res_create":
            self.controller.start_creation_wizard(platform, chat_id)
            return True

        if text == "/aoa_resolutions":
            self.controller.show_resolution_hub(platform, chat_id)
            return True

        if text.startswith("/aoa_res_queue_"):
            queue = text.replace("/aoa_res_queue_", "")
            self.controller.list_resolution_queue(platform, chat_id, active_profile, queue)
            return True

        if text.startswith("/aoa_res_withdraw_"):
            resolution_id = text.replace("/aoa_res_withdraw_", "")
            self.controller.withdraw_resolution(platform, chat_id, resolution_id, active_profile)
            return True

        if text == "/aoa_res_drafts":
            self.controller.list_draft_resolutions(platform, chat_id, active_profile)
            return True
            
        if text.startswith("/aoa_res_draft_view_"):
            resolution_id = text.replace("/aoa_res_draft_view_", "")
            self.controller.view_draft_resolution(platform, chat_id, resolution_id)
            return True
            
        if text.startswith("/aoa_res_edit_"):
            resolution_id = text.replace("/aoa_res_edit_", "")
            self.controller.show_edit_options(platform, chat_id, resolution_id)
            return True
            
        if text.startswith("/aoa_res_edittitle_"):
            resolution_id = text.replace("/aoa_res_edittitle_", "")
            self.controller.prompt_edit_draft(platform, chat_id, resolution_id, "resolution_title")
            return True
            
        if text.startswith("/aoa_res_edittext_"):
            resolution_id = text.replace("/aoa_res_edittext_", "")
            self.controller.prompt_edit_draft(platform, chat_id, resolution_id, "resolution_text")
            return True
            
        if text.startswith("/aoa_res_delconf_"):
            resolution_id = text.replace("/aoa_res_delconf_", "")
            self.controller.confirm_delete_draft(platform, chat_id, resolution_id)
            return True

        if text.startswith("/aoa_res_delete_"):
            resolution_id = text.replace("/aoa_res_delete_", "")
            self.controller.delete_draft(platform, chat_id, resolution_id, active_profile)
            return True
            
        if text.startswith("/aoa_res_circulate_"):
            resolution_id = text.replace("/aoa_res_circulate_", "")
            self.controller.circulate_resolution(platform, chat_id, resolution_id, active_profile)
            return True
            
        if text.startswith("/aoa_res_view_"):
            resolution_id = text.replace("/aoa_res_view_", "")
            self.controller.view_board_resolution(platform, chat_id, resolution_id, active_profile)
            return True
            
        # 👇 NEW: Approve & Decline Routing
        if text.startswith("/aoa_res_approve_"):
            resolution_id = text.replace("/aoa_res_approve_", "")
            self.controller.submit_resolution_response(platform, chat_id, resolution_id, "Signed", active_profile)
            return True

        if text.startswith("/aoa_res_decline_"):
            resolution_id = text.replace("/aoa_res_decline_", "")
            self.controller.prompt_decline_reason(platform, chat_id, resolution_id)
            return True
                
        return False
