from services.messenger import Messenger
from conversation.session import SessionManager
from api.erp import ERPClient
from datetime import datetime
import qrcode
import io

class VisitorController:
    def __init__(self, erp_client: ERPClient, session_manager: SessionManager):
        self.erp = erp_client
        self.session = session_manager

    # --- INVITATION WIZARD ---

    def start_invite(self, platform: str, chat_id: str, resident_flat: str):
        """Step 1: Ask for name, share contact, or pick quick options."""
        self.session.update_session(chat_id, step="awaiting_name", module="visitor", data={"flat": resident_flat})
        
        # Build dynamic grid with Quick Delivery and Frequent Visitors
        freq_visitors = self.erp.get_frequent_visitors(resident_flat)
        grid = [[{"📦 Quick Delivery (Today)": "/vquick_del"}]]
        
        row = []
        for v in freq_visitors:
            safe_v = v.replace(" ", "_")[:20] # Ensure safe callback format
            row.append({f"👤 {v}": f"/vfreq_{safe_v}"})
            if len(row) == 2:
                grid.append(row)
                row = []
        if row: grid.append(row)
        grid.append([{"🔙 Main Menu": "/menu"}])

        Messenger.send(
            platform, chat_id, 
            "✉️ *Pre-Approve a Visitor*\n\nEnter Name, share a Contact from your phonebook, or pick an option below:", 
            grid=grid
        )

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
            
            grid = [
                [{"🤝 Guest": "/vpurp_Guest"}, {"🛠️ Service": "/vpurp_Service"}],
                [{"🧹 Maid": "/vpurp_Maid"}, {"🚕 Taxi": "/vpurp_Taxi"}],
                [{"🔙 Main Menu": "/menu"}]
            ]
            Messenger.send(platform, chat_id, f"What is the purpose of *{name}*'s visit?", grid=grid)
            return

        elif current_step == "awaiting_purpose":
            session_data["purpose"] = text.replace("/vpurp_", "") if text.startswith("/vpurp_") else "Guest"
            self.session.update_session(chat_id, step="awaiting_date", module="visitor", data=session_data)
            
            grid = [
                [{"📅 Today": "/vdate_today"}, {"📆 Tomorrow": "/vdate_tomorrow"}],
                [{"🗓️ Multi-Day Pass": "/vdate_multi"}],
                [{"🔙 Main Menu": "/menu"}]
            ]
            Messenger.send(platform, chat_id, "When are they expected to arrive?", grid=grid)
            return

        elif current_step == "awaiting_date":
            date_sel = text.replace("/vdate_", "")
            if date_sel == "multi":
                self.session.update_session(chat_id, step="awaiting_end_date", module="visitor", data=session_data)
                grid = [[{"+ 3 Days": "/vend_3days"}, {"+ 1 Week": "/vend_1week"}], [{"🔙 Main Menu": "/menu"}]]
                Messenger.send(platform, chat_id, "How long will they be staying?", grid=grid)
            else:
                session_data["date"] = date_sel
                self.session.update_session(chat_id, step="awaiting_vehicle", module="visitor", data=session_data)
                Messenger.send(platform, chat_id, "🚗 Enter Vehicle Number (or click Skip):", grid=[[{"⏭️ Skip": "/vveh_skip"}], [{"🔙 Main Menu": "/menu"}]])
            return
            
        elif current_step == "awaiting_end_date":
            session_data["date"] = "today" 
            session_data["end_date"] = text.replace("/vend_", "")
            self.session.update_session(chat_id, step="awaiting_vehicle", module="visitor", data=session_data)
            Messenger.send(platform, chat_id, "🚗 Enter Vehicle Number (or click Skip):", grid=[[{"⏭️ Skip": "/vveh_skip"}], [{"🔙 Main Menu": "/menu"}]])
            return

        elif current_step == "awaiting_vehicle":
            vehicle = "" if text == "/vveh_skip" else text.strip()
            self.process_final_creation(
                platform, chat_id, session_data["flat"], session_data["visitor_name"], 
                session_data.get("date", "today"), session_data.get("purpose", "Guest"), vehicle, session_data.get("end_date", "")
            )

    def process_final_creation(self, platform, chat_id, resident_flat, visitor_name, date_sel, purpose, vehicle="", end_date=""):
        """Centralized method to hit ERPNext, generate a QR code, and display the result."""
        result = self.erp.create_preapproved_visitor(resident_flat, visitor_name, date_sel, purpose, vehicle, end_date)
        
        if result.get("success"):
            passcode = result.get("passcode")
            
            # 👇 Generate the Telegram Deep Link tailored specifically to your bot 👇
            deep_link = f"https://t.me/kvciii_bot?start=verify_{passcode}"
            
            # Create QR Code image in memory
            qr = qrcode.QRCode(version=1, box_size=10, border=2)
            qr.add_data(deep_link)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            
            bio = io.BytesIO()
            img.save(bio, 'PNG')
            bio.seek(0)
            
            # Construct the visually clean caption
            msg = (f"✅ *Visitor Gate Pass*\n\n"
                   f"👤 *Name:* {visitor_name}\n"
                   f"🔖 *Purpose:* {purpose}\n")
            if vehicle: msg += f"🚗 *Vehicle:* {vehicle}\n"
            msg += (f"📅 *Entry:* {date_sel.title()}\n"
                   f"🏠 *Host:* {resident_flat}\n\n"
                   f"📲 *Forward this QR Code to your guest.* They just need to flash it at the gate!")
                   
            # Send via your universal messenger
            Messenger.send_photo(platform, chat_id, bio, caption=msg, grid=[[{"🔙 Main Menu": "/menu"}]])
            
        else:
            Messenger.send(platform, chat_id, f"❌ Failed. Error:\n`{result.get('error')[:200]}`", grid=[[{"🔙 Main Menu": "/menu"}]])
        
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
                
                # Determine Status Display
                if raw_status.lower() == "entered":
                    status_display = "✅ Visited (Inside)"
                elif raw_status.lower() == "approved":
                    status_display = "⏳ Expected (Pre-Approved)"
                elif raw_status.lower() == "denied":
                    status_display = "🚫 Denied Entry"
                else:
                    status_display = f"🚦 {raw_status}"

                # Parse Creation Date
                raw_creation = log.get('creation', '')
                try:
                    clean_date = raw_creation.split(".")[0] 
                    dt_obj = datetime.strptime(clean_date, "%Y-%m-%d %H:%M:%S")
                    formatted_creation = dt_obj.strftime("%d %b %Y, %I:%M %p")
                except:
                    formatted_creation = str(raw_creation).split(" ")[0] if raw_creation else "N/A"
                    
                # Parse Expected Date
                formatted_expected = None
                if expected_date:
                    try:
                        exp_dt = datetime.strptime(str(expected_date), "%Y-%m-%d")
                        formatted_expected = exp_dt.strftime("%d %b %Y")
                    except:
                        formatted_expected = str(expected_date)

                reply += f"👤 *{log.get('visitor_name', 'Unknown')}* ({log.get('entry_type', '')})\n"
                
                # 👇 Display Logic: Show Expected Date if they haven't arrived yet 👇
                if formatted_expected and raw_status.lower() == "approved":
                    reply += f"   📆 *Expected On:* {formatted_expected}\n"
                else:
                    reply += f"   🗓️ *Entry/Created:* {formatted_creation}\n"
                    
                reply += f"   {status_display}\n\n"
                
        # Pagination row
        btns = []
        btns.append({"⬅️ Previous Week": f"/visitors_{offset + 1}"})
        if offset > 0: 
            btns.append({"Next Week ➡️": f"/visitors_{offset - 1}" if offset > 1 else "/history"})
            
        grid = [
            btns, 
            [{"🔙 Main Menu": "/menu"}]
        ]
            
        Messenger.send(platform, chat_id, reply, grid=grid)