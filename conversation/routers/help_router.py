from services.messenger import Messenger

class HelpRouter:
    def __init__(self, menu_ctrl):
        self.menu = menu_ctrl

    def handle(self, platform, chat_id, text, message, current_session, active_profile):
        
        # 1. Show the Main Help Menu
        if text == "/help_menu":
            self.menu.show_help_menu(platform, chat_id)
            return True
            
        # 2. Topic: Visitors
        if text == "/help_visitors":
            help_text = (
                "🎫 *How to Manage Visitors*\n\n"
                "*Pre-Approve a Guest:*\n"
                "1. Open the Resident Portal.\n"
                "2. Tap '🎫 Pre-Approve Visitor' and select a date.\n"
                "3. Share the generated QR Code or 6-digit PIN with your guest.\n\n"
                "*Walk-in Visitors (No QR Code):*\n"
                "If a guest arrives unannounced, the guard will enter their details. You will receive an instant notification with a photo to ✅ *Approve* or ❌ *Deny* their entry."
            )
            Messenger.send(platform, chat_id, help_text, inline_keyboard=[[{"text": "🔙 Back to Help Menu", "callback_data": "/help_menu"}]])
            return True
            
        # 3. Topic: Tickets
        if text == "/help_tickets":
            help_text = (
                "🛠️ *How to Raise Maintenance Tickets*\n\n"
                "1. Open the Resident Portal and tap '🛠️ Raise Ticket'.\n"
                "2. Select a category (e.g., Plumbing, Electrical).\n"
                "3. Type a brief description of the issue.\n"
                "4. After submitting, you can attach up to 3 photos of the problem.\n\n"
                "The bot will auto-assign the task to the correct staff member and notify you when the status changes!"
            )
            Messenger.send(platform, chat_id, help_text, inline_keyboard=[[{"text": "🔙 Back to Help Menu", "callback_data": "/help_menu"}]])
            return True

        # 4. Topic: Work Permits
        if text == "/help_wp":
            help_text = (
                "👷 *How to Request a Work Permit*\n\n"
                "_Available to Owners only._\n\n"
                "1. Open the Owner Portal and tap '👷 Work Permit'.\n"
                "2. Select the type of work (Civil, Interior, etc.).\n"
                "3. Once approved by the Estate Office, your workers can scan their daily passes at the gate."
            )
            Messenger.send(platform, chat_id, help_text, inline_keyboard=[[{"text": "🔙 Back to Help Menu", "callback_data": "/help_menu"}]])
            return True

        # 5. Topic: Tenants
        if text == "/help_tenants":
            help_text = (
                "🏠 *How to Add a Tenant*\n\n"
                "_Available to Owners only._\n\n"
                "1. Open the Owner Portal and tap '🏠 Tenant'.\n"
                "2. Provide your tenant's Name, Phone, and Email.\n"
                "3. Once registered, your tenant can start the bot using their Telegram app.\n\n"
                "*Note:* While a flat is rented, the tenant handles daily operations (Visitors, Tickets). The owner's dashboard will hide these buttons to prevent clutter."
            )
            Messenger.send(platform, chat_id, help_text, inline_keyboard=[[{"text": "🔙 Back to Help Menu", "callback_data": "/help_menu"}]])
            return True

        return False