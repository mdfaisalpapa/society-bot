from services.messenger import Messenger
from conversation.session import SessionManager
from api.erp import ERPClient
from datetime import datetime

class FacilityController:
    def __init__(self, erp_client: ERPClient, session_manager: SessionManager):
        self.erp = erp_client
        self.session = session_manager

    def start_booking_flow(self, platform: str, chat_id: str):
        """Step 1: Present available assets."""
        self.session.update_session(chat_id, step="awaiting_facility_selection", module="facility", data={})
        
        grid = [
            [{"text": "🏛️ Community Hall", "callback_data": "/fac_Hall"}],
            [{"text": "🏸 Badminton Court", "callback_data": "/fac_Court"}],
            [{"text": "🔙 Main Menu", "callback_data": "/menu"}]
        ]
        Messenger.send(platform, chat_id, "🏛️ *Facility Reservation*\n\nSelect the facility you want to reserve:", inline_keyboard=grid)

    def handle_wizard(self, platform: str, chat_id: str, text: str, step: str, session_data: dict, flat_number: str):
        """Processes steps sequentially to book a facility safely."""
        
        if step == "awaiting_facility_selection":
            facility_type = "Community Hall" if "Hall" in text else "Badminton Court"
            session_data["facility"] = facility_type
            
            self.session.update_session(chat_id, step="awaiting_booking_date", module="facility", data=session_data)
            Messenger.send(platform, chat_id, f"Selected: *{facility_type}*\n\nPlease enter the target reservation date in *YYYY-MM-DD* format (e.g., 2026-08-15):")
            return

        elif step == "awaiting_booking_date":
            date_str = text.strip()
            
            # Basic structural format verification
            try:
                target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                if target_date < datetime.now().date():
                    Messenger.send(platform, chat_id, "❌ You cannot select a date in the past. Please enter a valid future date:")
                    return
            except ValueError:
                Messenger.send(platform, chat_id, "❌ Invalid date format. Please look closely at the format and re-enter using *YYYY-MM-DD*:")
                return

            facility = session_data["facility"]
            
            # Hit ERPNext edge logic to verify availability and confirm reservation
            result = self.erp.book_facility(facility, flat_number, date_str)
            
            if result.get("success"):
                msg = (f"✅ *FACILITY RESERVATION CONFIRMED*\n\n"
                       f"🏛️ *Facility:* {facility}\n"
                       f"📅 *Date:* {date_str}\n"
                       f"🏠 *Allocated To Flat:* {flat_number}\n\n"
                       f"Your booking has been registered in the system.")
            else:
                msg = f"🛑 *RESERVATION FAILED*\n\n{result.get('error', 'The requested slot is unavailable.')}"
                
            Messenger.send(platform, chat_id, msg, grid=[[{"🔙 Main Menu": "/menu"}]])
            self.session.clear_session(chat_id)