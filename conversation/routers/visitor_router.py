class VisitorRouter:
    def __init__(self, visitor_controller, session_manager):
        self.controller = visitor_controller
        self.session = session_manager

    def handle(self, platform, chat_id, text, contact_data, current_session, active_profile):
        
        # Commands
        if text.startswith("/visitors") or text == "/history":
            offset = int(text.split("_")[1]) if "_" in text else 0
            self.controller.view_history(platform, chat_id, active_profile.flat_number, offset)
            return True
            
        # 👇 CHANGED: Only intercept Today and Tomorrow for the fast path 👇
        if text in ["/vdate_today", "/vdate_tomorrow"]:
            if not active_profile:
                Messenger.send(platform, chat_id, "❌ Profile not found.")
                return True
                
            selected_date = text.split("_")[1] # gets 'today' or 'tomorrow'
            self.controller.process_date_selection(platform, chat_id, selected_date, active_profile.flat_number)
            return True
        if text == "/invite":
            self.controller.start_invite(platform, chat_id, active_profile.flat_number)
            return True
            
        if text == "/vquick_del":
            self.session.update_session(chat_id, module="visitor", step="awaiting_name", data={"flat": active_profile.flat_number})
            self.controller.handle_wizard_reply(platform, chat_id, "/vquick_del", {"flat": active_profile.flat_number}, "awaiting_name")
            return True
            
        if text.startswith("/vfreq_"):
            visitor_name = text.replace("/vfreq_", "").replace("_", " ")
            self.session.update_session(chat_id, module="visitor", step="awaiting_name", data={"flat": active_profile.flat_number, "visitor_name": visitor_name})
            self.controller.handle_wizard_reply(platform, chat_id, text, {"flat": active_profile.flat_number, "visitor_name": visitor_name}, "awaiting_name")
            return True

        # Session Wizard Handlers
        if current_session and current_session.get("module") == "visitor":
            if not text.startswith("/") or text.startswith("/v") or contact_data:
                self.controller.handle_wizard_reply(platform, chat_id, text, current_session.get("data"), current_session.get("step"), contact_data)
                return True

        return False