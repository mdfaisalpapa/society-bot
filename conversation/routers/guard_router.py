from utils.logger import app_logger
from services.messenger import Messenger
# 👇 NEW IMPORTS HERE 👇
from utils.keyboard import KeyboardBuilder


class GuardRouter:
    def __init__(self, erp_client, gate_controller, session_manager):
        self.erp = erp_client
        self.gate_controller = gate_controller
        self.session = session_manager

    def handle(self, platform, chat_id, text, message, current_session, active_profile):
        from utils.logger import app_logger
        is_guard = self.erp.is_authorized_guard(chat_id, platform)

        # 👇 1. INTERCEPT NATIVE WEB APP DATA
        if message and message.get("web_app_data"):
            # This directly grabs the "verify_TC2-110_66670" string!
            text = message["web_app_data"]["data"]
        # 👇 1. SANITIZE DEEP LINKS INSTANTLY
        if text and text.startswith("/start verify_"):
            text = text.replace("/start ", "")

        # 👇 2. ADD "verify_" TO THE SECURE COMMANDS LIST
        # (This ensures manually typed passcodes are still protected by the is_guard check)
        guard_commands = ("/start verify_", "verify_", "/scan_qr", "/staff_in", "/staff_out", "/guard_walkin")
        
        if text and str(text).startswith(guard_commands) or current_session.get("module") == "guard_walkin":
            if not is_guard:
                Messenger.send(platform, chat_id, "❌ *Unauthorized Device.* Access denied.")
                return True
        # 👇 NEW: Registration Discovery Command (Left open to everyone)
        if text == "/register_guard":
            Messenger.send(
                platform, 
                chat_id, 
                f"📋 *Guard Registration Helper*\n\n"
                f"Your Chat ID is: `{chat_id}`\n\n"
                f"Please provide this ID to your Administrator to enable your device in the system."
            )
            return True

        # ... (Your existing logic continues below) ...
            
        # 1. QR Code Upload Processing
        if message and message.get("photo") and current_session.get("module") != "guard_walkin":
            app_logger.info(f"Guard {chat_id} uploaded a QR code photo.") # 🪵 LOGGING ADDED
            file_id = message.get("photo")[-1].get("file_id")
            self.gate_controller.process_qr_image(platform, chat_id, message, file_id)
            return True

        # ==========================================
        # 2. DOMESTIC STAFF SCANNER (Check this FIRST!)
        # ==========================================
        if text.startswith("verify_staff_"):
            staff_id = text.split("verify_staff_")[1]
            result = self.erp.verify_staff_pass(staff_id)
            scan_loop_keyboard = KeyboardBuilder.scanner_loop()
            
            if result.get("success"):
                staff_name = result.get('staff_name')
                role = result.get('role')
                linked_flats = result.get('flats', [])
                
                # 1. Show Success to Guard
                flats_str = ", ".join(linked_flats) if linked_flats else "None"
                success_msg = (f"✅ *STAFF ACCESS GRANTED*\n\n"
                               f"👤 *Name:* {staff_name}\n"
                               f"🛠 *Role:* {role}\n"
                               f"🏠 *Authorized Flats:* {flats_str}")
                Messenger.send(platform, chat_id, success_msg, inline_keyboard=scan_loop_keyboard)
                
                # 2. Notify Every Linked Resident
                for flat in linked_flats:
                    notify_chat_ids = self.erp.get_notification_chat_ids(flat)
                    for notify_chat in notify_chat_ids:
                        if notify_chat:
                            # 👇 ADDED: (ID: {staff_id})
                            notify_msg = (f"🔔 *Staff Arrival*\n\n"
                                          f"Your {role}, *{staff_name}* (ID: {staff_id}), has just checked in at the gate.")
                            Messenger.send(platform, notify_chat, notify_msg)
            else:
                # 1. Show Error to Guard
                error_msg = f"❌ *ACCESS DENIED*\n\n{result.get('error')}"
                Messenger.send(platform, chat_id, error_msg, inline_keyboard=scan_loop_keyboard)
                
                # 👇 NEW: Security Alert for Residents 👇
                status = result.get('status')
                linked_flats = result.get('flats', [])
                
                # If they are explicitly blacklisted, alert the linked flats
                if status == "Blacklisted" and linked_flats:
                    staff_name = result.get('staff_name', 'A staff member')
                    
                    for flat in linked_flats:
                        notify_chat_ids = self.erp.get_notification_chat_ids(flat)
                        for notify_chat in notify_chat_ids:
                            if notify_chat:
                                # 👇 ADDED: 🆔 *ID:* {staff_id}
                                alert_msg = (f"🚨 *SECURITY ALERT*\n\n"
                                             f"An access attempt was just blocked at the gate.\n\n"
                                             f"👤 *Name:* {staff_name}\n"
                                             f"🆔 *ID:* {staff_id}\n"
                                             f"❌ *Reason:* Profile is marked as Blacklisted.")
                                Messenger.send(platform, notify_chat, alert_msg)
            
            return True
        

        # Add this block to GuardRouter.handle in guard_router.py
        if text.startswith("verify_worker_"):
            worker_pass_id = text.split("verify_worker_")[1]
            result = self.erp.verify_worker_pass(worker_pass_id)
            scan_loop_keyboard = KeyboardBuilder.scanner_loop()
    
            if result.get("success"):
                worker_name = result.get('worker_name')
                flat = result.get('resident_flat')
        
                # 1. Success Message to Guard
                Messenger.send(platform, chat_id, f"✅ *WORKER ACCESS GRANTED*\n\n👤 *Name:* {worker_name}", inline_keyboard=scan_loop_keyboard)
        
                # 2. Notify the Resident (Reusing your Staff notification logic)
                notify_chat_ids = self.erp.get_notification_chat_ids(flat)
                for notify_chat in notify_chat_ids:
                    Messenger.send(platform, notify_chat, f"🔔 *Worker Arrival*\nYour worker *{worker_name}* has just checked in.")
            else:
                # 3. Error Message to Guard
                Messenger.send(platform, chat_id, f"❌ *ACCESS DENIED*\n\n{result.get('error')}", inline_keyboard=scan_loop_keyboard)
    
            return True

        ## ==========================================
        # 3. WORKER PASS SCANNER (Mirrors Staff Logic)
        # ==========================================
        elif text.startswith("verify_WP-PASS"):
            worker_pass_id = text.split("verify_")[1]
            result = self.erp.work_permit.verify_worker_pass(worker_pass_id)
            scan_loop_keyboard = KeyboardBuilder.scanner_loop()
            
            if result.get("success"):
                worker_name = result.get('worker_name')
                flat = result.get('flat') # Fetched from the API
                
                # 1. Success Message to Guard
                success_msg = (f"✅ *WORKER ACCESS GRANTED*\n\n"
                               f"👤 *Name:* {worker_name}\n"
                               f"🏠 *Authorized Flat:* {flat}")
                Messenger.send(platform, chat_id, success_msg, inline_keyboard=scan_loop_keyboard)
                
                # 2. Notify the Resident (Identical to Domestic Staff notification)
                if flat:
                    notify_chat_ids = self.erp.get_notification_chat_ids(flat)
                    for notify_chat in notify_chat_ids:
                        if notify_chat:
                            notify_msg = (f"🔔 *Worker Arrival*\n\n"
                                          f"Your authorized worker, *{worker_name}*, has just checked in at the gate.")
                            Messenger.send(platform, notify_chat, notify_msg)
            else:
                # Show Error to Guard
                error_msg = f"❌ *ACCESS DENIED*\n\n{result.get('error')}"
                Messenger.send(platform, chat_id, error_msg, inline_keyboard=scan_loop_keyboard)
            
            return True

        # ==========================================
        # 4. VISITOR SCANNER
        # ==========================================
        elif text.startswith("verify_"):
            passcode = text.split("verify_")[1]
            result = self.erp.verify_visitor_passcode(passcode)
            
            # 👇 CHANGED HERE: Using KeyboardBuilder instead of hardcoded dictionary 👇
            scan_loop_keyboard = KeyboardBuilder.scanner_loop()
            
            if result.get("success"):
                app_logger.info(f"Passcode {passcode} verified successfully.") # 🪵 LOGGING ADDED
                success_msg = (f"✅ *ACCESS GRANTED*\n\n👤 *Visitor:* {result['visitor_name']}\n"
                               f"🏠 *Going to:* {result['resident']}\n🚗 *Vehicle:* {result.get('vehicle', 'N/A')}\n\n"
                               f"_Visitor has been automatically logged as 'Entered'._")
                Messenger.send(platform, chat_id, success_msg, inline_keyboard=scan_loop_keyboard)
                
                # 👇 NEW: Smart Multi-Resident Notification 👇
                resident_flat = result.get('resident')
                host_chat_id = result.get('host_chat_id')
                app_logger.info(f"DEBUG: Extracted resident_flat: '{resident_flat}', host_chat_id: '{host_chat_id}'")
                
                if resident_flat:
                    # 1. Fetch all applicable residents for the flat (Owners & Tenants)
                    notify_chat_ids = self.erp.get_notification_chat_ids(resident_flat)
                    app_logger.info(f"DEBUG: Fetched notify_chat_ids from API: {notify_chat_ids}")
                    
                    # 2. Ensure the person who generated the pass ALWAYS gets the notification
                    if host_chat_id and host_chat_id not in notify_chat_ids:
                        notify_chat_ids.append(host_chat_id)
                        
                    app_logger.info(f"DEBUG: Final list of Chat IDs to notify: {notify_chat_ids}")
    
                    # 3. Send the notification to everyone in the final list
                    for chat_id_notify in notify_chat_ids:
                        if chat_id_notify:
                            notify_msg = (f"🔔 *Visitor Arrival*\n\n"
                                          f"Your visitor *{result['visitor_name']}* has just arrived at the gate "
                                          f"and has been granted access.")
                            app_logger.info(f"DEBUG: Attempting to send message to chat_id: {chat_id_notify}")
                            Messenger.send(platform, chat_id_notify, notify_msg)
            else:
                app_logger.error(f"Passcode {passcode} denied: {result.get('error')}") # 🪵 LOGGING ADDED
                error_msg = f"❌ *ACCESS DENIED*\n\n{result.get('error')}"
                Messenger.send(platform, chat_id, error_msg, inline_keyboard=scan_loop_keyboard)
            return True
       
        if text == "/scan_qr":
            self.gate_controller.handle_scan_prompt(platform, chat_id)
            return True

        # 2.5 Staff Operations (New)
        if text.startswith("/staff_in ") or text.startswith("/staff_out "):
            Messenger.send(platform, chat_id, "❌ Unauthorized.")
            return True
            
            parts = text.split(" ")
            if len(parts) < 2:
                Messenger.send(platform, chat_id, "❌ Usage: /staff_in <staff_id>")
                return True
                
            # Maps to the controller method we just discussed
            entry_type = "Entry" if parts[0] == "/staff_in" else "Exit"
            self.gate_controller.process_staff_scan(platform, chat_id, parts[1], entry_type)
            return True

        # 3. Walk-in Operations
        if text == "/guard_walkin":
            self.session.update_session(chat_id, module="guard_walkin", step="awaiting_flat", data={})
            Messenger.send(platform, chat_id, "🚶 *Walk-in Registration*\n\nEnter the target Flat Number (e.g., TC2-110):")
            return True

        if text.startswith("w_app_") or text.startswith("w_den_"):
            action, log_id, guard_id, target_flat = text.split("_")[0], text.split("_")[2], text.split("_")[3], text.split("_")[4]
            if action == "w": 
                self.erp.update_visitor_status(log_id, "Approved")
                Messenger.send(platform, chat_id, "✅ You approved entry for this visitor.")
                Messenger.send(platform, guard_id, f"✅ *Walk-in Approved* for Flat {target_flat}. You can open the gate.")
            else: 
                self.erp.update_visitor_status(log_id, "Deny")
                Messenger.send(platform, chat_id, "❌ You denied entry for this visitor.")
                Messenger.send(platform, guard_id, f"🛑 *Walk-in DENIED* for Flat {target_flat}. Turn the visitor back.")
            return True

        # 4. Walk-in Wizard Session
        if current_session and current_session.get("module") == "guard_walkin":
            step = current_session.get("step")
            session_data = current_session.get("data", {})
            
            if step == "awaiting_flat":
                if not text:
                    Messenger.send(platform, chat_id, "❌ Please type the Flat Number first.")
                    return True
                clean_flat = text.upper().strip()
                
                # 👇 CHANGED: Fetch ALL applicable residents (Owner/Tenant + Family)
                notify_chat_ids = self.erp.get_notification_chat_ids(clean_flat)
                if not notify_chat_ids:
                    Messenger.send(platform, chat_id, "❌ Invalid Flat Number or no registered residents found.")
                    return True
                    
                session_data["flat"] = clean_flat 
                # Save the whole list into the session
                session_data["notify_chat_ids"] = notify_chat_ids 
                self.session.update_session(chat_id, module="guard_walkin", step="awaiting_purpose", data=session_data)
                
                # 🔄 DYNAMIC FETCH: Pull Purpose using KeyboardBuilder
                purpose_keyboard = KeyboardBuilder.walkin_purpose()                
                Messenger.send(
                    platform, 
                    chat_id, 
                    f"✅ Flat {clean_flat} Verified.\n\nWhat is the purpose of the visit?", 
                    inline_keyboard=purpose_keyboard
                )
                
            elif step == "awaiting_purpose":
                if not text.startswith("wpurp_"):
                    Messenger.send(platform, chat_id, "❌ Please select an option.")
                    return True
                session_data["purpose"] = text.split("_")[1]
                self.session.update_session(chat_id, module="guard_walkin", step="awaiting_photo_or_name", data=session_data)
                Messenger.send(platform, chat_id, f"✅ Purpose: {session_data['purpose']}\n\n📸 *Snap a live photo* of the visitor, OR type their name:")
                
            elif step == "awaiting_photo_or_name":
                flat = session_data["flat"]
                purpose = session_data.get("purpose", "Guest")
                visitor_identifier = text.strip() if text else "Walk-in Visitor"
                photo_id = message.get("photo")[-1].get("file_id") if message.get("photo") else None
                
                if not photo_id and not text:
                    Messenger.send(platform, chat_id, "❌ Please send a photo or type a name.")
                    return True
                
                log_id = self.erp.create_walkin_visitor(flat, visitor_identifier, purpose)
                purpose_emoji = {"Delivery": "📦", "Cab": "🚕", "Service": "🛠️", "Guest": "🤝"}.get(purpose, "👤")
                
                # 1. LOOP ALL RESIDENTS: Send the Walk-in Approval Alert to everyone
                for res_chat_id in session_data["notify_chat_ids"]:
                    resident_keyboard = KeyboardBuilder.walkin_approval(log_id, chat_id, flat)
                    
                    if photo_id:
                        import io, requests
                        file_url = Messenger.get_file_url(platform, photo_id)
                        if file_url:
                            photo_bytes = io.BytesIO(requests.get(file_url).content)
                            photo_bytes.name = "visitor.jpg"
                            Messenger.send_photo(platform, res_chat_id, photo_bytes, caption=f"🔔 *Gate Security Alert*\nA {purpose_emoji} *{purpose}* is at the gate requesting entry.", inline_keyboard=resident_keyboard)
                        else:
                            Messenger.send(platform, res_chat_id, f"🔔 *Gate Security Alert*\nA {purpose_emoji} *{purpose}* is at the gate requesting entry. (Photo capture failed)", inline_keyboard=resident_keyboard)
                    else:
                        Messenger.send(platform, res_chat_id, f"🔔 *Gate Security Alert*\nA {purpose_emoji} *{purpose}* named *{visitor_identifier}* is at the gate requesting entry.", inline_keyboard=resident_keyboard)
                
                app_logger.info(f"Walk-in pass {log_id} generated for {flat} by guard {chat_id}")
                
                # 2. HYBRID ROUTING LOGIC: Build a multi-resident call list for the guard
                call_keyboard = []
                msg_text = "⏳ Details pushed to all residents. Awaiting approval..."
                has_phone = False
                
                for res_chat_id in session_data["notify_chat_ids"]:
                    profile = self.erp.get_profile_by_chat_id(res_chat_id)
                    
                    if profile:
                        role = getattr(profile, 'role', 'Resident')
                        username = getattr(profile, 'telegram_username', None)
                        
                        # Extract the exact name based on their profile role
                        if role == 'Owner':
                            res_name = getattr(profile, 'owner_name', 'Owner')
                        elif role == 'Tenant':
                            res_name = getattr(profile, 'tenant_name', 'Tenant')
                        elif role == 'Family':
                            res_name = getattr(profile, 'member_name', 'Family Member')
                        else:
                            res_name = getattr(profile, 'name', 'Resident')
                        
                        # Fetch the button row and URL from KeyboardBuilder
                        btn_row = KeyboardBuilder.guard_call_resident_telegram(res_chat_id, username)[0]
                        
                        # 👇 NEW: Completely override the button text to show Name + Role
                        btn_row[0]['text'] = f"📞 Call {res_name} ({role})"
                        
                        call_keyboard.append(btn_row)
                        
                        # Optional Cellular Backup
                        #active_phone = getattr(profile, 'active_phone', None)
                        #if active_phone:
                         #   if not has_phone:
                          #      msg_text += "\n\n*Backup Cellular Contacts:*"
                           #     has_phone = True
                            # 👇 NEW: Also show the name in the cellular backup text
                            #msg_text += f"\n📞 {res_name} ({role}): {active_phone}"
                            
                Messenger.send(
                    platform, 
                    chat_id, 
                    msg_text, 
                    inline_keyboard=call_keyboard if call_keyboard else None
                )
                    
                self.session.clear_session(chat_id)
            return True
            
        return False