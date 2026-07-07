from services.messenger import Messenger
from conversation.session import SessionManager
from api.erp import ERPClient

class VisitorController:
    def __init__(self):
        self.erp = ERPClient()
        self.session = SessionManager()

    # --- INVITATION WIZARD ---

    def start_invite(self, platform: str, chat_id: str, resident_flat: str):
        """Step 1: Ask for the visitor's name."""
        self.session.update_session(
            chat_id, 
            step="awaiting_name", 
            module="visitor", 
            data={"flat": resident_flat}
        )
        
        Messenger.send(
            platform, 
            chat_id, 
            "✉️ *Invite a Visitor*\n\nPlease enter the full name of your visitor:", 
            force_reply=True
        )

    def handle_wizard_reply(self, platform: str, chat_id: str, text: str, session_data: dict, current_step: str):
        """Routes the user's text based on their current step in the wizard."""
        
        if current_step == "awaiting_name":
            # Save the name and ask for the date using an inline keyboard
            session_data["visitor_name"] = text.strip()
            self.session.update_session(chat_id, step="awaiting_date", module="visitor", data=session_data)
            
            grid = [
                [{"text": "📅 Today", "callback_data": "/vdate_today"}],
                [{"text": "📆 Tomorrow", "callback_data": "/vdate_tomorrow"}]
            ]
            Messenger.send(platform, chat_id, f"When is *{session_data['visitor_name']}* expected to arrive?", grid=grid)

    def process_date_selection(self, platform: str, chat_id: str, selection: str):
        """Step 3: Finalize creation after they click Today or Tomorrow."""
        session_info = self.session.get_session(chat_id)
        if not session_info or session_info.get("module") != "visitor":
            Messenger.send(platform, chat_id, "❌ Session expired. Please type /invite to start again.")
            return
            
        session_data = session_info.get("data", {})
        visitor_name = session_data.get("visitor_name")
        resident_flat = session_data.get("flat")
        
        # Call ERPNext
        result = self.erp.create_preapproved_visitor(resident_flat, visitor_name, selection)
        
        if result.get("success"):
            passcode = result.get("passcode")
            msg = (f"✅ *Visitor Pre-Approved!*\n\n"
                   f"👤 *Name:* {visitor_name}\n"
                   f"📅 *Date:* {selection.title()}\n\n"
                   f"Share this Gate Passcode with your guest:\n👉 `{passcode}`")
            Messenger.send(platform, chat_id, msg)
            self.session.clear_session(chat_id)
        else:
            Messenger.send(platform, chat_id, "❌ Failed to create gate pass. Please try again.")
            self.session.clear_session(chat_id)

    # --- HISTORY MODULE ---

    def view_history(self, platform: str, chat_id: str, resident_flat: str, offset: int = 0):
        """Displays visitor history with pagination."""
        logs = self.erp.get_visitor_history(resident_flat, offset)
        
        reply = f"📋 *Visitor History (Week -{offset})*\n\n"
        if not logs:
            reply += "No visitors found for this period."
        else:
            for log in logs:
                # Format: 🔹 John Doe (Walk-in) - Approved
                reply += f"🔹 *{log['visitor_name']}* ({log['entry_type']}) - {log['status']}\n"
                
        # Pagination Buttons
        btns = [{"text": "⬅️ Older", "callback_data": f"/visitors_{offset + 1}"}]
        if offset > 0: 
            btns.append({"text": "Newer ➡️", "callback_data": f"/visitors_{offset - 1}" if offset > 1 else "/visitors"})
            
        Messenger.send(platform, chat_id, reply, grid=[btns])