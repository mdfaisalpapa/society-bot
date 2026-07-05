from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
class Keyboards:
    @staticmethod
    def main_menu(is_guard=False, is_registered=False, user_name="", cust_name=""):
        if is_guard:
            message = "🛡️ *Security Dashboard*"
            buttons = [[InlineKeyboardButton("📝 Log Walk-in Visitor", callback_data="/gate")], [InlineKeyboardButton("🔑 Check Passcode", callback_data="/passcode")], [InlineKeyboardButton("🚪 Logout", callback_data="/logout")]]
        elif is_registered:
            message = f"🏠 *Welcome, {user_name}!*"
            buttons = [[InlineKeyboardButton("✉️ Invite Visitor", callback_data="/invite"), InlineKeyboardButton("📋 History", callback_data="/visitors")], [InlineKeyboardButton("🛠️ Ticket", callback_data="/ticket"), InlineKeyboardButton("🔍 My Tickets", callback_data="/tickets")], [InlineKeyboardButton("👤 Profile", callback_data="/profile"), InlineKeyboardButton("🏠 Tenant", callback_data="/tenant")], [InlineKeyboardButton("🐾 Pets", callback_data="/pet"), InlineKeyboardButton("📊 Dues", callback_data="/dues")], [InlineKeyboardButton("🚪 Logout", callback_data="/logout")]]
        else:
            message = "🏠 *Welcome to Resident Bot*"
            buttons = [[InlineKeyboardButton("📝 Register", callback_data="/register")]]
        return message, InlineKeyboardMarkup(buttons)
    @staticmethod
    def tenant_relationships():
        buttons = [[InlineKeyboardButton("🏠 Tenant", callback_data="REL:Tenant")], [InlineKeyboardButton("👷 Caretaker", callback_data="REL:Caretaker")], [InlineKeyboardButton("🏢 Company", callback_data="REL:Company Lease")], [InlineKeyboardButton("🏨 Guest House", callback_data="REL:Guest House")]]
        return InlineKeyboardMarkup(buttons)
    @staticmethod
    def confirm_buttons(confirm_callback="/confirm", edit_callback="/edit", cancel_callback="/cancel"):
        buttons = [[InlineKeyboardButton("✅ Confirm", callback_data=confirm_callback)], [InlineKeyboardButton("✏️ Edit", callback_data=edit_callback)], [InlineKeyboardButton("❌ Cancel", callback_data=cancel_callback)]]
        return InlineKeyboardMarkup(buttons)
    @staticmethod
    def pet_menu(has_pets=False):
        if has_pets:
            message = "🐾 *Pet Management*"
            buttons = [[InlineKeyboardButton("➕ Add", callback_data="/add_pet"), InlineKeyboardButton("✏️ Edit", callback_data="/edit_pet")], [InlineKeyboardButton("❌ Remove", callback_data="/remove_pet")]]
        else:
            message = "🐾 No pets registered"
            buttons = [[InlineKeyboardButton("➕ Add Pet", callback_data="/add_pet")]]
        return message, InlineKeyboardMarkup(buttons)
