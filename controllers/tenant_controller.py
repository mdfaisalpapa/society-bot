import datetime
import json
from services.messenger import Messenger
from api.erp import ERPClient
from conversation.session import SessionManager

class TenantController:
    def __init__(self, erp_client: ERPClient, session_manager: SessionManager):
        self.erp = erp_client
        self.session = session_manager

    def validate_date(self, date_text: str) -> bool:
        """Replaces the 80-line legacy is_valid_date function."""
        try:
            datetime.datetime.strptime(date_text, "%Y-%m-%d")
            return True
        except ValueError:
            return False

    def start_wizard(self, platform: str, chat_id: str, flat_number: str):
        """Step 1: Triggered by /add_tenant"""
        self.session.update_session(chat_id, step="tenant_name", module="add_tenant", data={"flat": flat_number})
        Messenger.send(platform, chat_id, "🏠 *New Tenant Registration*\n\nStep 1 of 6\n\nPlease enter the *Tenant Name*.", force_reply=True)

    def process_wizard(self, platform: str, chat_id: str, text: str, session_data: dict):
        # ADD THIS DEBUG LINE
        
        step = session_data.get("step")
        # ... (rest of your logic)
        data = session_data.get("data", {})

        if step == "tenant_name":
            data["tenant_name"] = text.strip()
            self.session.update_session(chat_id, step="relationship", module="add_tenant", data=data)
            
            # Pass the list directly
            inline_keyboard = [
                [{"text": "🏠 Tenant", "callback_data": "/rel_Tenant"}],
                [{"text": "👷 Caretaker", "callback_data": "/rel_Caretaker"}],
                [{"text": "🏢 Company Lease", "callback_data": "/rel_Company Lease"}],
                [{"text": "🏨 Guest House", "callback_data": "/rel_Guest House"}]
            ]
            
            # Change reply_markup= to inline_keyboard=
            Messenger.send(platform, chat_id, "🏠 *New Tenant Registration*\n\nStep 2 of 6\n\nSelect Relationship:", inline_keyboard=inline_keyboard)
        elif step == "relationship":
            if text.startswith("/rel_"):
                data["relationship"] = text.replace("/rel_", "")
                self.session.update_session(chat_id, step="mobile", module="add_tenant", data=data)
                Messenger.send(platform, chat_id, "🏠 *New Tenant Registration*\n\nStep 3 of 6\n\nEnter Mobile Number.", force_reply=True)
            else:
                Messenger.send(platform, chat_id, "Please select a relationship using the buttons.")

        elif step == "mobile":
            data["mobile"] = text.strip()
            self.session.update_session(chat_id, step="email", module="add_tenant", data=data)
            Messenger.send(platform, chat_id, "🏠 *New Tenant Registration*\n\nStep 4 of 6\n\nEnter Email Address.\nIf not available, type NA.", force_reply=True)

        elif step == "email":
            data["email"] = text.strip()
            self.session.update_session(chat_id, step="start_date", module="add_tenant", data=data)
            Messenger.send(platform, chat_id, "🏠 *New Tenant Registration*\n\nStep 5 of 6\n\nEnter Tenancy Start Date.\nExample: YYYY-MM-DD", force_reply=True)

        elif step == "start_date":
            if not self.validate_date(text.strip()):
                Messenger.send(platform, chat_id, "❌ Invalid date. Format must be YYYY-MM-DD\nExample: 2026-07-01", force_reply=True)
                return
                
            data["start_date"] = text.strip()
            self.session.update_session(chat_id, step="end_date", module="add_tenant", data=data)
            Messenger.send(platform, chat_id, "🏠 *New Tenant Registration*\n\nStep 6 of 6\n\nEnter Tenancy End Date.\nFormat: YYYY-MM-DD\nIf not decided, type NA.", force_reply=True)

        elif step == "end_date":
            end_date = text.strip().upper()
            if end_date != "NA":
                if not self.validate_date(end_date):
                    Messenger.send(platform, chat_id, "❌ Invalid date. Format must be YYYY-MM-DD or NA.", force_reply=True)
                    return
                if end_date < data["start_date"]:
                    Messenger.send(platform, chat_id, f"❌ End Date cannot be earlier than Start Date ({data['start_date']}).", force_reply=True)
                    return

            data["end_date"] = end_date
            self.session.update_session(chat_id, step="confirm", module="add_tenant", data=data)
            self.show_confirmation(platform, chat_id, data)

    def show_confirmation(self, platform: str, chat_id: str, data: dict):
        summary = (
            "🏠 *New Tenant Registration*\n\n"
            "Please verify the details:\n\n"
            f"👤 Name : {data.get('tenant_name')}\n"
            f"👥 Relationship : {data.get('relationship')}\n"
            f"📱 Mobile : {data.get('mobile')}\n"
            f"📧 Email : {data.get('email')}\n"
            f"📅 Start Date : {data.get('start_date')}\n"
            f"📅 End Date : {data.get('end_date')}"
        )
        # Pass the list directly
        inline_keyboard = [
            [{"text": "✅ Confirm", "callback_data": "/confirm_tenant"}],
            [{"text": "❌ Cancel", "callback_data": "/cancel"}]
        ]
        
        # Change reply_markup= to inline_keyboard=
        Messenger.send(platform, chat_id, summary, inline_keyboard=inline_keyboard)

    def confirm_tenant(self, platform: str, chat_id: str, session_data: dict):
        data = session_data.get("data", {})
        flat_number = data.get("flat")
        
        success = self.erp.create_active_tenant(flat_number, data)
        self.session.clear_session(chat_id)
        
        if success:
            Messenger.send(platform, chat_id, "✅ Tenant added successfully! The tenant can now use the bot and type `/register` to verify their identity.")
        else:
            Messenger.send(platform, chat_id, "❌ Failed to create tenant in ERPNext. Please try again.")

    def show_management_menu(self, platform: str, chat_id: str, profile):
        """Displays the main /tenant dashboard."""
        if profile.is_rented:
            reply = (
                "🏠 *Tenant Management*\n\n"
                f"👤 *Active Tenant:* {profile.tenant_name}\n"
                f"📱 *Phone:* {profile.tenant_phone or 'N/A'}\n"
                f"✉️ *Email:* {profile.tenant_email or 'N/A'}"
            )
            inline_keyboard = [
                [{"text": "❌ Deactivate Tenant", "callback_data": "/deactivate_tenant"}]
                # Note: Edit, Documents, and Replace buttons can be added back here later
            ]
        else:
            reply = "🏠 *Tenant Management*\n\nNo active tenant found."
            inline_keyboard = [
                [{"text": "➕ Add Tenant", "callback_data": "/add_tenant"}]
            ]
            
        Messenger.send(platform, chat_id, reply, inline_keyboard=inline_keyboard)

    def confirm_deactivation(self, platform: str, chat_id: str):
        """Shows the warning prompt before deleting access."""
        reply = "⚠️ *Warning*\n\nAre you sure you want to deactivate the current tenant? They will lose access to the bot immediately."
        inline_keyboard = [
            [{"text": "✅ Yes, Deactivate", "callback_data": "/confirm_deactivate_tenant"}],
            [{"text": "🔙 Cancel", "callback_data": "/tenant"}]
        ]
        Messenger.send(platform, chat_id, reply, inline_keyboard=inline_keyboard)

    def process_deactivation(self, platform: str, chat_id: str, flat_number: str):
        """Triggers the ERP action and resets the dashboard."""
        success = self.erp.deactivate_tenant(flat_number)
        
        if success:
            Messenger.send(platform, chat_id, "✅ Tenant successfully deactivated. The flat is now marked as self-occupied.")
            
            # Immediately show the empty dashboard to visually confirm the change
            inline_keyboard = [[{"text": "➕ Add Tenant", "callback_data": "/add_tenant"}]]
            Messenger.send(platform, chat_id, "🏠 *Tenant Management*\n\nNo active tenant found.", inline_keyboard=inline_keyboard)
        else:
            Messenger.send(platform, chat_id, "❌ Failed to deactivate tenant. Please contact administration.")