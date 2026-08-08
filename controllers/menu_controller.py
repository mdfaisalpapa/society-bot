import os
import requests
from services.messenger import Messenger
from entities.models import ResidentProfile
from api.erp import ERPClient
from utils.keyboard import KeyboardBuilder
from utils.logger import app_logger

class MenuController:
    def __init__(self):
        self.erp = ERPClient()

    def show_main_menu(self, platform, chat_id, active_profile):
        """Displays the Unified Hub with Role Selection Buttons."""
        app_logger.info(f"Showing main menu to chat_id: {chat_id}")
        
        if not active_profile:
            Messenger.send(platform, chat_id, "Please /register to use this bot.")
            return

        role = getattr(active_profile, 'role', '')
        staff_role = getattr(active_profile, 'staff_role', None)
        clean_staff_role = staff_role.strip() if staff_role else ""

        # ==========================================
        # 1. BUILD UNIFIED DASHBOARD TEXT
        # ==========================================
        if role == "Owner": raw_name = getattr(active_profile, 'owner_name', None)
        elif role == "Tenant": raw_name = getattr(active_profile, 'tenant_name', None)
        elif role == "Family": raw_name = getattr(active_profile, 'family_name', None)
        else: raw_name = None

        name = raw_name or getattr(active_profile, 'staff_name', None) or getattr(active_profile, 'resident_name', 'User')
        flat = getattr(active_profile, 'flat_number', 'ESTATE OFFICE')
        
        text = (f"🏠 *Welcome back, {name} ({flat})!*\n\n"
                "Your Unified Dashboard is ready. Please select a portal below to continue:\n")
                
        # ==========================================
        # 2. VERIFICATION & GROUP MEMBERSHIP CHECK
        # ==========================================
        if role in ["Owner", "Tenant", "Family"]:
            is_owner = (role == "Owner")
            is_rented = getattr(active_profile, 'is_rented', False)
            status = getattr(active_profile, 'owner_status', 'Unverified') if is_owner else "Verified"
            verified_statuses = ["Verified", "Verified by Bot", "Verified Physically"]
            
            if status not in verified_statuses and status != "Pending":
                text += "\n⚠️ *Action Required:* You are not verified. Please go to your Profile to upload your Possession Letter and gain access to the community groups.\n"
            elif status == "Pending":
                text += "\n⏳ *Status:* Your document is currently under review.\n"

            if status in verified_statuses:
                bot_token = os.getenv("SOCIETY_BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
                owners_group_id = os.getenv("OWNERS_GROUP_ID")
                residents_group_id = os.getenv("RESIDENTS_GROUP_ID")
                owners_link = os.getenv("OWNERS_INVITE_LINK", "")
                residents_link = os.getenv("RESIDENTS_INVITE_LINK", "")

                def is_in_group(group_id):
                    if not group_id: return True 
                    try:
                        res = requests.get(f"https://api.telegram.org/bot{bot_token}/getChatMember?chat_id={group_id}&user_id={chat_id}", timeout=2).json()
                        if res.get("ok"): return res["result"]["status"] in ["member", "administrator", "creator", "restricted"]
                    except Exception: pass
                    return False

                group_status_lines = []
                is_rented_bool = str(is_rented).strip().lower() in ['1', 'true', 'yes']
                
                if is_owner:
                    if is_in_group(owners_group_id): group_status_lines.append("🤝 *Owners Group:* ✅ Joined")
                    else: group_status_lines.append(f"🤝 *Owners Group:* ❌ Not Joined. Join at: {owners_link}")

                is_resident = (is_owner and not is_rented_bool) or (not is_owner and role.lower() == "tenant")
                if is_resident:
                    if is_in_group(residents_group_id): group_status_lines.append("🏘️ *Residents Group:* ✅ Joined")
                    else: group_status_lines.append(f"🏘️ *Residents Group:* ❌ Not Joined. Join at: {residents_link}")

                if group_status_lines:
                    text += "\n📢 *Community Groups:*\n" + "\n".join(group_status_lines) + "\n"
        
       # ==========================================
        # 3. GENERATE ROLE-BASED PORTAL BUTTONS
        # ==========================================
        keyboard = []
        is_aoa = getattr(active_profile, 'is_aoa_member', False)
        
        if role in ["Owner", "Tenant", "Family"]:
            keyboard.append([{"text": "🏠 Open Resident Portal", "callback_data": "/portal_resident"}])
            
        # 👇 NEW: Add the AoA Portal Button if they are a member
        if is_aoa:
            keyboard.append([{"text": "👔 Open AoA Committee Portal", "callback_data": "/portal_aoa"}])
            
        if clean_staff_role in ["Office Admin", "Estate Manager"]:
            keyboard.append([{"text": "🏢 Open Estate Office Portal", "callback_data": "/portal_admin"}])
        elif clean_staff_role == "Doc Verifier":
            keyboard.append([{"text": "✅ Open Verification Desk", "callback_data": "/portal_verifier"}])
        elif clean_staff_role == "Security Guard":
            keyboard.append([{"text": "🛡️ Open Security Gate Portal", "callback_data": "/portal_guard"}])
        elif clean_staff_role and clean_staff_role.startswith("Maintenance"):
            keyboard.append([{"text": f"🛠️ Open {clean_staff_role} Dashboard", "callback_data": "/my_assigned_tickets"}])

        # 👇 NEW: Add the Help Button at the very bottom of the Hub
        keyboard.append([{"text": "❓ Help & Guides", "callback_data": "/help_menu"}])

        Messenger.send(platform, chat_id, text, inline_keyboard=keyboard)

    # ==========================================
    # SUB-PORTAL METHODS (Triggered by Buttons)
    # ==========================================
    def show_resident_portal(self, platform, chat_id, active_profile):
        role = getattr(active_profile, 'role', '')
        is_owner = (role == "Owner")
        is_rented = getattr(active_profile, 'is_rented', False)
        is_aoa = getattr(active_profile, 'is_aoa_member', False)
        
        keyboard = KeyboardBuilder.resident_grid(is_owner, is_rented, is_aoa)
        # 👇 BACK BUTTON CHANGED
        keyboard.append([{"text": "🔙 Back to Main Hub", "callback_data": "/menu"}])
        
        text = ("🏠 *Resident Portal*\n\n"
                "You can use the *🚨 Report Violation* button below to flag any active work permit infractions in the building.\n\n"
                "Select a service:")
        Messenger.send(platform, chat_id, text, inline_keyboard=keyboard)

    def show_guard_portal(self, platform, chat_id, active_profile):
        keyboard = KeyboardBuilder.guard_inline_keyboard()
        # 👇 BACK BUTTON CHANGED
        keyboard.append([{"text": "🔙 Back to Main Hub", "callback_data": "/menu"}])
        Messenger.send(platform, chat_id, "🛡️ *Security Gate Portal*\n\nSelect an action:", inline_keyboard=keyboard)

    def show_admin_portal(self, platform, chat_id, active_profile):
        keyboard = KeyboardBuilder.admin_grid()
        # 👇 BACK BUTTON CHANGED
        keyboard.append([{"text": "🔙 Back to Main Hub", "callback_data": "/menu"}])
        Messenger.send(platform, chat_id, "🏢 *Estate Office Portal*\n\nSelect an administrative action:", inline_keyboard=keyboard)

    def show_verifier_portal(self, platform, chat_id, active_profile):
        keyboard = KeyboardBuilder.verifier_grid()
        # 👇 BACK BUTTON CHANGED
        keyboard.append([{"text": "🔙 Back to Main Hub", "callback_data": "/menu"}])
        Messenger.send(platform, chat_id, "✅ *Verification Desk*\n\nSelect a verification queue:", inline_keyboard=keyboard)

    def show_aoa_portal(self, platform, chat_id, active_profile):
        keyboard = [
            [{"text": "🛡️ Monitor Maintenance Tickets", "callback_data": "/aoa_monitor_menu_open"}],
            # 👇 BACK BUTTON CHANGED
            [{"text": "🔙 Back to Main Hub", "callback_data": "/menu"}]
        ]
        
        text = ("👔 *AoA Committee Portal*\n\n"
                "Welcome to the Association Management dashboard. "
                "Select an administrative action below:")
                
        Messenger.send(platform, chat_id, text, inline_keyboard=keyboard)

    def show_help_menu(self, platform, chat_id):
        keyboard = [
            [{"text": "🎫 Inviting Visitors", "callback_data": "/help_visitors"}, {"text": "🛠️ Raising Tickets", "callback_data": "/help_tickets"}],
            [{"text": "👷 Work Permits", "callback_data": "/help_wp"}, {"text": "🏠 Adding Tenants", "callback_data": "/help_tenants"}],
            [{"text": "🔙 Back to Main Hub", "callback_data": "/menu"}]
        ]
        
        text = ("❓ *Society Bot Help Center*\n\n"
                "Welcome to the quick reference guide. Tap a topic below to learn how that module works:")
                
        Messenger.send(platform, chat_id, text, inline_keyboard=keyboard)