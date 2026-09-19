from services.messenger import Messenger
from conversation.session import SessionManager
from utils.keyboard import KeyboardBuilder

class VehicleController:
    def __init__(self, erp_client, session_manager: SessionManager):
        self.erp = erp_client
        self.session = session_manager

    def show_my_vehicles(self, platform: str, chat_id: str, flat_number: str):
        vehicles = self.erp.vehicle.get_my_vehicles(flat_number)
        
        if not vehicles:
            msg = "🚗 *My Vehicles*\n\nYou haven't registered any vehicles yet."
        else:
            msg = f"🚗 *My Vehicles ({len(vehicles)})*\n\n"
            for v in vehicles:
                status = "🟢" if v.get("active") else "🔴"
                msg += f"{status} *{v.get('registration_number')}* ({v.get('vehicle_type')})\n"
                msg += f"   └ {v.get('make')} {v.get('model')}\n\n"
                
        Messenger.send(platform, chat_id, msg, inline_keyboard=KeyboardBuilder.resident_vehicles_grid())

    def start_wizard(self, platform: str, chat_id: str):
        self.session.update_session(chat_id, step="vehicle_type", module="add_vehicle")
        Messenger.send(platform, chat_id, "🚗 *Add New Vehicle*\n\nStep 1/5: Select the vehicle type:", inline_keyboard=KeyboardBuilder.vehicle_type_grid())

    def process_wizard(self, platform: str, chat_id: str, text: str, session_data: dict, profile):
        step = session_data.get("step")
        data = session_data.get("data", {})

        if step == "vehicle_type":
            data["vehicle_type"] = text.replace("/vtype_", "")
            self.session.update_session(chat_id, step="reg_no", module="add_vehicle", data=data)
            Messenger.send(platform, chat_id, "Step 2/5: Enter Registration Number (e.g., TN01AB1234):", force_reply=True)
            
        elif step == "reg_no":
            data["registration_number"] = text.strip().upper()
            self.session.update_session(chat_id, step="make", module="add_vehicle", data=data)
            Messenger.send(platform, chat_id, "Step 3/5: Enter Vehicle Make (e.g., Honda, Maruti):", force_reply=True)
            
        elif step == "make":
            data["make"] = text.strip()
            self.session.update_session(chat_id, step="model", module="add_vehicle", data=data)
            Messenger.send(platform, chat_id, "Step 4/5: Enter Vehicle Model (e.g., City, Swift):", force_reply=True)
            
        elif step == "model":
            data["model"] = text.strip()
            self.session.update_session(chat_id, step="color", module="add_vehicle", data=data)
            Messenger.send(platform, chat_id, "Step 5/5: Enter Vehicle Color:", force_reply=True)
            
        elif step == "color":
            data["color"] = text.strip()
            Messenger.send(platform, chat_id, "⏳ Registering vehicle...")
            
            success = self.erp.vehicle.create_vehicle(data, profile)
            self.session.clear_session(chat_id)
            
            if success:
                Messenger.send(platform, chat_id, f"✅ Vehicle *{data['registration_number']}* registered successfully!")
                self.show_my_vehicles(platform, chat_id, profile.flat_number)
            else:
                Messenger.send(platform, chat_id, "❌ Failed to register vehicle.")