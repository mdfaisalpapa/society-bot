from services.telegram import TelegramService
from services.messenger import Messenger
from conversation.session import SessionManager
from api.erp import ERPClient
from controllers.profile_controller import ProfileController
from controllers.registration_controller import RegistrationController
from controllers.menu_controller import MenuController
from controllers.maintenance_controller import MaintenanceController
from controllers.visitor_controller import VisitorController
from controllers.tenant_controller import TenantController
from controllers.gate_controller import GateController
from controllers.facility_controller import FacilityController

class ConversationEngine:
    def __init__(self):
        self.session_manager = SessionManager()
        self.erp_client = ERPClient()
        self.profile_controller = ProfileController(self.erp_client, self.session_manager)
        self.registration_controller = RegistrationController(self.erp_client, self.session_manager)
        self.menu_controller = MenuController()
        self.maintenance_controller = MaintenanceController(self.erp_client, self.session_manager)
        self.visitor_controller = VisitorController(self.erp_client, self.session_manager)
        self.tenant_controller = TenantController(self.erp_client, self.session_manager)
        self.gate_controller = GateController(self.erp_client)
        self.facility_controller = FacilityController(self.erp_client, self.session_manager)

    def process_update(self, update: dict):
        platform = "telegram" 
        if "object" in update and update.get("object") == "whatsapp_business_account":
            platform = "whatsapp"

        message = update.get("message", {})
        chat_id = str(message.get("chat", {}).get("id"))
        
        # 👇 1. FETCH SESSION EARLY 👇
        current_session = self.session_manager.get_session(chat_id) if chat_id else {}
        
        # 3. HANDLE FILE UPLOADS FIRST
        if message.get("photo") or message.get("document"):
            
            # --- 0. GUARD QR SCAN ROUTING ---
            if self.erp_client.is_authorized_guard(chat_id, platform) and message.get("photo"):
                # If they are NOT doing a walk-in, assume it's a QR code scan
                if current_session.get("module") != "guard_walkin":
                    file_id = message.get("photo")[-1].get("file_id")
                    self.gate_controller.process_qr_image(platform, chat_id, message, file_id)
                    return
            # --------------------------------

            reply_to = message.get("reply_to_message", {})
            reply_text = reply_to.get("text") or reply_to.get("caption") or ""
            active_profile = self.erp_client.get_profile_by_chat_id(chat_id)
            
            # --- 1. Native Mobile Routing (Using Reply Context) ---
            if "Module: Maintenance Ticket" in reply_text:
                ticket_id = self._extract_id_from_text(reply_text)
                self.maintenance_controller.handle_file_upload(platform, chat_id, ticket_id, message)
                return
                
            elif "Module: Tenant Document" in reply_text:
                if not active_profile or str(active_profile.telegram_chat_id) != str(chat_id):
                    Messenger.send(platform, chat_id, "❌ Unauthorized.")
                    return
                self.tenant_controller.handle_document_upload(platform, chat_id, active_profile.flat_number, message, current_session)
                return
                
            # --- 2. Web/Desktop Fallback (Using Session State) ---
            module = current_session.get("module") or "" 
            
            if module == "maintenance":
                ticket_id = current_session.get("data", {}).get("ticket_id")
                if ticket_id:
                    self.maintenance_controller.handle_file_upload(platform, chat_id, ticket_id, message)
                    return
                    
            elif "tenant" in module or module == "add_tenant" or module == "edit_tenant":
                if not active_profile or str(active_profile.telegram_chat_id) != str(chat_id):
                    Messenger.send(platform, chat_id, "❌ Unauthorized.")
                    return
                self.tenant_controller.handle_document_upload(platform, chat_id, active_profile.flat_number, message, current_session)
                return
                
            # 👇 2. ALLOW WALK-IN PHOTOS TO PASS THROUGH 👇
            elif module == "guard_walkin":
                pass # Let it bypass the error and flow down to the session block below
                
            else:
                # --- 3. If All Routing Fails ---
                Messenger.send(
                    platform, 
                    chat_id, 
                    "⚠️ Upload received, but the bot lost the context.\n\n"
                    "On Telegram Web/Desktop, drag-and-drop often unlinks the file. "
                    "Please **right-click** (or click the three dots) on the bot's prompt, select **Reply**, and then attach the file."
                )
                return
        
        callback_query = update.get("callback_query", {})
        chat_id = None
        text = ""
        contact_data = None 

        if callback_query:
            if platform == "telegram":
                TelegramService.answer_callback_query(callback_query.get("id"))
            chat_id = str(callback_query.get("message", {}).get("chat", {}).get("id"))
            text = callback_query.get("data", "")
        elif message:
            chat_id = str(message.get("chat", {}).get("id"))
            text = message.get("text", "").strip() if message.get("text") else ""
            contact_data = message.get("contact") 

        if not chat_id:
            return

        current_session = self.session_manager.get_session(chat_id)

        # GUARD SCAN INTERCEPTOR (Updated)
        if text.startswith("/start verify_"):
            
            # --- AGNOSTIC SECURITY LOCK ---
            if not self.erp_client.is_authorized_guard(chat_id, platform):
                Messenger.send(platform, chat_id, "❌ *Unauthorized Device.* Access denied.")
                return
            # ------------------------------

            passcode = text.split("verify_")[1]
            result = self.erp_client.verify_visitor_passcode(passcode)
            
            # 👇 Create the rapid-loop scanner button 👇
            scan_loop_keyboard = [
                [{"text": "📷 Scan Next Pass", "web_app": {"url": "https://kvc3.railwayofficersclub.in/scanner"}}]
            ]
            
            if result.get("success"):
                success_msg = (f"✅ *ACCESS GRANTED*\n\n"
                               f"👤 *Visitor:* {result['visitor_name']}\n"
                               f"🏠 *Going to:* {result['resident']}\n"
                               f"🚗 *Vehicle:* {result['vehicle']}\n\n"
                               f"_Visitor has been automatically logged as 'Entered'._")
                # Send the success message WITH the scanner button attached
                Messenger.send(platform, chat_id, success_msg, inline_keyboard=scan_loop_keyboard)
            else:
                error_msg = f"❌ *ACCESS DENIED*\n\n{result.get('error')}"
                # Send the error message WITH the scanner button attached
                Messenger.send(platform, chat_id, error_msg, inline_keyboard=scan_loop_keyboard)
            return
        # 👆 END GUARD SCAN INTERCEPTOR 👆
        
        
        # GLOBAL COMMAND OVERRIDE
        # 👇 Now protects BOTH /v (visitors) and /cat_ (maintenance categories) 👇
        if text.startswith("/") and text not in ["/rel_Tenant", "/rel_Caretaker", "/rel_Company Lease", "/rel_Guest House", "/confirm_tenant", "/reg_role_Owner", "/reg_role_Tenant"] and not text.startswith("/v") and not text.startswith("/cat_"):
            self.session_manager.clear_session(chat_id)
            current_session = {} 
            if text == "/cancel":
                Messenger.send(platform, chat_id, "✅ Current operation cancelled.", remove_keyboard=True)
                return
# Add this in process_update
        print(f"DEBUG: Current session for {chat_id}: {current_session}")
        if current_session.get("module") == "register":
            step = current_session.get("step")
            if step == "awaiting_flat" and text:
                self.registration_controller.process_flat_number(platform, chat_id, text)
                return
            elif step == "awaiting_role" and text:
                self.registration_controller.process_role_selection(platform, chat_id, text, current_session.get("data", {}))
                return
            elif step == "awaiting_registration_contact" and contact_data:
                if str(contact_data.get("user_id")) == str(message.get("from", {}).get("id")):
                    user_id = str(update.get("message", {}).get("from", {}).get("id"))
                    self.registration_controller.verify_and_register_contact(
                        platform, chat_id, user_id, contact_data, current_session.get("data", {})
                    )
                else:
                    Messenger.send(platform, chat_id, "❌ Verification failed. You must share your own profile contact.", remove_keyboard=True)
                    self.session_manager.clear_session(chat_id)
                return

        active_profile = self.erp_client.get_profile_by_chat_id(chat_id)

        if current_session.get("module") == "profile" and active_profile:
            if str(active_profile.telegram_chat_id) != str(chat_id):
                Messenger.send(platform, chat_id, "❌ Unauthorized. Tenants cannot modify profile details.", remove_keyboard=True)
                self.session_manager.clear_session(chat_id)
                return
            step = current_session.get("step")
            if step == "awaiting_contact" and contact_data:
                if str(contact_data.get("user_id")) == str(message.get("from", {}).get("id")):
                    phone_number = contact_data.get("phone_number")
                    self.profile_controller.save_edited_field(platform, chat_id, active_profile, "phone", phone_number, remove_keyboard=True)
                else:
                    Messenger.send(platform, chat_id, "❌ Verification failed.", remove_keyboard=True)
                    self.session_manager.clear_session(chat_id)
                return
            elif step == "awaiting_email" and text:
                self.profile_controller.save_edited_field(platform, chat_id, active_profile, "email", text)
                return

        if current_session.get("module") == "edit_tenant" and active_profile and active_profile.is_rented:
            if str(active_profile.telegram_chat_id) != str(chat_id):
                Messenger.send(platform, chat_id, "❌ Unauthorized.", remove_keyboard=True)
                self.session_manager.clear_session(chat_id)
                return
            self.tenant_controller.process_edit(platform, chat_id, text, active_profile.flat_number, current_session)
            return

        if current_session.get("module") == "maintenance" and active_profile:
            step = current_session.get("step")
            if step == "awaiting_category" and text.startswith("/cat_"):
                self.maintenance_controller.process_category_selection(platform, chat_id, text)
                return
            elif step == "awaiting_description" and text:
                self.maintenance_controller.submit_ticket(platform, chat_id, active_profile, text)
                return

        if current_session.get("module") == "add_tenant" and active_profile:
            if text not in ["/confirm_tenant", "/cancel"]:
                self.tenant_controller.process_wizard(platform, chat_id, text, current_session)
                return

        # 👇 Allows Contact Sharing and our new /v buttons into the wizard 👇
        if current_session and current_session.get("module") == "visitor":
            # Allow it through IF it's not a command, OR if it's a specific /v wizard command, OR if it's a shared contact
            if not text.startswith("/") or text.startswith("/v") or contact_data:
                self.visitor_controller.handle_wizard_reply(
                    platform, 
                    chat_id, 
                    text, 
                    current_session.get("data"), 
                    current_session.get("step"), 
                    contact_data
                )
                return
        # GUARD WALK-IN SESSION HANDLER
        if current_session and current_session.get("module") == "guard_walkin":
            step = current_session.get("step")
            session_data = current_session.get("data", {})
            
            if step == "awaiting_flat":
                if not text:
                    Messenger.send(platform, chat_id, "❌ Please type the Flat Number first (e.g., TC2-110) before taking a photo.")
                    return
                
                clean_flat = text.upper().strip()
                resident_chat = self.erp_client.get_resident_chat_id(clean_flat)
                
                if not resident_chat:
                    Messenger.send(platform, chat_id, "❌ Invalid Flat Number or Resident not registered on Telegram. Try again:")
                    return
                    
                session_data["flat"] = clean_flat 
                session_data["resident_chat"] = resident_chat
                # Advance to the new purpose step
                self.session_manager.update_session(chat_id, module="guard_walkin", step="awaiting_purpose", data=session_data)
                
                purpose_keyboard = [
                    [{"text": "📦 Delivery", "callback_data": "wpurp_Delivery"}, {"text": "🚕 Cab", "callback_data": "wpurp_Cab"}],
                    [{"text": "🛠️ Service", "callback_data": "wpurp_Service"}, {"text": "🤝 Guest", "callback_data": "wpurp_Guest"}]
                ]
                Messenger.send(platform, chat_id, f"✅ Flat {clean_flat} Verified.\n\nWhat is the purpose of the visit?", inline_keyboard=purpose_keyboard)
                return
                
            elif step == "awaiting_purpose":
                # Ensure they actually clicked a button
                if not text.startswith("wpurp_"):
                    Messenger.send(platform, chat_id, "❌ Please select an option from the buttons above.")
                    return
                
                purpose = text.split("_")[1]
                session_data["purpose"] = purpose
                self.session_manager.update_session(chat_id, module="guard_walkin", step="awaiting_photo_or_name", data=session_data)
                
                Messenger.send(platform, chat_id, f"✅ Purpose: {purpose}\n\n📸 *Snap a live photo* of the visitor, OR type their name:")
                return

            elif step == "awaiting_photo_or_name":
                flat = session_data["flat"]
                res_chat = session_data["resident_chat"]
                purpose = session_data.get("purpose", "Guest")
                visitor_identifier = "Walk-in Visitor"
                photo_id = None
                
                if message.get("photo"):
                    photo_id = message.get("photo")[-1].get("file_id")
                elif text:
                    visitor_identifier = text.strip()
                else:
                    Messenger.send(platform, chat_id, "❌ Please send a photo or type a name.")
                    return
                
                # Pass the dynamically selected purpose to your ERP API
                log_id = self.erp_client.create_walkin_visitor(flat, visitor_identifier, purpose)
                
                resident_keyboard = [
                    [
                        {"text": "✅ Approve", "callback_data": f"w_app_{log_id}_{chat_id}_{flat}"},
                        {"text": "❌ Deny", "callback_data": f"w_den_{log_id}_{chat_id}_{flat}"}
                    ]
                ]
                
                # Dynamic emojis for the resident's notification alert
                purpose_emoji = {"Delivery": "📦", "Cab": "🚕", "Service": "🛠️", "Guest": "🤝"}.get(purpose, "👤")
                
                if photo_id:
                    import io
                    import requests
                    
                    file_url = Messenger.get_file_url(platform, photo_id)
                    if file_url:
                        img_response = requests.get(file_url)
                        photo_bytes = io.BytesIO(img_response.content)
                        photo_bytes.name = "visitor.jpg"
                        
                        alert_msg = f"🔔 *Gate Security Alert*\nA {purpose_emoji} *{purpose}* is at the gate requesting entry to your flat."
                        Messenger.send_photo(platform, res_chat, photo_bytes, caption=alert_msg, inline_keyboard=resident_keyboard)
                    else:
                        alert_msg = f"🔔 *Gate Security Alert*\nA {purpose_emoji} *{purpose}* is at the gate requesting entry. (Photo capture failed)"
                        Messenger.send(platform, res_chat, alert_msg, inline_keyboard=resident_keyboard)
                        
                else:
                    alert_msg = f"🔔 *Gate Security Alert*\nA {purpose_emoji} *{purpose}* named *{visitor_identifier}* is at the gate requesting entry to your flat."
                    Messenger.send(platform, res_chat, alert_msg, inline_keyboard=resident_keyboard)
                
                Messenger.send(platform, chat_id, "⏳ Details pushed to resident. Awaiting approval...")
                self.session_manager.clear_session(chat_id)
                return
        # Add this step validation checking near your other session routers (like visitor or maintenance)
        if current_session and current_session.get("module") == "facility":
            if not text.startswith("/") or text.startswith("/fac_"):
                self.facility_controller.handle_wizard(
                    platform, chat_id, text, 
                    current_session.get("step"), 
                    current_session.get("data"), 
                    active_profile.flat_number
                )
                return
        # Place this right inside your callback_query interception handling block
        if text == "/guard_walkin" and self.erp_client.is_authorized_guard(chat_id, platform):
            self.session_manager.update_session(chat_id, module="guard_walkin", step="awaiting_flat", data={})
            Messenger.send(platform, chat_id, "🚶 *Walk-in Registration*\n\nEnter the target Flat Number (e.g., TC2-110):")
            return

        # Place this inside your resident callback interceptor routines
        if text.startswith("w_app_") or text.startswith("w_den_"):
            action, log_id, guard_id, target_flat = text.split("_")[0], text.split("_")[2], text.split("_")[3], text.split("_")[4]
            
            if action == "w": # Approve
                self.erp_client.update_visitor_status(log_id, "Approved")
                Messenger.send(platform, chat_id, "✅ You approved entry for this visitor.")
                Messenger.send(platform, guard_id, f"✅ *Walk-in Approved* for Flat {target_flat}. You can open the gate.")
            else: # Deny
                self.erp_client.update_visitor_status(log_id, "Deny")
                Messenger.send(platform, chat_id, "❌ You denied entry for this visitor.")
                Messenger.send(platform, guard_id, f"🛑 *Walk-in DENIED* for Flat {target_flat}. Turn the visitor back.")
            return

        # Check if they are an authorized guard before trapping them
        is_guard = self.erp_client.is_authorized_guard(chat_id, platform)

        # Allow guards to bypass the "unregistered" trap
        if not active_profile and not is_guard:
            if text == "/register":
                self.registration_controller.start_registration(platform, chat_id)
            elif text == "/register_guard":
                if self.erp_client.is_authorized_guard(chat_id, platform):
                    Messenger.send(platform, chat_id, "✅ This device is already authorized for Gate Security.")
                    self.menu_controller.show_main_menu(platform, chat_id, active_profile)
            else:
                Messenger.send(platform, chat_id, "Please /register to use this bot.")
            return

        if text in ["/start", "/menu"]:
            self.menu_controller.show_main_menu(platform, chat_id, active_profile)
        elif text == "/profile":
            self.profile_controller.show_profile(platform, chat_id, active_profile)
        elif text == "/logout":
            if active_profile:
                self.profile_controller.process_logout(platform, chat_id, active_profile)
            elif self.erp_client.is_authorized_guard(chat_id, platform):
                Messenger.send(platform, chat_id, "🛡️ Security devices cannot log out via the bot. The Administrator must deactivate this device in the ERP Dashboard.", remove_keyboard=True)
            else:
                Messenger.send(platform, chat_id, "You are not currently logged in.")
            
        elif text in ["/edit_phone", "/clear_phone", "/edit_email"]:
            if active_profile and str(active_profile.telegram_chat_id) != str(chat_id):
                Messenger.send(platform, chat_id, "❌ Unauthorized action.")
            else:
                if text == "/edit_phone":
                    self.profile_controller.start_edit_phone(platform, chat_id, active_profile)
                elif text == "/clear_phone":
                    self.profile_controller.save_edited_field(platform, chat_id, active_profile, "phone", "")
                elif text == "/edit_email":
                    self.profile_controller.start_edit_field(platform, chat_id, "email")
                    
        elif text == "/raise_ticket":
            self.maintenance_controller.start_ticket_flow(platform, chat_id)
        
        elif text == "/my_tickets":
            self.maintenance_controller.show_active_tickets(platform, chat_id, active_profile, offset=0, status_filter="Open")
        elif text.startswith("/my_tickets_"):
            parts = text.split("_")
            offset = int(parts[2])
            status_filter = parts[3]
            self.maintenance_controller.show_active_tickets(platform, chat_id, active_profile, offset=offset, status_filter=status_filter)
        elif text.startswith("/view_"):
            ticket_name = text.split("_")[1].upper()
            self.maintenance_controller.view_ticket(platform, chat_id, ticket_name)
        elif text.startswith("/viewfile_"):
            file_name = text.split("_", 1)[1]
            self.maintenance_controller.view_file(platform, chat_id, file_name)
        elif text.startswith("/addfile_"):
            ticket_name = text.split("_")[1].upper()
            self.maintenance_controller.trigger_upload_prompt(platform, chat_id, ticket_name)
        # ... (scroll down to the command routing section)
        elif text == "/scan_qr":
            if not self.erp_client.is_authorized_guard(chat_id, platform):
                Messenger.send(platform, chat_id, "❌ Unauthorized.")
            else:
                self.gate_controller.handle_scan_prompt(platform, chat_id)
        
        elif text == "/tenant":
            if active_profile and str(active_profile.telegram_chat_id) != str(chat_id):
                Messenger.send(platform, chat_id, "❌ Tenant Management is available only to Flat Owners.")
            else:
                self.tenant_controller.show_management_menu(platform, chat_id, active_profile)

        elif text in ["/edit_tenant_phone", "/edit_tenant_email", "/extend_tenant", "/deactivate_tenant", "/previous_tenants", "/reactivate_tenant"]:
            if active_profile and str(active_profile.telegram_chat_id) != str(chat_id):
                Messenger.send(platform, chat_id, "❌ Unauthorized action. Only Flat Owners can manage tenants.")
            else:
                if text == "/edit_tenant_phone":
                    self.tenant_controller.start_edit(platform, chat_id, "phone")
                elif text == "/edit_tenant_email":
                    self.tenant_controller.start_edit(platform, chat_id, "email")
                elif text == "/extend_tenant":
                    self.tenant_controller.start_edit(platform, chat_id, "end_date")
                elif text == "/deactivate_tenant":
                    self.tenant_controller.confirm_deactivation(platform, chat_id)
                elif text == "/previous_tenants":
                    self.tenant_controller.show_previous_tenants(platform, chat_id, active_profile.flat_number)
                elif text == "/reactivate_tenant":
                    self.tenant_controller.process_reactivation(platform, chat_id, active_profile.flat_number)
        # --- Tenant Management Routing ---
        elif text == "/tenant_docs":
            if active_profile and str(active_profile.telegram_chat_id) != str(chat_id):
                Messenger.send(platform, chat_id, "❌ Unauthorized action.")
            else:
                # Pass the flat_number so the menu can query existing files
                self.tenant_controller.show_documents_menu(platform, chat_id, active_profile.flat_number)
        elif text == "/old_tdocs":
            if active_profile and str(active_profile.telegram_chat_id) != str(chat_id):
                Messenger.send(platform, chat_id, "❌ Unauthorized action.")
            else:
                self.tenant_controller.show_old_documents(platform, chat_id, active_profile.flat_number)        
        elif text.startswith("/v_tdoc_"):
            if active_profile and str(active_profile.telegram_chat_id) != str(chat_id):
                Messenger.send(platform, chat_id, "❌ Unauthorized action.")
            else:
                file_record = text.replace("/v_tdoc_", "")
                self.tenant_controller.view_tenant_document(platform, chat_id, file_record)
                
        elif text in ["/up_doc_rent", "/up_doc_pvc", "/up_doc_id", "/up_doc_photo"]:
            if active_profile and str(active_profile.telegram_chat_id) != str(chat_id):
                Messenger.send(platform, chat_id, "❌ Unauthorized action.")
            else:
                doc_type = text.replace("/up_doc_", "")
                self.tenant_controller.start_document_upload(platform, chat_id, doc_type)
                    
        elif text == "/add_tenant":
            if active_profile and str(active_profile.telegram_chat_id) != str(chat_id):
                Messenger.send(platform, chat_id, "❌ Unauthorized. Only Flat Owners can register a new tenant.")
            elif active_profile and active_profile.is_rented:
                Messenger.send(platform, chat_id, "❌ Flat is already rented.\n\nPlease go to /tenant and deactivate the current tenant before adding a new one.")
            else:
                self.tenant_controller.start_wizard(platform, chat_id, active_profile.flat_number)
                
        elif text == "/confirm_tenant":
            if current_session and current_session.get("module") == "add_tenant":
                self.tenant_controller.confirm_tenant(platform, chat_id, current_session)
        
       # Visitor Management Routing
        elif text.startswith("/visitors") or text == "/history":
            offset = int(text.split("_")[1]) if "_" in text else 0
            self.visitor_controller.view_history(platform, chat_id, active_profile.flat_number, offset)
        elif text.startswith("/vdate_"):
            selection = text.split("_")[1]
            self.visitor_controller.process_date_selection(platform, chat_id, selection)
        elif text == "/invite":
            self.visitor_controller.start_invite(platform, chat_id, active_profile.flat_number)
        elif text == "/notices":
            notices = self.erp_client.get_active_notices()
            if not notices:
                reply = "📋 *Notice Board*\n\nNo active announcements at this time."
            else:
                reply = "📋 *Notice Board & Circulars*\n\n"
                for n in notices:
                    reply += f"🗓️ _{n['date']}_ \n*📌 {n['title']}*\n{n['content']}\n\n--- \n\n"
            Messenger.send(platform, chat_id, reply, grid=[[{"🔙 Main Menu": "/menu"}]])
        elif text == "/dues":
            if not active_profile:
                Messenger.send(platform, chat_id, "❌ Profile not found.")
                return
            
            total_dues = self.erp_client.get_outstanding_dues(active_profile.flat_number)
            if total_dues > 0:
                msg = (f"📊 *Maintenance Dues Account*\n\n"
                       f"Flat Number: {active_profile.flat_number}\n"
                       f"Total Outstanding: *₹{total_dues:,.2f}*\n\n"
                       f"🔗 You can clear your balance via the digital desk portal or app payment links.")
            else:
                msg = f"📊 *Maintenance Dues Account*\n\n✅ Your account is fully settled. No outstanding dues found!"
                
            Messenger.send(platform, chat_id, msg, grid=[[{"🔙 Main Menu": "/menu"}]])
        elif text == "/book_facility":
            if not active_profile:
                Messenger.send(platform, chat_id, "❌ Register profiles before booking facilities.")
                return
            self.facility_controller.start_booking_flow(platform, chat_id)
        else:
            if not text.startswith("/"):
                Messenger.send(platform, chat_id, "I didn't understand that command. Try /menu.")

    def _extract_id_from_text(self, text: str):
        for line in text.splitlines():
            if line.startswith("ID: "):
                return line.replace("ID: ", "").strip()
        return None