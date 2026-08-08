from services.messenger import Messenger

class StaffRouter:
    def __init__(self, staff_controller):
        self.controller = staff_controller

    def handle(self, platform, chat_id, text, message, current_session, active_profile):
        from utils.logger import app_logger
        
        app_logger.info(f"DEBUG SESSION DUMP: {current_session}")
        
        # 👇 FIX 1: Read the state from the 'module' key, because that's where it saved!
        state = current_session.get("module") 
        
        # 👇 FIX 2: Read the staff_id from inside the 'data' dictionary!
        staff_id = current_session.get("data", {}).get("target_staff_id")
        
        # 2. Catch the Rating State
        if state == "WAITING_FOR_STAFF_RATING":
            if not staff_id:
                Messenger.send(platform, chat_id, "⚠️ Session expired. Please click the Rate button again.")
                self.controller.session.update_session(chat_id, "staff", "", {})
                return True
                
            self.controller.process_staff_rating(platform, chat_id, active_profile.flat_number, staff_id, text)
            return True
            
        # 3. Catch the Complaint State
        if state == "WAITING_FOR_STAFF_COMPLAINT":
            if not staff_id:
                Messenger.send(platform, chat_id, "⚠️ Session expired. Please click the Complain button again.")
                self.controller.session.update_session(chat_id, "staff", "", {})
                return True
                
            self.controller.process_staff_complaint(platform, chat_id, active_profile.flat_number, staff_id, text)
            return True
            
        # ... (keep the rest of your button logic below)
            
        # ... (keep the rest of your button click logic below here) ...                
            self.controller.process_staff_complaint(platform, chat_id, active_profile.flat_number, staff_id, text)
            return True
        # 1. Main Staff Menu
        if text == "/staff":
            if not active_profile:
                Messenger.send(platform, chat_id, "❌ Profile not found.")
            else:
                self.controller.show_staff_menu(platform, chat_id, active_profile.flat_number)
            return True

        # 👇 2. NEW: Show Categories to Add Staff
        if text == "/st_add":
            if not active_profile: Messenger.send(platform, chat_id, "❌ Unauthorized.")
            else: self.controller.show_staff_categories(platform, chat_id)
            return True

        # 👇 3. NEW: Show Staff in a specific Category
        if text.startswith("/st_cat_"):
            if not active_profile: Messenger.send(platform, chat_id, "❌ Unauthorized.")
            else: 
                category = text.split("_")[2]
                self.controller.show_staff_by_category(platform, chat_id, category)
            return True
            
        # 👇 4. NEW: Process the Linkage
        if text.startswith("/st_link_"):
            if not active_profile: Messenger.send(platform, chat_id, "❌ Unauthorized.")
            else:
                staff_id = text.split("/st_link_")[1]
                self.controller.process_link_staff(platform, chat_id, active_profile.flat_number, staff_id)
            return True

        # 5. Generate Daily Gate Pass
        if text.startswith("/stpass_"):
            if not active_profile:
                Messenger.send(platform, chat_id, "❌ Unauthorized.")
                return True
                
            parts = text.split("_")
            staff_id = parts[1]
            staff_name = parts[2]
            role = parts[3] if len(parts) > 3 else "Staff"
            
            self.controller.generate_pass(platform, chat_id, active_profile.flat_number, staff_id, staff_name, role)
            return True
        # 👇 NEW: Catch the Unlink button
        if text.startswith("/st_unlink_"):
            if not active_profile: 
                Messenger.send(platform, chat_id, "❌ Unauthorized.")
            else:
                staff_id = text.split("/st_unlink_")[1]
                self.controller.process_unlink_staff(platform, chat_id, active_profile.flat_number, staff_id)
            return True
        # 👇 Catch the "View Details" button
        if text.startswith("/st_view_"):
            if not active_profile:
                Messenger.send(platform, chat_id, "❌ Unauthorized.")
            else:
                staff_id = text.split("/st_view_")[1]
                self.controller.show_staff_details(platform, chat_id, staff_id)
            return True
        # 👇 Catch the "Rate" and "Complain" button clicks 👇
        if text.startswith("/st_rate_"):
            if not active_profile: 
                Messenger.send(platform, chat_id, "❌ Unauthorized.")
            else:
                staff_id = text.split("/st_rate_")[1]
                self.controller.prompt_staff_rating(platform, chat_id, staff_id)
            return True
            
        if text.startswith("/st_comp_"):
            if not active_profile: 
                Messenger.send(platform, chat_id, "❌ Unauthorized.")
            else:
                staff_id = text.split("/st_comp_")[1]
                self.controller.prompt_staff_complaint(platform, chat_id, staff_id)
            return True

        return False