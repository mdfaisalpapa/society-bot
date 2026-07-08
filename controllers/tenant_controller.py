import datetime
import json
from services.messenger import Messenger
from api.erp import ERPClient
from conversation.session import SessionManager

def safe_md(text):
    """Escapes underscores to prevent Telegram Markdown crashes."""
    return str(text).replace("_", "\\_").replace("*", "\\*") if text else "N/A"

class TenantController:
    def __init__(self, erp_client: ERPClient, session_manager: SessionManager):
        self.erp = erp_client
        self.session = session_manager

    def validate_date(self, date_text: str) -> bool:
        try:
            datetime.datetime.strptime(date_text, "%Y-%m-%d")
            return True
        except ValueError:
            return False

    def start_wizard(self, platform: str, chat_id: str, flat_number: str):
        self.session.update_session(chat_id, step="tenant_name", module="add_tenant", data={"flat": flat_number})
        Messenger.send(platform, chat_id, "🏠 *New Tenant Registration*\n\nStep 1 of 6\n\nPlease enter the *Tenant Name*.", force_reply=True)

    def process_wizard(self, platform: str, chat_id: str, text: str, session_data: dict):
        step = session_data.get("step")
        data = session_data.get("data", {})

        if step == "tenant_name":
            data["tenant_name"] = text.strip()
            self.session.update_session(chat_id, step="relationship", module="add_tenant", data=data)
            inline_keyboard = [
                [{"text": "🏠 Tenant", "callback_data": "/rel_Tenant"}],
                [{"text": "👷 Caretaker", "callback_data": "/rel_Caretaker"}],
                [{"text": "🏢 Company Lease", "callback_data": "/rel_Company Lease"}],
                [{"text": "🏨 Guest House", "callback_data": "/rel_Guest House"}],
                [{"text": "❌ Cancel & Exit", "callback_data": "/cancel"}]
            ]
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
            f"📧 Email : {safe_md(data.get('email'))}\n"
            f"📅 Start Date : {data.get('start_date')}\n"
            f"📅 End Date : {data.get('end_date')}"
        )
        inline_keyboard = [
            [{"text": "✅ Confirm", "callback_data": "/confirm_tenant"}],
            [{"text": "❌ Cancel", "callback_data": "/cancel"}]
        ]
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
        if profile.is_rented:
            reply = (
                "🏠 *Tenant Management*\n\n"
                f"👤 *Name:* {safe_md(profile.tenant_name)}\n"
                f"👥 *Relationship:* {safe_md(profile.tenant_relationship)}\n"
                f"📱 *Phone:* {safe_md(profile.tenant_phone)}\n"
                f"✉️ *Email:* {safe_md(profile.tenant_email)}\n"
                f"📅 *Start Date:* {safe_md(profile.tenant_start_date)}\n"
                f"📅 *End Date:* {safe_md(profile.tenant_end_date)}\n"
                f"🔒 *Status:* {safe_md(profile.tenant_status)}"
            )
            inline_keyboard = [
                [{"text": "📱 Edit Phone", "callback_data": "/edit_tenant_phone"}, {"text": "✉️ Edit Email", "callback_data": "/edit_tenant_email"}],
                [{"text": "📅 Extend Tenancy", "callback_data": "/extend_tenant"}],
                [{"text": "📜 Previous Tenants", "callback_data": "/previous_tenants"}],
                [{"text": "❌ Deactivate Tenant", "callback_data": "/deactivate_tenant"}]
            ]
        else:
            reply = "🏠 *Tenant Management*\n\nNo active tenant found."
            inline_keyboard = [
                [{"text": "➕ Add New Tenant", "callback_data": "/add_tenant"}],
                [{"text": "🔄 Reactivate Last Tenant", "callback_data": "/reactivate_tenant"}],
                [{"text": "📜 Previous Tenants", "callback_data": "/previous_tenants"}]
            ]
        Messenger.send(platform, chat_id, reply, inline_keyboard=inline_keyboard)

    def show_previous_tenants(self, platform: str, chat_id: str, flat_number: str):
        past_tenants = self.erp.get_previous_tenants(flat_number)
        if not past_tenants:
            Messenger.send(platform, chat_id, "📜 *Previous Tenants*\n\nNo past tenants found for this flat.")
            return
        reply = "📜 *Previous Tenants*\n\n"
        for t in past_tenants:
            reply += (
                f"👤 *{safe_md(t.get('tenant_name'))}*\n"
                f"📱 {t.get('mobile_no') or 'N/A'}\n"
                f"📅 {t.get('start_date') or 'Unknown'} to {t.get('end_date') or 'Unknown'}\n"
                "〰️〰️〰️〰️〰️〰️〰️\n"
            )
        inline_keyboard = [[{"text": "🔙 Back to Menu", "callback_data": "/tenant"}]]
        Messenger.send(platform, chat_id, reply, inline_keyboard=inline_keyboard)

    def process_reactivation(self, platform: str, chat_id: str, flat_number: str):
        success = self.erp.reactivate_last_tenant(flat_number)
        if success:
            Messenger.send(platform, chat_id, "✅ The previous tenant has been successfully reactivated.\n\nType /tenant to view the updated dashboard.")
        else:
            Messenger.send(platform, chat_id, "❌ Failed to reactivate. No previous tenants found, or an error occurred.")

    def start_edit(self, platform: str, chat_id: str, field_type: str):
        self.session.update_session(chat_id, module="edit_tenant", step=f"awaiting_{field_type}")
        if field_type == "end_date":
            Messenger.send(platform, chat_id, "📅 Please enter the new Tenancy End Date.\nFormat: YYYY-MM-DD\n(Or type NA if indefinite):", force_reply=True)
        else:
            field_name = "Mobile Number" if field_type == "phone" else "Email Address"
            Messenger.send(platform, chat_id, f"✏️ Please enter the new {field_name} for the tenant:", force_reply=True)

    def process_edit(self, platform: str, chat_id: str, text: str, flat_number: str, session_data: dict):
        step = session_data.get("step")
        if step == "awaiting_end_date":
            field_type = "end_date"
            new_value = text.strip().upper()
            if new_value != "NA" and not self.validate_date(new_value):
                Messenger.send(platform, chat_id, "❌ Invalid date. Format must be YYYY-MM-DD or NA.", force_reply=True)
                return
        else:
            field_type = "phone" if step == "awaiting_phone" else "email"
            new_value = text.strip()
        
        success = self.erp.update_tenant_details(flat_number, field_type, new_value)
        self.session.clear_session(chat_id)
        if success:
            display_name = "End Date" if field_type == "end_date" else field_type.capitalize()
            Messenger.send(platform, chat_id, f"✅ Tenant {display_name} updated successfully!\n\nUse /tenant to view the dashboard.")
        else:
            Messenger.send(platform, chat_id, "❌ Failed to update tenant details.")

    def confirm_deactivation(self, platform: str, chat_id: str):
        reply = "⚠️ *Warning*\n\nAre you sure you want to deactivate the current tenant? They will lose access to the bot immediately."
        inline_keyboard = [
            [{"text": "✅ Yes, Deactivate", "callback_data": "/confirm_deactivate_tenant"}],
            [{"text": "🔙 Cancel", "callback_data": "/tenant"}]
        ]
        Messenger.send(platform, chat_id, reply, inline_keyboard=inline_keyboard)

    def process_deactivation(self, platform: str, chat_id: str, flat_number: str):
        success = self.erp.deactivate_tenant(flat_number)
        if success:
            Messenger.send(platform, chat_id, "✅ Tenant successfully deactivated. The flat is now marked as self-occupied.")
            inline_keyboard = [[{"text": "➕ Add Tenant", "callback_data": "/add_tenant"}]]
            Messenger.send(platform, chat_id, "🏠 *Tenant Management*\n\nNo active tenant found.", inline_keyboard=inline_keyboard)
        else:
            Messenger.send(platform, chat_id, "❌ Failed to deactivate tenant. Please contact administration.")