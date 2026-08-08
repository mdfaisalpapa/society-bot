from services.messenger import Messenger
from utils.keyboard import KeyboardBuilder
from utils.logger import app_logger

class StaffController:
    def __init__(self, erp_client, session_manager):
        self.erp = erp_client
        self.session = session_manager

    def show_staff_menu(self, platform: str, chat_id: str, flat_number: str):
        app_logger.info(f"Showing staff menu to {chat_id}")
        staff_list = self.erp.get_domestic_staff(flat_number)
        
        if not staff_list:
            # 👇 CHANGED: Updated message for when they have no staff
            msg = "🧹 *Domestic Staff Management*\n\nYou do not have any active domestic staff registered to your flat.\n\nClick below to find and link staff from the society pool."
        else:
            msg = "🧹 *Domestic Staff Management*\n\nSelect a staff member below to generate a daily Gate Pass, or link a new one:"
            
        # 👇 CHANGED: Now it ALWAYS calls the keyboard builder, even if the list is empty!
        keyboard = KeyboardBuilder.staff_list_menu(staff_list)
        
        Messenger.send(platform, chat_id, msg, inline_keyboard=keyboard)

    def generate_pass(self, platform: str, chat_id: str, flat_number: str, staff_id: str, staff_name: str, role: str):
        app_logger.info(f"Generating staff pass for {staff_name} at flat {flat_number}")
        
        result = self.erp.create_staff_pass(flat_number, staff_name, role)
        
        if result.get("success"):
            passcode = result["passcode"]
            msg = (f"✅ *Daily Gate Pass Generated*\n\n"
                   f"👤 *Staff:* {staff_name} ({role})\n"
                   f"🏠 *Flat:* {flat_number}\n\n"
                   f"The pass is valid for today. Below is the QR code for entry:")
            
            # Send the text confirmation
            Messenger.send(platform, chat_id, msg)
            
            # Send the QR Code Image
            qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data=verify_{passcode}"
            Messenger.send_photo(platform, chat_id, qr_url, caption=f"QR Code for {staff_name}")
        else:
            Messenger.send(platform, chat_id, "❌ Failed to generate pass. Please try again later.")

# ... existing methods (show_staff_menu, generate_pass) ...

    def show_staff_categories(self, platform: str, chat_id: str):
        app_logger.info(f"Showing staff categories to {chat_id}")
        msg = "🔍 *Find Society Staff*\n\nSelect a category to view approved staff available in the society:"
        Messenger.send(platform, chat_id, msg, inline_keyboard=KeyboardBuilder.staff_categories())

    def show_staff_by_category(self, platform: str, chat_id: str, category: str):
        from utils.logger import app_logger
        import json  # 👇 Added json import
        
        app_logger.info(f"Showing {category} staff to {chat_id}")
        
        try:
            staff_list = self.erp.get_staff_by_category(category)
            
            if not staff_list:
                msg = f"No active staff found in the {category} category."
                Messenger.send(platform, chat_id, msg, inline_keyboard=KeyboardBuilder.staff_categories())
                return
                
            # Plain text to bypass ANY Markdown parser errors
            msg = f"Available Staff: {category}\nClick below to link them to your flat."
            
            keyboard = KeyboardBuilder.society_staff_list(staff_list, category)
            
            # 👇 THE MAGIC FIX: Force the dictionary into a JSON string! 👇
            if isinstance(keyboard, dict):
                keyboard = json.dumps(keyboard)
            
            app_logger.info(f"DEBUG KEYBOARD PAYLOAD: {keyboard}")
            
            res = Messenger.send(platform, chat_id, msg, inline_keyboard=keyboard)
            app_logger.info(f"DEBUG TELEGRAM RESPONSE: {res}")
            
        except Exception as e:
            app_logger.error(f"CRITICAL ERROR in show_staff_by_category: {e}")
            Messenger.send(platform, chat_id, f"⚠️ An error occurred: {e}")
    def process_link_staff(self, platform: str, chat_id: str, flat_number: str, staff_id: str):
        app_logger.info(f"Resident {flat_number} linking staff {staff_id}")
        success = self.erp.link_staff_to_flat(staff_id, flat_number)
        
        if success:
            msg = "✅ *Staff Successfully Linked!*\n\nThey have been added to your profile. You can now generate daily Gate Passes for them."
            # Automatically route them back to their updated personal staff menu
            self.show_staff_menu(platform, chat_id, flat_number)
            Messenger.send(platform, chat_id, msg)
        else:
            Messenger.send(platform, chat_id, "❌ Failed to link staff. Please contact the Estate Office.")

    def process_unlink_staff(self, platform: str, chat_id: str, flat_number: str, staff_id: str):
        from utils.logger import app_logger
        app_logger.info(f"Resident {flat_number} unlinking staff {staff_id}")
        
        success = self.erp.unlink_staff_from_flat(staff_id, flat_number)
        
        if success:
            Messenger.send(platform, chat_id, "✅ *Staff Unlinked*\n\nYou will no longer receive notifications for this staff member.")
            # Refresh their staff menu
            self.show_staff_menu(platform, chat_id, flat_number)
        else:
            Messenger.send(platform, chat_id, "❌ Failed to unlink staff. Please try again.")

    def show_staff_details(self, platform: str, chat_id: str, staff_id: str):
        from utils.logger import app_logger
        app_logger.info(f"Showing details for staff {staff_id} to {chat_id}")
        
        staff_doc = self.erp.get_staff_details(staff_id)
        
        if not staff_doc:
            Messenger.send(platform, chat_id, "❌ Could not fetch staff details.")
            return
            
        name = staff_doc.get("staff_name", "Unknown")
        role = staff_doc.get("role", "Staff")
        phone = staff_doc.get("phone", "Not provided")
        status = staff_doc.get("status", "Unknown")
        
        # Format the rating
        rating = staff_doc.get("avg_rating", 0)
        rating_str = f"⭐ {rating}/5" if rating > 0 else "No Rating Yet"
        
        # Format the Reviews (Previously Complaints)
        complaints_list = staff_doc.get("recent_complaints", [])
        if complaints_list:
            comp_str = "\n".join([f"🔹 {c}" for c in complaints_list])
            # 👇 CHANGED: Now says "Recent Reviews"
            complaints_section = f"\n\n💬 *Recent Reviews:*\n{comp_str}"
        else:
            complaints_section = ""
        
        # Add to message
        msg = (f"👤 *Staff Profile*\n\n"
               f"📛 *Name:* {name}\n"
               f"🛠 *Role:* {role}\n"
               f"📱 *Phone:* {phone}\n"
               f"🆔 *ID:* {staff_id}\n"
               f"📊 *Status:* {status}\n"
               f"⭐️ *Community Rating:* {rating_str}"
               f"{complaints_section}\n\n"
               f"What would you like to do?")
               
        keyboard = KeyboardBuilder.staff_manage_menu(staff_id)
        Messenger.send(platform, chat_id, msg, inline_keyboard=keyboard)

    def prompt_staff_rating(self, platform: str, chat_id: str, staff_id: str):
        """Asks the user to enter a rating."""
        # 👇 FIX: Removed 'platform,' from this call 👇
       # 👇 Explicit named arguments
        # 👇 Perfect 4-argument signature
        self.session.update_session(chat_id, "staff", "WAITING_FOR_STAFF_RATING", {"target_staff_id": staff_id})
        
        msg = (f"⭐ *Rate Staff Member*\n\n"
               f"Please reply to this message with a single number from *1 to 5*\n"
               f"(1 = Poor, 5 = Excellent).")
               
        Messenger.send(platform, chat_id, msg, inline_keyboard=KeyboardBuilder.cancel_operation())

    def process_staff_rating(self, platform: str, chat_id: str, flat_number: str, staff_id: str, rating_text: str):
        """Validates the number and pushes it to ERPNext."""
        try:
            rating = int(rating_text.strip())
            if rating < 1 or rating > 5:
                raise ValueError
        except ValueError:
            Messenger.send(platform, chat_id, "⚠️ Invalid input. Please reply with a single number between 1 and 5 (e.g., 4).")
            return

        success = self.erp.submit_staff_review(staff_id, flat_number, "Rating", rating=rating)
        
        if success:
            Messenger.send(platform, chat_id, "✅ *Rating Submitted!*\n\nThank you for helping keep our community informed.")
# (Update BOTH the success and fail blocks to clear the session!)
            self.session.update_session(chat_id, "staff", "", {})
            self.show_staff_details(platform, chat_id, staff_id)
        else:
            Messenger.send(platform, chat_id, "❌ Failed to submit rating. Please try again later.")
# (Update BOTH the success and fail blocks to clear the session!)
            self.session.update_session(chat_id, "staff", "", {})
    def prompt_staff_complaint(self, chat_id: str, staff_id: str):
        """Asks the user to type their review."""
        self.session.update_session(chat_id, "staff", "WAITING_FOR_STAFF_COMPLAINT", {"target_staff_id": staff_id})
        
        # 👇 CHANGED: Friendly review prompt
        msg = (f"💬 *Write a Review*\n\n"
               f"Please type your feedback below (positive or constructive). "
               f"This will be shared anonymously on the staff member's profile.")
               
        Messenger.send("telegram", chat_id, msg, inline_keyboard=KeyboardBuilder.cancel_operation())

    def prompt_staff_complaint(self, platform: str, chat_id: str, staff_id: str):
        """Asks the user to type their review."""
        self.session.update_session(chat_id, "staff", "WAITING_FOR_STAFF_COMPLAINT", {"target_staff_id": staff_id})
        
        msg = (f"💬 *Write a Review*\n\n"
               f"Please type your feedback below (positive or constructive). "
               f"This will be shared anonymously on the staff member's profile.")
               
        Messenger.send(platform, chat_id, msg, inline_keyboard=KeyboardBuilder.cancel_operation())

    def process_staff_complaint(self, platform: str, chat_id: str, flat_number: str, staff_id: str, complaint_text: str):
        """Pushes the review text to ERPNext."""
        success = self.erp.submit_staff_review(staff_id, flat_number, "Complaint", comments=complaint_text)
        
        if success:
            Messenger.send(platform, chat_id, "✅ *Review Published*\n\nThank you for your feedback!")
            self.session.update_session(chat_id, "staff", "", {})
            self.show_staff_details(platform, chat_id, staff_id)
        else:
            Messenger.send(platform, chat_id, "❌ Failed to submit review. Please try again later.")
            self.session.update_session(chat_id, "staff", "", {})