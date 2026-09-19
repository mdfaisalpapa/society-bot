from services.messenger import Messenger
from api.erp import ERPClient
from entities.models import ResidentProfile
from conversation.session import SessionManager
from utils.keyboard import KeyboardBuilder

class ProfileController:
    def __init__(self, erp_client: ERPClient, session_manager: SessionManager):
        self.erp = erp_client
        self.session = session_manager

    def show_profile(self, platform: str, chat_id: str, profile: ResidentProfile):
        """Displays the user's profile with correct info based on their role."""
        
        # 1. Determine Identity based on explicit role
        role = str(getattr(profile, 'role', '')).strip().lower()
        # 👇 Define cgewho_reg right here at the top!
        cgewho_reg = getattr(profile, 'CGEWHO_reg_no', None) or 'Not Set'
        
        # 👇 NEW: Fetch Property Tax No safely
        tax_no = getattr(profile, 'property_tax_no', None)
        tax_display = tax_no if tax_no else "Not Updated ❌"

        if role == "owner":
            is_owner = True
            name, phone, email = profile.owner_name, profile.owner_phone, profile.owner_email
            display_role = "Flat Owner"
        elif role == "tenant":
            is_owner = False
            name, phone, email = profile.tenant_name, profile.tenant_phone, profile.tenant_email
            display_role = "Tenant"
        else: # Family or Fallback
            is_owner = False
            name, phone = profile.family_name, profile.family_phone
            email = "N/A"
            display_role = "Family Member"
            
        # 🛡️ TELEGRAM MARKDOWN FIX: Escape underscores so the API doesn't crash
        safe_name = str(name).replace("_", "\\_") if name else 'Not set'
        safe_email = str(email).replace("_", "\\_") if email else 'Not set'
        safe_tax = str(tax_display).replace("_", "\\_")
        safe_eb = str(profile.eb_service_no).replace("_", "\\_") if profile.eb_service_no else 'Not set'
            
        text = (
            f"🏠 *My Profile*\n\n"
            f"🏢 *Flat:* {profile.flat_number}\n"
            f"🧑‍💼 *Role:* {display_role}\n"
            f"📛 *Name:* {safe_name}\n"
            f"📞 *Phone:* {phone or 'Not set'}\n"
            f"✉️ *Email:* {safe_email}\n"
            f"🆔 *CGEWHO Reg No:* `{cgewho_reg}`\n" 
            f"🚗 *Parking:* {profile.parking_slot or 'Not set'}\n"
            f"⚡ *EB Service No:* {safe_eb}\n" 
        )
        
        if is_owner:
            text += f"📜 *Property Tax No:* {safe_tax}\n"
        
        # 👇 NEW: Display the Verification Status
        # Note: We use 'registration_status' because that is the field we update in ERPNext
        status = getattr(profile, 'owner_status', 'Unverified') 
        verified_statuses = ["Verified", "Verified by Bot", "Verified Physically", "Verified with CGEWHO Data"]
        
        # Add visual indicators for the status
        if status in verified_statuses:
            text += f"\n✅ *Document Status:* {status}\n"
        elif status == "Pending":
            text += f"\n⏳ *Document Status:* {status}\n"
        elif status == "Rejected":
            text += f"\n❌ *Document Status:* {status} (Please re-upload)\n"
        else:
            text += f"\n⚠️ *Document Status:* {status}\n"

        has_document = bool(getattr(profile, 'sale_deed', None))
        
        # 2. Build Buttons: Only give Owners the Edit/Tenant Management buttons
        keyboard = []
        if is_owner:
            keyboard.append([
                {"text": "📱 Edit Phone", "callback_data": "/edit_phone"}, 
                {"text": "✉️ Edit Email", "callback_data": "/edit_email"}
            ])
            
            # 👇 NEW: Place "Check Tax Dues" right next to/below the deed actions for owners
            if tax_no:
                keyboard.append([
                    {"text": "🔍 Check Tax Dues", "callback_data": "/fetch_tax_dues"},
                    {"text": "🔗 Pay on Portal", "url": "https://tnurbanepay.tn.gov.in/PT_CPPaymentDetails.aspx"}
                ])
            
            # STRICT ENFORCEMENT: Check Status AND Document Existence
            if status in verified_statuses and has_document:
                # Verified AND has file: ONLY View Deed
                keyboard.append([{"text": "👁️ View Possession Letter", "callback_data": "/see_deed"}])                
            elif status in ["Pending", "Rejected"] and has_document:
                keyboard.append([
                    {"text": "👁️ View Uploaded Letter", "callback_data": "/see_deed"},
                    {"text": "🔄 Re-upload Letter", "callback_data": "/upload_deed"}
                ])
            else:
                keyboard.append([{"text": "📎 Upload Possession Letter", "callback_data": "/upload_deed"}])
                
        keyboard.extend(KeyboardBuilder.back_to_menu())
        Messenger.send(platform, chat_id, text, inline_keyboard=keyboard)
    def process_logout(self, platform: str, chat_id: str, profile: ResidentProfile):
        """Executes the logout API call and explicitly clears sessions."""
        success = self.erp.logout_resident(profile.flat_number, chat_id)
        
        if success:
            self.session.clear_session(chat_id)
            Messenger.send(platform, chat_id, f"✅ Successfully logged out of {profile.flat_number}.\n\nYou will no longer receive gate alerts or notifications.")
        else:
            Messenger.send(platform, chat_id, "❌ Something went wrong while logging out. Please try again or contact Admin.")

    def start_edit_phone(self, platform: str, chat_id: str, profile: ResidentProfile):
        """Step 1: Check if phone exists. Offer to clear, or ask to share contact."""
        
        # Determine Identity based on Chat ID
        is_owner = str(profile.telegram_chat_id) == str(chat_id)
        current_phone = profile.owner_phone if is_owner else profile.tenant_phone
        
        if current_phone:
            self.session.update_session(chat_id, step="awaiting_phone_action", module="profile")
            Messenger.send(platform, chat_id, f"Your current registered phone is `{current_phone}`.\n\nDo you want to clear it so you can log in from another device?", inline_keyboard=KeyboardBuilder.profile_edit_phone_grid())
        else:
            self.session.update_session(chat_id, step="awaiting_contact", module="profile")
            Messenger.send(
                platform,
                chat_id,
                "Tap the button below to securely share your phone number with the bot:",
                request_contact="📱 Share My Phone Number"
            )

    def start_edit_field(self, platform: str, chat_id: str, field_type: str):
        """Step 1: Ask for new value and lock session (used for Email)."""
        self.session.update_session(chat_id, step=f"awaiting_{field_type}", module="profile")
        field_name = "Phone Number" if field_type == "phone" else "Email Address"
        
        Messenger.send(
            platform,
            chat_id,
            f"✏️ Please enter your new {field_name}:",
            force_reply=True
        )

    def save_edited_field(self, platform: str, chat_id: str, profile: ResidentProfile, field_type: str, new_value: str, remove_keyboard: bool = False):
        """Step 2: Save to ERPNext and clear session."""
        clean_value = new_value.strip()
        
        # UPDATE THIS LINE: Pass chat_id instead of profile.is_rented
        success = self.erp.update_resident_field(profile.flat_number, chat_id, field_type, clean_value)

        self.session.clear_session(chat_id)

        if success:
            field_name = "Phone" if field_type == "phone" else "Email"
            action = "cleared" if clean_value == "" else "updated"
            Messenger.send(platform, chat_id, f"✅ {field_name} {action}!\n\nType /profile to see the changes.", remove_keyboard=remove_keyboard)
        else:
            Messenger.send(platform, chat_id, "❌ Failed to update. Please try again.", remove_keyboard=remove_keyboard)



    def start_sale_deed_upload(self, platform: str, chat_id: str):
        self.session.update_session(chat_id, module="profile", step="awaiting_sale_deed")
        
        prompt = (
            "📎 *Upload Possession Letter*\n\n"
            "To verify your ownership, please upload your **Possession cum Occupation Letter** issued by CGEWHO.\n\n"
            "📄 The pdf file should be less than 1 MB and clearly show your Name, Flat No, and Car Parking.\n\n"
            "👇 Please tap the 📎 attachment icon and send the PDF/Image directly as a reply to this message."
        )
        Messenger.send(platform, chat_id, prompt, force_reply=True)

    def handle_sale_deed_upload(self, platform: str, chat_id: str, flat_number: str, message: dict):
        import os, threading
        from utils.ocr_verifier import OCRVerifier
        
        retry_keyboard = [[{"text": "📄 Upload Possession Letter", "callback_data": "/upload_deed"}]]

        # 👇 NEW: Handle both Photos and Documents
        if message.get("photo"):
            new_file_id = message["photo"][-1]["file_id"]
        elif message.get("document"):
            mime = message["document"].get("mime_type", "").lower()
            if "pdf" not in mime and "image" not in mime:
                Messenger.send(platform, chat_id, "❌ Please upload a PDF or an Image (JPG/PNG).", inline_keyboard=retry_keyboard)
                return
            new_file_id = message["document"]["file_id"]
        else:
            Messenger.send(platform, chat_id, "❌ Please upload a PDF or an Image (JPG/PNG).", inline_keyboard=retry_keyboard)
            return
        
        # ❌ The rogue line has been deleted from here!
        
        # Check session for a saved page 1 (if any)
        session_data = self.session.get_session(chat_id).get("data", {})
        page_1_id = session_data.get("page_1_file_id")
        file_payload = [page_1_id, new_file_id] if page_1_id else new_file_id

        Messenger.send(platform, chat_id, "⏳ Uploading and scanning document via AI OCR... Please wait.")
        def process_ocr_and_upload():
            # CALL THE SHARED BRAIN
            result = OCRVerifier.process_full_verification(self.erp, file_payload, flat_number)
            
            if not result.get("success"):
                if result.get("status") == "needs_page_2":
                    session_data["page_1_file_id"] = result.get("file_id")
                    self.session.update_session(chat_id, step="awaiting_sale_deed_page_2", module="profile", data=session_data)
                    Messenger.send(
                        platform, chat_id, 
                        "📄 *Page 1 Accepted!*\n\n"
                        "This PDF only contains the first page. Please upload **Page 2** (containing the signatures) as a PDF to complete verification."
                    )
                    return
                else:
                    Messenger.send(platform, chat_id, f"❌ *Automated Verification Failed*\n{result.get('error')}", inline_keyboard=retry_keyboard)
                    return
                
            # SUCCESS: Route to Main Menu
            if hasattr(self, 'session'):
                self.session.clear_session(chat_id)
                
            owner_invite = os.getenv("OWNERS_INVITE_LINK", "")
            resident_invite = os.getenv("RESIDENTS_INVITE_LINK", "")
            bot_link = os.getenv("BOT_LINK", "the Society Bot")
            
            success_msg = (
                f"✅ *AI Verification Passed & Approved!*\n{result.get('table')}\n\n"
                f"Your profile is now automatically Verified!\n\n"
                f"🤝 *Join the Owners Group:*\nTap here: {owner_invite}\n\n"
            )
            
            if result.get("is_rented"):
                success_msg += f"🏘️ *Residents Group:*\nSince your flat is let out, only your tenant is eligible. Forward this link to them: {bot_link}"
            else:
                success_msg += f"🏘️ *Join the Residents Group:*\nTap here: {resident_invite}"
                
            Messenger.send(platform, chat_id, success_msg)
            
            # Print the Main Menu
            from controllers.menu_controller import MenuController
            menu = MenuController()
            updated_profile = self.erp.get_profile_by_chat_id(chat_id)
            if updated_profile:
                menu.show_main_menu(platform, chat_id, updated_profile)

        threading.Thread(target=process_ocr_and_upload).start()
    def view_my_deed(self, platform: str, chat_id: str, flat_number: str):
        """Fetches the uploaded Sale Deed from ERPNext and sends it to the Owner."""
        import json, requests, os
        from services.messenger import Messenger
        
        Messenger.send(platform, chat_id, "⏳ Fetching your document securely from the server...")
        
        # 1. Fetch the file path from the Owner's record
        params = {"filters": json.dumps([["flat", "=", flat_number], ["active", "=", 1]]), "fields": '["sale_deed"]'}
        res = requests.get(f"{self.erp.base_url}/Owners", headers=self.erp.headers, params=params)
        
        if res.status_code == 200 and res.json().get("data"):
            file_path = res.json()["data"][0].get("sale_deed")
            
            if not file_path:
                Messenger.send(platform, chat_id, "❌ No document found on the server.")
                return
                
            # 2. Download the file from ERPNext (Bypasses private file restrictions using Bot Headers)
            root_url = self.erp.base_url.replace("/api/resource", "")
            if not file_path.startswith("/"):
                file_path = "/" + file_path
            full_url = f"{root_url}{file_path}"
            
            file_res = requests.get(full_url, headers=self.erp.headers)
            
            if file_res.status_code == 200:
                bot_token = os.getenv("SOCIETY_BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
                
                # 3. Send file directly via Telegram API
                file_name = file_path.split("/")[-1]
                mime_type = "application/pdf" if file_path.lower().endswith(".pdf") else "image/jpeg"
                
                # Route to sendDocument or sendPhoto based on file type
                if "image" in mime_type:
                    tg_url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
                    files = {"photo": (file_name, file_res.content, mime_type)}
                    data = {"chat_id": chat_id, "caption": "📄 *Your Possession Letter*"}
                else:
                    tg_url = f"https://api.telegram.org/bot{bot_token}/sendDocument"
                    files = {"document": (file_name, file_res.content, mime_type)}
                    data = {"chat_id": chat_id, "caption": "📄 *Your Possession Letter*"}
                    
                tg_res = requests.post(tg_url, data=data, files=files)
                
                if tg_res.status_code != 200:
                    Messenger.send(platform, chat_id, "❌ Failed to transmit the document via Telegram.")
            else:
                Messenger.send(platform, chat_id, "❌ Could not download the document from ERPNext.")
        else:
            Messenger.send(platform, chat_id, "❌ Could not locate your Owner profile.")