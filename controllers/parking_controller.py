from services.messenger import Messenger
from datetime import datetime

class ParkingController:
    def __init__(self, erp_client, session_manager):
        self.erp = erp_client
        self.session = session_manager

    def show_parking_dashboard(self, platform: str, chat_id: str, flat_number: str):
        slots = self.erp.get_owned_slots_with_allocation(flat_number)
        
        if not slots:
            Messenger.send(platform, chat_id, "🅿️ *Parking Management*\n\nYou do not own any parking slots.", inline_keyboard=[[{"text": "🔙 Back to Main Menu", "callback_data": "/menu"}]])
            return

        reply = "🅿️ *Your Owned Parking Slots*\n\n"
        keyboard = []
        
        for slot in slots:
            slot_id = slot["parking_slot"]
            a_type = slot["allocation_type"]
            alloc_name = slot["allocation_name"]
            occupant = slot["occupied_by"]
            
            reply += f"🚗 *Slot:* `{slot_id}`\n📋 *Status:* {a_type}\n"
            if a_type == "Private Neighbor Rental":
                reply += f"👤 *Occupied By:* Flat {occupant}\n"
            reply += "〰️〰️〰️〰️〰️〰️〰️\n"
            
            # 🛡️ Action Buttons (Now safely handles 'NONE' allocation_names)
            if a_type != "Self-Occupied":
                keyboard.append([{"text": f"👤 Reclaim {slot_id}", "callback_data": f"/pk_self_{slot_id}_{alloc_name}"}])
            if a_type != "Private Neighbor Rental":
                keyboard.append([{"text": f"🤝 Rent {slot_id}", "callback_data": f"/pk_pvt_{slot_id}_{alloc_name}"}])
                
            keyboard.append([{"text": f"📜 View History ({slot_id})", "callback_data": f"/pk_hist_{slot_id}"}])

        keyboard.append([{"text": "🔙 Back to Main Menu", "callback_data": "/menu"}])
        Messenger.send(platform, chat_id, reply, inline_keyboard=keyboard)
    def show_history(self, platform: str, chat_id: str, slot_id: str):
        history = self.erp.get_parking_history(slot_id)
        if not history:
            Messenger.send(platform, chat_id, f"📜 *History for {slot_id}*\n\nNo records found.", inline_keyboard=[[{"text": "🔙 Back", "callback_data": "/parking"}]])
            return
            
        reply = f"📜 *Allocation History: {slot_id}*\n\n"
        for h in history:
            status_icon = "🟢" if h.get("status") == "Active" else "⚪"
            start_fmt = datetime.strptime(h["start_date"], "%Y-%m-%d").strftime("%d-%m-%Y") if h.get("start_date") else "Unknown"
            end_fmt = datetime.strptime(h["end_date"], "%Y-%m-%d").strftime("%d-%m-%Y") if h.get("end_date") else "Present"
            
            reply += f"{status_icon} *{h.get('allocation_type')}*\n"
            reply += f"👤 Flat: {h.get('occupied_by')}\n"
            reply += f"📅 {start_fmt} to {end_fmt}\n"
            reply += "〰️〰️〰️〰️〰️〰️〰️\n"
            
        Messenger.send(platform, chat_id, reply, inline_keyboard=[[{"text": "🔙 Back", "callback_data": "/parking"}]])

    def process_self_reclaim(self, platform: str, chat_id: str, slot_id: str, old_alloc: str, flat_number: str):
        start_date = datetime.today().strftime('%Y-%m-%d')
        success = self.erp.reallocate_parking_slot(slot_id, old_alloc, "Self-Occupied", flat_number, start_date, "")
        
        if success:
            Messenger.send(platform, chat_id, "✅ *Parking Reclaimed*\n\nThe slot is now marked as Self-Occupied.")
            self.show_parking_dashboard(platform, chat_id, flat_number)
        else:
            Messenger.send(platform, chat_id, "❌ Failed to update parking slot.")

    # --- WIZARD FOR NEIGHBOR RENTAL ---
    def start_neighbor_rental_wizard(self, platform: str, chat_id: str, slot_id: str, old_alloc: str):
        self.session.update_session(chat_id, step="neighbor_flat", module="parking", data={"slot_id": slot_id, "old_alloc": old_alloc})
        Messenger.send(platform, chat_id, "🤝 *Rent to Neighbor*\n\nStep 1/3: Please enter the Neighbor's Flat Number (e.g., TA1-102):", force_reply=True)

    def process_wizard(self, platform: str, chat_id: str, text: str, session_data: dict, flat_number: str):
        step = session_data.get("step")
        data = session_data.get("data", {})

        if step == "neighbor_flat":
            neighbor = text.strip().upper()
            owner_flat = str(flat_number).strip().upper()
            
            # 1. Prevent renting to their own flat
            if neighbor == owner_flat:
                Messenger.send(platform, chat_id, "❌ You cannot rent a parking slot to your own flat. Please enter a different neighbor's Flat Number:", force_reply=True)
                return
                
            # 2. Validate the flat exists in the ERPNext Customer DocType
            if not self.erp.validate_flat_for_parking(neighbor):
                Messenger.send(platform, chat_id, f"❌ Flat {neighbor} not found. Please enter a valid Flat Number:", force_reply=True)
                return
                
            data["neighbor_flat"] = neighbor
            self.session.update_session(chat_id, step="start_date", module="parking", data=data)
            Messenger.send(platform, chat_id, "Step 2/3: Enter the Start Date (DD-MM-YYYY):", force_reply=True)
        elif step == "start_date":
            try:
                # 1. Parse the input string into a datetime object
                parsed_date = datetime.strptime(text.strip(), "%d-%m-%Y")
                
                # 2. Validate that the date is not in the past
                if parsed_date.date() < datetime.today().date():
                    Messenger.send(platform, chat_id, "❌ Start Date cannot be in the past. Please enter today's date or a future date (DD-MM-YYYY):", force_reply=True)
                    return
                    
                # 3. Format it for ERPNext if valid
                data["start_date"] = parsed_date.strftime("%Y-%m-%d")
                
            except ValueError:
                Messenger.send(platform, chat_id, "❌ Invalid format. Please use DD-MM-YYYY (e.g., 25-10-2026):", force_reply=True)
                return
                
            self.session.update_session(chat_id, step="end_date", module="parking", data=data)
            Messenger.send(platform, chat_id, "Step 3/3: Enter the End Date (DD-MM-YYYY), or type NA if indefinite:", force_reply=True)
        elif step == "end_date":
            end_input = text.strip().upper()
            end_date_erp = ""
            if end_input != "NA":
                try:
                    end_date_erp = datetime.strptime(end_input, "%d-%m-%Y").strftime("%Y-%m-%d")
                except ValueError:
                    Messenger.send(platform, chat_id, "❌ Invalid format. Please use DD-MM-YYYY or type NA:", force_reply=True)
                    return

            success = self.erp.reallocate_parking_slot(
                slot_id=data["slot_id"],
                old_name=data["old_alloc"],
                new_type="Private Neighbor Rental",
                occupant=data["neighbor_flat"],
                start=data["start_date"],
                end=end_date_erp
            )
            self.session.clear_session(chat_id)

            if success:
                Messenger.send(platform, chat_id, f"✅ *Parking Rented*\n\nSlot {data['slot_id']} successfully rented to Flat {data['neighbor_flat']}.")
                self.show_parking_dashboard(platform, chat_id, flat_number)
            else:
                Messenger.send(platform, chat_id, "❌ Failed to reallocate slot. Please try again.")
