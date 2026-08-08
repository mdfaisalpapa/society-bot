from services.messenger import Messenger

class CoreRouter:
    def __init__(self, erp_client, session_manager, profile_ctrl, menu_ctrl, facility_ctrl):
        self.erp = erp_client
        self.session = session_manager
        self.profile = profile_ctrl
        self.menu = menu_ctrl
        self.facility = facility_ctrl

    def handle(self, platform, chat_id, text, message, contact_data, current_session, active_profile):
        
        # Inside the handle() method:
        # ==========================================
        # 🛡️ THE SECURITY QUARANTINE (Hard-Gate)
        # ==========================================
        valid_statuses = ["Verified by Bot", "Verified Physically", "Verified"]
        
        # If they are an Owner, but their status is NOT verified...
        if active_profile and active_profile.role == "Owner" and getattr(active_profile, 'owner_status', '') not in valid_statuses:
            
            # Allow them to upload the deed, cancel, or stay in the upload wizard
            allowed_commands = ["/upload_deed", "/cancel", "/start", "/see_deed"]
            is_in_upload_wizard = current_session.get("step") == "awaiting_sale_deed"
            
            if text not in allowed_commands and not is_in_upload_wizard:
                # Block the action and force them to the upload screen
                Messenger.send(
                    platform, 
                    chat_id, 
                    "🔒 *Account Locked: Verification Required*\n\n"
                    "To secure our community, owner access is restricted until your CGEWHO Possession Letter is verified.\n\n"
                    "Please tap the button below to upload your document.",
                    # We can use a standard inline keyboard button to trigger the upload flow
                    inline_keyboard=[[{"text": "📄 Upload Possession Letter", "callback_data": "/upload_deed"}]]
                )
                return True # Stop processing any other commands!
        # ==========================================
        # 🔍 RESIDENT LOOKUP COMMAND (/whois)
        # ==========================================
        if text.startswith("/whois"):
            if message.get("reply_to_message"):
                target_user = message["reply_to_message"].get("from", {})
                target_chat_id = str(target_user.get("id"))
                target_first_name = target_user.get("first_name", "This user")
                
                # 👇 NEW: Check if the target is the bot itself!
                if target_user.get("is_bot"):
                    reply_msg = "🤖 *That's me!*\n\nI am the automated Society Bot, managing community services, verifying records, and keeping the database clean 24/7."
                    Messenger.send(platform, chat_id, reply_msg)
                    return True
                
                target_profile = self.erp.get_profile_by_chat_id(target_chat_id)
                
                if target_profile:
                    flat_num = getattr(target_profile, 'flat_number', 'Unknown Flat')
                    role = getattr(target_profile, 'role', 'Resident')
                    
                    if role == 'Owner':
                        erp_name = getattr(target_profile, 'owner_name', target_first_name)
                    elif role == 'Tenant':
                        erp_name = getattr(target_profile, 'tenant_name', target_first_name)
                    else:
                        erp_name = getattr(target_profile, 'member_name', target_first_name)
                    
                    reply_msg = (
                        f"🔍 *Verified Member*\n\n"
                        f"👤 *Name:* {erp_name}\n"
                        f"🏠 *Flat:* {flat_num}\n"
                        f"🏷️ *Role:* {role}"
                    )
                else:
                    reply_msg = f"❌ *Unverified User*\n\nCould not find a registered profile for {target_first_name} in the system."
                    
                Messenger.send(platform, chat_id, reply_msg)
            else:
                Messenger.send(platform, chat_id, "ℹ️ *How to use /whois*\n\nPlease **reply** to a message sent by the person you want to identify, and type `/whois`.")
                
            return True
        # ... (The rest of your existing CoreRouter handle code continues below) ...
        if text.startswith("/start"):
            self.session.clear_session(chat_id)
            
            # 👇 NEW: Catch the Deep Link from the Group Request
            if text == "/start register" and not active_profile:
                # Call whatever method starts your registration flow
                self.profile.start_registration(platform, chat_id) 
                return True
                
            self.menu.show_main_menu(platform, chat_id, active_profile)
            return True
       # 1. General Core Menus, Cancels, & Commands
        if text in ["/start", "/menu", "/cancel"]:
            # Always clear any active wizard they were stuck in
            self.session.clear_session(chat_id)
            
            if text == "/cancel":
                Messenger.send(platform, chat_id, "❌ Operation cancelled.")
                
            self.menu.show_main_menu(platform, chat_id, active_profile)
            return True
            
        # 👇 NEW: Unified Hub Portal Navigation
        if text == "/portal_resident":
            self.menu.show_resident_portal(platform, chat_id, active_profile)
            return True
            
        if text == "/portal_guard":
            self.menu.show_guard_portal(platform, chat_id, active_profile)
            return True
            
        if text == "/portal_admin":
            self.menu.show_admin_portal(platform, chat_id, active_profile)
            return True
            
        if text == "/portal_verifier":
            self.menu.show_verifier_portal(platform, chat_id, active_profile)
            return True
        # 👇 NEW: Unified Hub Portal Navigation
        if text == "/portal_resident":
            self.menu.show_resident_portal(platform, chat_id, active_profile)
            return True
            
        if text == "/portal_aoa":
            self.menu.show_aoa_portal(platform, chat_id, active_profile)
            return True

        if text == "/profile": 
            self.profile.show_profile(platform, chat_id, active_profile)
            return True

        # 2. Profile Edits & Notification Toggles
        # 👇 ADDED "/see_deed" to the list below
        if text in ["/edit_phone", "/clear_phone", "/edit_email", "/upload_deed", "/see_deed"]:
            if not active_profile:
                Messenger.send(platform, chat_id, "❌ Unauthorized action. Profile not found.")
            else:
                if text == "/edit_phone": self.profile.start_edit_phone(platform, chat_id, active_profile)
                elif text == "/clear_phone": self.profile.save_edited_field(platform, chat_id, active_profile, "phone", "")
                elif text == "/edit_email": self.profile.start_edit_field(platform, chat_id, "email")
                elif text == "/upload_deed": 
                    if active_profile.role == "Owner": self.profile.start_sale_deed_upload(platform, chat_id)
                # 👇 NEW: Route the exact new command
                elif text == "/see_deed":
                    if active_profile.role == "Owner": self.profile.view_my_deed(platform, chat_id, active_profile.flat_number)
            return True
# 3. Utilities (Notices, Dues, Facility)
        if text == "/notices":
            notices = self.erp.get_active_notices()
            reply = "📋 *Notice Board & Circulars*\n\n" + "".join([f"🗓️ _{n['date']}_ \n*📌 {n['title']}*\n{n['content']}\n\n--- \n\n" for n in notices]) if notices else "📋 *Notice Board*\n\nNo active announcements at this time."
            # 👇 UPDATED BACK BUTTON
            Messenger.send(platform, chat_id, reply, inline_keyboard=[[{"text": "🔙 Back to Resident Portal", "callback_data": "/portal_resident"}]])
            return True
            
        if text == "/dues":
            if not active_profile: 
                Messenger.send(platform, chat_id, "❌ Profile not found.")
                return True
            total_dues = self.erp.get_outstanding_dues(active_profile.flat_number)
            msg = f"📊 *Maintenance Dues Account*\n\nFlat Number: {active_profile.flat_number}\nTotal Outstanding: *₹{total_dues:,.2f}*\n\n🔗 You can clear your balance via the digital desk portal or app payment links." if total_dues > 0 else f"📊 *Maintenance Dues Account*\n\n✅ Your account is fully settled. No outstanding dues found!"
            # 👇 UPDATED BACK BUTTON
            Messenger.send(platform, chat_id, msg, inline_keyboard=[[{"text": "🔙 Back to Resident Portal", "callback_data": "/portal_resident"}]])
            return True
            
        if text == "/book_facility":
            if not active_profile: 
                Messenger.send(platform, chat_id, "❌ Register profiles before booking facilities.")
            else: 
                self.facility.start_booking_flow(platform, chat_id)
            return True
        # 👇 NEW: Property Tax Scraper Route
        if text == "/fetch_tax_dues":
            if not active_profile or not getattr(active_profile, 'property_tax_no', None):
                Messenger.send(platform, chat_id, "❌ No Property Tax Number found on your profile.")
                return True
                
            tax_no = active_profile.property_tax_no
            
            # 1. Send immediate feedback so the user knows the bot is working
            Messenger.send(platform, chat_id, f"🔄 Connecting to TN Urban ePay portal for Tax No: `{tax_no}`...\n_This may take a few seconds._")
            
            # 2. Run the Scraper (Import it at the top of your router file!)
            from services.tax_scraper import TaxScraper
            result = TaxScraper.fetch_dues(tax_no)
            
            # 3. Deliver the result
            if result.get("error"):
                Messenger.send(platform, chat_id, f"⚠️ *Update:*\n{result['error']}")
            else:
                Messenger.send(platform, chat_id, f"📊 *Property Tax Update*\n\n{result.get('details')}")
                
            return True

        # 4. Core Sessions (Profile Editing, Facility)
        module = current_session.get("module")
        
        if module == "profile":
            if not active_profile:
                Messenger.send(platform, chat_id, "❌ Session expired or unauthorized.", remove_keyboard=True)
                self.session.clear_session(chat_id)
                return True
                
            step = current_session.get("step")
            if step == "awaiting_contact" and contact_data:
                if str(contact_data.get("user_id")) == str(message.get("from", {}).get("id")):
                    self.profile.save_edited_field(platform, chat_id, active_profile, "phone", contact_data.get("phone_number"), remove_keyboard=True)
                else:
                    Messenger.send(platform, chat_id, "❌ Verification failed.", remove_keyboard=True)
                    self.session.clear_session(chat_id)
            elif step == "awaiting_email" and text:
                self.profile.save_edited_field(platform, chat_id, active_profile, "email", text)
           # 👇 UPDATED: Catch the Sale Deed upload (Page 1 OR Page 2)
            elif step in ["awaiting_sale_deed", "awaiting_sale_deed_page_2"]:
                if message and (message.get("document") or message.get("photo")):
                    # Pass it to the controller (the controller will clear the session if it's the final page)
                    self.profile.handle_sale_deed_upload(platform, chat_id, active_profile.flat_number, message)
                else:
                    # 👇 UPDATED ERROR MESSAGE
                    Messenger.send(platform, chat_id, "❌ Please upload your Possession Letter as a PDF or an Image (JPG/PNG).")
            return True
        if module == "facility":
            if not text.startswith("/") or text.startswith("/fac_"):
                self.facility.handle_wizard(platform, chat_id, text, current_session.get("step"), current_session.get("data"), active_profile.flat_number)
                return True

        return False