from services.messenger import Messenger
from conversation.session import SessionManager
from api.erp import ERPClient
from utils.logger import app_logger
from utils.keyboard import KeyboardBuilder

class RegistrationController:
    # 🛡️ THE ULTIMATE FAILSAFE: A completely independent memory bank 
    # that ignores the router's memory wipes entirely.
    _memory_cache = {}

    def __init__(self, erp_client: ERPClient, session_manager: SessionManager):
        self.erp = erp_client
        self.session = session_manager

    def start_registration(self, platform: str, chat_id: str):
        self.session.update_session(chat_id, module="register", step="awaiting_flat", data={})
        # Clear any old ghost data for this user
        if chat_id in self.__class__._memory_cache:
            del self.__class__._memory_cache[chat_id]
        Messenger.send(platform, chat_id, "🏢 *Registration*\n\nPlease enter your Flat Number (e.g., TC2-411):", force_reply=True)

    def process_flat_number(self, platform: str, chat_id: str, text: str):
        import re
        
        # 1. Clean the input: uppercase and remove ONLY spaces
        raw_flat = text.upper().replace(" ", "")
        
        # 2. Extract components using Strict Architectural Rules
        # Rule 1: Starts with optional T
        # Rule 2: Block is strictly A, B, C, or D -> ([A-D])
        # Rule 3: Block number is strictly 1, 2, or 3 -> ([1-3])
        # Rule 4: Floor is 1-10, followed by a 2-digit flat -> ((?:[1-9]|10)\d{2})
        match = re.match(r'^T?([A-D])([1-3])-?((?:[1-9]|10)\d{2})$', raw_flat)
        
        if match:
            block_letter = match.group(1)
            block_num = match.group(2)
            flat_num = match.group(3)
            
            # 3. Rebuild it perfectly
            flat_number = f"T{block_letter}{block_num}-{flat_num}"
        else:
            # Fallback for completely unrecognized formats
            flat_number = raw_flat if raw_flat.startswith("T") else f"T{raw_flat}"

        # 4. Fetch from ERPNext
        profile = self.erp.get_resident_profile(flat_number)
        
        if not profile:
            Messenger.send(
                platform, 
                chat_id, 
                f"❌ Flat '{flat_number}' not found or is invalid.\n\n"
                f"Ensure your floor is between 1-10 and block is A-D (e.g., TC2-411). Please try again.", 
                force_reply=True
            )
            return

        self.__class__._memory_cache[chat_id] = {"flat": flat_number}
        
        # 5. Check if the flat is already verified
        status = getattr(profile, 'owner_status', 'Unverified')
        verified_statuses = ["Verified", "Verified by Bot", "Verified Physically"]
        
        if status in verified_statuses:
            # ALREADY VERIFIED: Proceed to Role Selection
            self.session.update_session(chat_id, module="register", step="awaiting_role", data={"flat": flat_number})
            if profile.is_rented:
                Messenger.send(platform, chat_id, f"Flat {flat_number} is marked as rented.\nHow are you registering?", inline_keyboard=KeyboardBuilder.registration_role_grid(is_rented=True))
            else:
                Messenger.send(platform, chat_id, f"✅ Flat {flat_number} found.\nHow are you registering?", inline_keyboard=KeyboardBuilder.registration_role_grid(is_rented=False))
        else:
            # NOT VERIFIED: Force Owner Role & Ask for Document
            clean_role = "Owner"
            self.__class__._memory_cache[chat_id]["role"] = clean_role
            self.session.update_session(chat_id, module="register", step="awaiting_reg_deed", data={"flat": flat_number, "role": clean_role})
            
            prompt = (
                f"⚠️ Flat {flat_number} is not yet verified.\n\n"
                "📎 *Upload Possession Letter*\n\n"
                "To verify your ownership and proceed with registration, please upload your **Possession cum Occupation Letter**.\n\n"
                "👇 Please tap the 📎 attachment icon and send the PDF or Image directly."
            )
            Messenger.send(platform, chat_id, prompt)
    def process_registration_deed(self, platform: str, chat_id: str, flat_number: str, message: dict, session_data: dict):
        import threading
        from utils.ocr_verifier import OCRVerifier

        if not flat_number:
            flat_number = self.__class__._memory_cache.get(chat_id, {}).get("flat")

        # 👇 Handle both Photos and Documents
        if message.get("photo"):
            # Telegram sends an array of sizes; [-1] gets the highest resolution
            new_file_id = message["photo"][-1]["file_id"]
        elif message.get("document"):
            mime = message["document"].get("mime_type", "").lower()
            if "pdf" not in mime and "image" not in mime:
                Messenger.send(platform, chat_id, "❌ Please upload a PDF or an Image (JPG/PNG).")
                return
            new_file_id = message["document"]["file_id"]
        else:
            Messenger.send(platform, chat_id, "❌ Please upload a PDF or an Image (JPG/PNG).")
            return
        
        # 👇 The rogue line has been removed from here!
        
        # Check if they are uploading Page 2, or if this is their first upload
        page_1_id = session_data.get("page_1_file_id")
        file_payload = [page_1_id, new_file_id] if page_1_id else new_file_id

        Messenger.send(platform, chat_id, "⏳ Verifying document via AI OCR... Please wait.")

        def run_ocr_and_proceed():
            # CALL THE SHARED BRAIN - Pass file_payload instead of a single ID
            result = OCRVerifier.process_full_verification(self.erp, file_payload, flat_number, update_status=False)
            
            if not result.get("success"):
                # Handle the 1-Page valid scenario (Old Format)
                if result.get("status") == "needs_page_2":
                    session_data["page_1_file_id"] = result.get("file_id")
                    self.session.update_session(chat_id, step="awaiting_reg_deed_page_2", module="register", data=session_data)
                    Messenger.send(
                        platform, chat_id, 
                        "📄 *Page 1 Accepted!*\n\n"
                        "This PDF only contains the first page. Please upload **Page 2** (containing the signatures) as a PDF to complete verification."
                    )
                    return
                else:
                    Messenger.send(platform, chat_id, f"❌ *Verification Failed*\n{result.get('error')}\n\nPlease try uploading again.")
                    return
                
            # SUCCESS: Move to Contact Sharing
            self.session.update_session(chat_id, step="awaiting_registration_contact", module="register", data=session_data)
            Messenger.send(
                platform, chat_id, 
                f"✅ *AI Verification Passed!*\n{result.get('table')}\n\n"
                f"📱 *Click the 'Share Contact' button below to finalize your registration.*",
                request_contact="📞 Share Contact"
            )

        threading.Thread(target=run_ocr_and_proceed).start()
    def process_role_selection(self, platform, chat_id, role, session_data=None):
        clean_role = role.replace("/reg_role_", "").strip()
        
        # 👇 SAVE TO OUR INDEPENDENT VAULT 👇
        if chat_id not in self.__class__._memory_cache:
            self.__class__._memory_cache[chat_id] = {}
        self.__class__._memory_cache[chat_id]["role"] = clean_role
        
        self.session.update_session(chat_id, module="register", step="awaiting_registration_contact", data={"role": clean_role})
        
        msg = (f"✅ You selected: *{clean_role}*\n\n"
               "📱 Please tap the **'Share Contact'** button below to securely verify your identity.")
        
        Messenger.send(platform, chat_id, msg, request_contact="📞 Share Contact")

    def verify_and_register_contact(self, platform: str, chat_id: str, user_id: str, contact_data: dict, session_data: dict):
        from utils.logger import app_logger 
        
        # 👇 RETRIEVE FROM OUR INDEPENDENT VAULT 👇
        cache = self.__class__._memory_cache.get(chat_id, {})
        
        flat_number = cache.get("flat")
        role = cache.get("role")
        shared_phone = str(contact_data.get("phone_number", "")).replace("+", "").replace(" ", "").replace("-", "")

        app_logger.info(f"REGISTRATION DIAGNOSTIC - Cache Vault Data - Flat: '{flat_number}', Role: '{role}', Phone: '{shared_phone}'")

        if not flat_number:
            self.session.clear_session(chat_id)
            # Remove the contact keyboard first, then send the inline button
            Messenger.send(platform, chat_id, "❌ Session expired or flat number lost.", remove_keyboard=True)
            Messenger.send(
                platform, 
                chat_id, 
                "Please tap the button below to start over:", 
                inline_keyboard=[[{"text": "📝 Register", "callback_data": "/register"}]]
            )
            return

        if role not in ["Owner", "Tenant", "Family"]:
            self.session.clear_session(chat_id)
            # Remove the contact keyboard first, then send the inline button
            Messenger.send(platform, chat_id, f"❌ Registration failed. Unrecognized role: '{role}'.", remove_keyboard=True)
            Messenger.send(
                platform, 
                chat_id, 
                "Please tap the button below to try again:", 
                inline_keyboard=[[{"text": "📝 Register", "callback_data": "/register"}]]
            )
            return
            
        profile = self.erp.get_resident_profile(flat_number)
        if not profile:
            self.session.clear_session(chat_id)
            Messenger.send(platform, chat_id, f"❌ Profile not found for flat {flat_number}.", remove_keyboard=True)
            return
            
        if role == "Owner":
            expected_phone = str(profile.owner_phone or "").replace("+", "").replace(" ", "").replace("-", "")
            if expected_phone and expected_phone not in shared_phone and shared_phone not in expected_phone:
                self.session.clear_session(chat_id)
                Messenger.send(platform, chat_id, "❌ Verification failed. The shared phone number does not match the registered Owner's number.", remove_keyboard=True)
                return
                
        elif role == "Tenant":
            expected_phone = str(profile.tenant_phone or "").replace("+", "").replace(" ", "").replace("-", "")
            if not expected_phone:
                self.session.clear_session(chat_id)
                Messenger.send(platform, chat_id, "❌ Registration blocked. The Flat Owner must add your details via the bot before you can register.", remove_keyboard=True)
                return
            if expected_phone not in shared_phone and shared_phone not in expected_phone:
                self.session.clear_session(chat_id)
                Messenger.send(platform, chat_id, "❌ Verification failed. The shared phone number does not match the Tenant number pre-approved by the Owner.", remove_keyboard=True)
                return

        elif role == "Family":
            family_member = self.erp.verify_family_member(flat_number, shared_phone)
            if not family_member:
                self.session.clear_session(chat_id)
                Messenger.send(platform, chat_id, "❌ Verification failed. Your number is not registered as an Active Family Member for this flat. Please ask the Owner to add you via the bot.", remove_keyboard=True)
                return

        success = self.erp.register_resident(flat_number, chat_id, user_id, role, shared_phone)
        
        if success:
            if role == "Owner":
                if not expected_phone:
                    self.erp.update_resident_field(flat_number, chat_id, "phone", shared_phone)
                
                # 👇 NEW: The user shared their contact successfully. Officially mark as verified!
                if getattr(profile, 'owner_status', 'Unverified') not in ["Verified", "Verified by Bot", "Verified Physically"]:
                    api_base = getattr(self.erp, "base_client", self.erp)
                    api_base.update_document("Owners", profile.owner_id, {"registration_status": "Verified by Bot"})

            # Cleanup our vault
            # Cleanup our vault
            if chat_id in self.__class__._memory_cache:
                del self.__class__._memory_cache[chat_id]
            self.session.clear_session(chat_id)
            
            # Send a separate message to remove the contact keyboard, then send the inline menu button
            Messenger.send(platform, chat_id, "🎉 *Registration Successful!*", remove_keyboard=True)
            Messenger.send(
                platform, 
                chat_id, 
                "Welcome to the Society Bot! Tap the button below to get started.",
                inline_keyboard=[[{"text": "📋 Open Main Menu", "callback_data": "/menu"}]]
            )
        else:
            self.session.clear_session(chat_id)
            Messenger.send(platform, chat_id, "❌ Registration failed. We couldn't link your account. Please contact the administration.", remove_keyboard=True)

    def start_guard_registration(self, platform, chat_id, user_info):
        msg = (f"🛡️ *Guard Registration Request*\n\n"
               f"Name: {user_info.get('first_name')}\n"
               f"ID: `{chat_id}`\n\n"
               "Please provide this ID to the RWA Administrator to activate your gate access.")
        Messenger.send(platform, chat_id, msg)