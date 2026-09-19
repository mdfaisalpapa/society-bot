from services.messenger import Messenger
from conversation.session import SessionManager
from api.erp import ERPClient
from datetime import datetime
from utils.keyboard import KeyboardBuilder
import qrcode
import io
from utils.logger import app_logger
import random
import requests
        

class VisitorController:
    def __init__(self, erp_client: ERPClient, session_manager: SessionManager):
        self.erp = erp_client
        self.session = session_manager

    # --- INVITATION WIZARD ---

    def start_invite(self, platform: str, chat_id: str, resident_flat: str):
        from utils.keyboard import KeyboardBuilder
        self.session.update_session(chat_id, step="awaiting_name", module="visitor", data={"flat": resident_flat})
        freq_visitors = self.erp.get_frequent_visitors(resident_flat)
        Messenger.send(platform, chat_id, "✉️ *Pre-Approve a Visitor*\n\nEnter Name, share a Contact from your phonebook, or pick an option below:", inline_keyboard=KeyboardBuilder.visitor_invite_grid(freq_visitors))

    def handle_wizard_reply(self, platform: str, chat_id: str, text: str, session_data: dict, current_step: str, contact_data: dict = None):
        """Routes the user's text based on their current step in the wizard."""
        
        if current_step == "awaiting_name":
            # 1. Delivery Bypass (Instant Pass)
            if text == "/vquick_del":
                self.process_final_creation(platform, chat_id, session_data["flat"], "Delivery Agent", "today", "Delivery")
                return

            # 2. Extract Name (From Contact, Frequent Button, or Text)
            if contact_data:
                name = contact_data.get("first_name", "")
                if contact_data.get("last_name"): name += " " + contact_data.get("last_name")
            elif text.startswith("/vfreq_"):
                name = text.replace("/vfreq_", "").replace("_", " ")
            else:
                name = text.strip()

            session_data["visitor_name"] = name
            self.session.update_session(chat_id, step="awaiting_purpose", module="visitor", data=session_data)
            
            Messenger.send(platform, chat_id, f"What is the purpose of *{name}*'s visit?", inline_keyboard=KeyboardBuilder.visitor_purpose_grid())
            return

        elif current_step == "awaiting_purpose":
            session_data["purpose"] = text.replace("/vpurp_", "") if text.startswith("/vpurp_") else "Guest"
            self.session.update_session(chat_id, step="awaiting_date", module="visitor", data=session_data)
            
            Messenger.send(platform, chat_id, "When are they expected to arrive?", inline_keyboard=KeyboardBuilder.visitor_date_grid())
            return

        elif current_step == "awaiting_date":
            date_sel = text.replace("/vdate_", "")
            if date_sel == "multi":
                self.session.update_session(chat_id, step="awaiting_end_date", module="visitor", data=session_data)
                Messenger.send(platform, chat_id, "How long will they be staying?", inline_keyboard=KeyboardBuilder.visitor_duration_grid())
            else:
                session_data["date"] = date_sel
                if session_data.get("purpose", "").lower() == "delivery":
                    self.process_final_creation(
                        platform, chat_id, session_data["flat"], session_data["visitor_name"], 
                        session_data.get("date", "today"), session_data.get("purpose", "Guest"), "", session_data.get("end_date", "")
                    )
                else:
                    self.session.update_session(chat_id, step="awaiting_vehicle", module="visitor", data=session_data)
                    Messenger.send(platform, chat_id, "🚗 Enter Vehicle Number (or click Skip):", inline_keyboard=KeyboardBuilder.visitor_vehicle_skip_grid())
            return
            
        elif current_step == "awaiting_end_date":
            session_data["date"] = "today" 
            session_data["end_date"] = text.replace("/vend_", "")
            if session_data.get("purpose", "").lower() == "delivery":
                self.process_final_creation(
                    platform, chat_id, session_data["flat"], session_data["visitor_name"], 
                    session_data.get("date", "today"), session_data.get("purpose", "Guest"), "", session_data.get("end_date", "")
                )
            else:
                self.session.update_session(chat_id, step="awaiting_vehicle", module="visitor", data=session_data)
                Messenger.send(platform, chat_id, "🚗 Enter Vehicle Number (or click Skip):", inline_keyboard=KeyboardBuilder.visitor_vehicle_skip_grid())
            return

        elif current_step == "awaiting_vehicle":
            vehicle = "" if text == "/vveh_skip" else text.strip()
            self.process_final_creation(
                platform, chat_id, session_data["flat"], session_data["visitor_name"], 
                session_data.get("date", "today"), session_data.get("purpose", "Guest"), vehicle, session_data.get("end_date", "")
            )

    def process_final_creation(self, platform, chat_id, resident_flat, visitor_name, date_sel, purpose, vehicle="", end_date=""):
        """Centralized method to hit ERPNext, generate a QR code locally, and display the result."""
        import qrcode
        import io
        import urllib.parse
        from datetime import datetime, timedelta
        
        final_end_date = end_date if end_date else date_sel
        result = self.erp.create_preapproved_visitor(resident_flat, visitor_name, date_sel, purpose, vehicle, end_date)
        
        if result.get("success"):
            passcode = result.get("passcode")
            
            # 1. Format the actual display date
            if date_sel.lower() == "today":
                display_date = datetime.now().strftime("%d %b %Y")
            elif date_sel.lower() == "tomorrow":
                display_date = (datetime.now() + timedelta(days=1)).strftime("%d %b %Y")
            else:
                display_date = date_sel.title()

            # Generate QR Code locally for the Telegram display
            qr_data = f"verify_{passcode}"
            qr = qrcode.QRCode(version=1, box_size=10, border=2)
            qr.add_data(qr_data)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            
            # ... (Inside process_final_creation)
            
            # ... (Inside process_final_creation)
            
            bio = io.BytesIO()
            img.save(bio, 'PNG')
            bio.seek(0)
            
            # 👇 1. Fetch the public URL from your environment variables
            import os
            public_erp_url = os.getenv("PUBLIC_ERP_URL")
            
                
            # 👇 2. Construct the URL pointing to the function you just created
            qr_url = f"{public_erp_url.rstrip('/')}/api/method/society_erp.api.generate_qr?passcode={passcode}"
            
            # 3. Construct the WhatsApp message using the new display_date
            pass_details = (
                f"🏢 *KVC-III Gate Pass*\n\n"
                f"👤 Visitor: {visitor_name}\n"
                f"🏠 Host: Flat {resident_flat}\n"
                f"📅 Entry: {display_date}\n"
            )
         
            if vehicle: 
                pass_details += f"🚗 Vehicle: {vehicle}\n"
            
            pass_details += f"\n🎟️ Passcode: {passcode}\n\n"
            pass_details += f"📱 Tap link below to view QR Code for the gate:\n{qr_url}"

            # 4. Create WhatsApp Share Link (Raw string addition)
            encoded_text = urllib.parse.quote(pass_details)
            base_url = "https://api.whatsapp.com/send?text="
            wa_link = base_url + encoded_text
            
            # 5. Telegram Message Caption
            msg = (f"✅ *Visitor Gate Pass Generated!*\n\n"
                   f"Tap the **Share on WhatsApp** button below. It will automatically draft a message containing the pass details and a link to this QR code for your guest!")
            
            # 6. Build Keyboard
            keyboard = [
                [{"text": "💬 Share Pass & QR on WhatsApp", "url": wa_link}],
                [{"text": "🔙 Main Menu", "callback_data": "/menu"}]
            ]
                   
            Messenger.send_photo(platform, chat_id, bio, caption=msg, inline_keyboard=keyboard)
            
        else:
            Messenger.send(platform, chat_id, f"❌ Failed. Error:\n`{result.get('error')[:200]}`", inline_keyboard=[[{"text": "🔙 Main Menu", "callback_data": "/menu"}]])
        
        self.session.clear_session(chat_id)
    # --- HISTORY MODULE ---

    def view_history(self, platform: str, chat_id: str, resident_flat: str, offset: int = 0):
        """Displays visitor history with pagination, timestamps, and visit status."""
        logs = self.erp.get_visitor_history(resident_flat, offset)
        
        reply = f"📋 *Visitor History (Week -{offset})*\n\n"
        
        if not logs:
            reply += "No visitors found for this period."
        else:
            for log in logs:
                raw_status = log.get('status', 'Unknown')
                expected_date = log.get('expected_date')
                
                if raw_status.lower() == "entered":
                    status_display = "✅ Visited (Inside)"
                elif raw_status.lower() == "approved":
                    status_display = "⏳ Expected (Pre-Approved)"
                elif raw_status.lower() == "denied":
                    status_display = "🚫 Denied Entry"
                else:
                    status_display = f"🚦 {raw_status}"

                raw_creation = log.get('creation', '')
                try:
                    clean_date = raw_creation.split(".")[0] 
                    dt_obj = datetime.strptime(clean_date, "%Y-%m-%d %H:%M:%S")
                    formatted_creation = dt_obj.strftime("%d %b %Y, %I:%M %p")
                except:
                    formatted_creation = str(raw_creation).split(" ")[0] if raw_creation else "N/A"
                    
                formatted_expected = None
                if expected_date:
                    try:
                        exp_dt = datetime.strptime(str(expected_date), "%Y-%m-%d")
                        formatted_expected = exp_dt.strftime("%d %b %Y")
                    except:
                        formatted_expected = str(expected_date)

                reply += f"👤 *{log.get('visitor_name', 'Unknown')}* ({log.get('entry_type', '')})\n"
                
                if formatted_expected and raw_status.lower() == "approved":
                    reply += f"   📆 *Expected On:* {formatted_expected}\n"
                else:
                    reply += f"   🗓️ *Entry/Created:* {formatted_creation}\n"
                    
                reply += f"   {status_display}\n\n"
                
        btns = []
        btns.append({"⬅️ Previous Week": f"/visitors_{offset + 1}"})
        if offset > 0: 
            btns.append({"Next Week ➡️": f"/visitors_{offset - 1}" if offset > 1 else "/history"})
            
        Messenger.send(platform, chat_id, reply, inline_keyboard=KeyboardBuilder.visitor_history_grid(offset))