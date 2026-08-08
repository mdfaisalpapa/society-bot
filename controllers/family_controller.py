from services.messenger import Messenger
from utils.keyboard import KeyboardBuilder

class FamilyController:
    def __init__(self, erp_client, session_manager):
        self.erp = erp_client
        self.session = session_manager

    def show_family_menu(self, platform: str, chat_id: str, flat_number: str, can_manage: bool):
        """Displays ACTIVE family members."""
        members = self.erp.get_family_members(flat_number, status="Active")
        
        msg = "👨‍👩‍👧‍👦 *Active Family Members*\n\n"
        if not members:
            msg += "No active family members found."
        else:
            for m in members:
                msg += f"👤 *{m.get('member_name')}* ({m.get('relation')})\n📱 {m.get('mobile_no')}\n\n"
                
        Messenger.send(platform, chat_id, msg, inline_keyboard=KeyboardBuilder.family_active_menu(members, can_manage))

    def show_inactive_family_menu(self, platform: str, chat_id: str, flat_number: str, can_manage: bool):
        """Displays INACTIVE family members."""
        members = self.erp.get_family_members(flat_number, status="Inactive")
        
        msg = "🗄️ *Inactive Family Members*\n\n"
        if not members:
            msg += "No inactive members found."
        else:
            for m in members:
                msg += f"👤 *{m.get('member_name')}* ({m.get('relation')})\n📱 {m.get('mobile_no')}\n\n"
                
        Messenger.send(platform, chat_id, msg, inline_keyboard=KeyboardBuilder.family_inactive_menu(members, can_manage))

    def activate_member(self, platform: str, chat_id: str, member_id: str, flat_number: str):
        success = self.erp.activate_family_member(member_id)
        if success:
            Messenger.send(platform, chat_id, "✅ Family member reactivated successfully.")
        else:
            Messenger.send(platform, chat_id, "❌ Failed to reactivate. Please try again.")
        self.show_inactive_family_menu(platform, chat_id, flat_number, True)
        
    def deactivate_member(self, platform: str, chat_id: str, member_id: str, flat_number: str):
        success = self.erp.deactivate_family_member(member_id)
        if success:
            Messenger.send(platform, chat_id, "✅ Family member deactivated.")
        else:
            Messenger.send(platform, chat_id, "❌ Failed to deactivate. Please try again.")
        self.show_family_menu(platform, chat_id, flat_number, True)

    # ==========================================
    # ➕ ADD FAMILY MEMBER WIZARD
    # ==========================================

    def start_add_member(self, platform: str, chat_id: str):
        """Step 1: Starts the wizard to add a new family member."""
        # Initialize the session to wait for the name
        self.session.update_session(chat_id, module="family", step="awaiting_name", data={})
        
        Messenger.send(
            platform, 
            chat_id, 
            "➕ Let's add a new family member.\n\nPlease enter their *Full Name*:", 
            inline_keyboard=KeyboardBuilder.cancel_operation()
        )

    def set_relation(self, platform: str, chat_id: str, relation: str, session_data: dict):
        """Step 3: Handles the inline button click from the dynamic relationship menu."""
        session_data["relation"] = relation
        self.session.update_session(chat_id, module="family", step="awaiting_phone", data=session_data)
        
        name = session_data.get("member_name", "this member")
        Messenger.send(
            platform,
            chat_id,
            f"Got it. What is the *10-digit mobile number* for {name}?\n\n(Type 'Skip' if they don't have a phone)",
            inline_keyboard=KeyboardBuilder.cancel_operation()
        )

    def handle_wizard_reply(self, platform: str, chat_id: str, text: str, session_data: dict, step: str, flat_number: str):
        """Handles text replies (Name and Phone) during the add family wizard."""
        
        if step == "awaiting_name":
            # Step 2: Save name and ask for relationship using our Dynamic API Keyboard
            session_data["member_name"] = text
            self.session.update_session(chat_id, module="family", step="awaiting_relation", data=session_data)
            
            Messenger.send(
                platform,
                chat_id,
                f"Great. What is the relationship of *{text}* to you?",
                inline_keyboard=KeyboardBuilder.family_relations() 
            )

        elif step == "awaiting_phone":
            # 1. Clean the input
            phone_input = text.strip().replace(" ", "").replace("-", "")
            
            # 2. Basic Length Validation
            if phone_input.lower() != "skip" and len(phone_input) < 10:
                Messenger.send(platform, chat_id, "❌ That number is too short. Please provide a valid 10-digit mobile number, or type 'Skip'.")
                return # Stop here and don't call the API
            
            # 3. Formatting for API
            if phone_input.lower() == "skip":
                phone = ""
            else:
                phone = f"+91-{phone_input}"
            
            # ... (continue with the rest of the saving logic)
                    
            name = session_data.get("member_name")
            relation = session_data.get("relation")
            
            # Send processing message
            Messenger.send(platform, chat_id, "⏳ Saving family member...")
            
            # Add to ERPNext using individual positional/keyword arguments
            success = self.erp.add_family_member(
                flat_number=flat_number,
                name=name,
                relation=relation,
                mobile_no=phone
            )
            
            # Clear the session
            self.session.clear_session(chat_id)
            
            if success:
                Messenger.send(platform, chat_id, f"✅ *{name}* has been successfully added to your family.")
                self.show_family_menu(platform, chat_id, flat_number, True)
            else:
                Messenger.send(platform, chat_id, "❌ Failed to add family member. Please contact the admin.", inline_keyboard=KeyboardBuilder.back_to_menu())