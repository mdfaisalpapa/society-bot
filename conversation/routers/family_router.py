from services.messenger import Messenger
from utils.logger import app_logger

class FamilyRouter:
    def __init__(self, family_ctrl):
        self.controller = family_ctrl

    def handle(self, platform, chat_id, text, message, current_session, active_profile):
        
        # 👇 1. THE BOUNCER: Ignore Staff Profiles immediately
        role = getattr(active_profile, 'role', '')
        if role in ["Office Admin", "Estate Manager", "Security Guard"]:
            return False

        # 👇 2. THE SAFE FETCH: Use getattr so it never crashes if a field is missing
        primary_ids = str(getattr(active_profile, 'active_chat_id', ''))
        can_manage = str(chat_id) in primary_ids
        flat_number = getattr(active_profile, 'flat_number', '')
        
        # ==========================================
        # 🔄 DYNAMIC WIZARD ROUTING (Takes Priority)
        # ==========================================
        module = current_session.get("module")
        if module == "family":
            step = current_session.get("step")
            session_data = current_session.get("data", {})
            
            # Route text inputs for Name and Phone to the unified handler
            if step in ["awaiting_name", "awaiting_phone"] and text and not text.startswith("/"):
                self.controller.handle_wizard_reply(platform, chat_id, text, session_data, step, flat_number)
                return True
                
            # Route dynamic relation button clicks
            if step == "awaiting_relation" and text.startswith("/fam_rel_"):
                relation = text.replace("/fam_rel_", "")
                self.controller.set_relation(platform, chat_id, relation, session_data)
                return True

        # ==========================================
        # 📌 STATIC COMMANDS & BUTTONS
        # ==========================================
        
        # 1. Main Menu Command (Active Members)
        if text == "/family":
            self.controller.show_family_menu(platform, chat_id, flat_number, can_manage)
            return True
            
        # 1b. Inactive Menu Command
        if text == "/fam_inactive":
            self.controller.show_inactive_family_menu(platform, chat_id, flat_number, can_manage)
            return True

        # 2. Add Button Clicked
        if text == "/fam_add":
            if not can_manage:
                Messenger.send(platform, chat_id, "❌ Only the Primary Resident can add Family Members.")
                return True
            self.controller.start_add_member(platform, chat_id)
            return True
            
        # 3. Remove/Deactivate Button Clicked
        if text.startswith("/fam_del_"):
            if not can_manage:
                Messenger.send(platform, chat_id, "❌ Only the Primary Resident can manage Family Members.")
                return True
            member_id = text.replace("/fam_del_", "")
            self.controller.deactivate_member(platform, chat_id, member_id, flat_number)
            return True
            
        # 4. Reactivate Button Clicked
        if text.startswith("/fam_react_"):
            if not can_manage:
                Messenger.send(platform, chat_id, "❌ Only the Primary Resident can manage Family Members.")
                return True
            member_id = text.replace("/fam_react_", "")
            self.controller.activate_member(platform, chat_id, member_id, flat_number)
            return True

        return False