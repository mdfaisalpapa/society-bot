import os
import requests
import re # 👈 Add this import at the top
from services.messenger import Messenger
from conversation.session import SessionManager
from utils.keyboard import KeyboardBuilder

class VehicleController:
    def __init__(self, erp_client, session_manager: SessionManager):
        self.erp = erp_client
        self.session = session_manager

# controllers/vehicle_controller.py

    # controllers/vehicle_controller.py

    def show_my_vehicles(self, platform: str, chat_id: str, flat_number: str):
        vehicles = self.erp.vehicle.get_my_vehicles(flat_number)
        available_slots = self.erp.vehicle.get_available_parking_slots(flat_number)
        
        car_count = sum(1 for v in vehicles if v.get("vehicle_type") == "Car")
        bike_count = sum(1 for v in vehicles if v.get("vehicle_type") == "Bike")
        
        if not vehicles:
            msg = "🚗 *My Vehicles*\n\nYou haven't registered any vehicles yet.\n\n"
        else:
            msg = f"🚗 *My Vehicles ({len(vehicles)})*\n\n"
            for v in vehicles:
                status = "🟢" if v.get("active") else "🔴"
                msg += f"{status} *{v.get('registration_number')}* ({v.get('vehicle_type')})\n"
                msg += f"   └ {v.get('make')} {v.get('model')}\n"
                
                # 👇 FIX: Handle Blank slots strictly as Open Parking
                parking_slot = v.get("parking_slot")
                if parking_slot:
                    msg += f"   🅿️ Slot: *{parking_slot}* (Reserved)\n"
                elif not parking_slot:  # Catch all blanks (None or "")
                    msg += "   🅿️ Type: *Open Parking*\n"
                    msg += "   ⚠️ _Subject to availability._\n"
                msg += "\n"
                
        msg += "🅿️ *Available Allocations:*\n"
        
        if available_slots:
            for slot in available_slots:
                msg += f" ▫️ `{slot}`\n"
        elif car_count == 0:
            msg += " ▫️ Type: *Open Parking*\n"
            msg += "   ⚠️ _Subject to availability._\n"
        else:
            msg += "⚠️ *Already Car parking consumed*\n"
            
        # 👇 FIX: Changed bike display logic to handle 2 bikes
        if bike_count >= 2:
            msg += "\n🛵 *Bikes:* Already Bike parking consumed\n"
        else:
            msg += "\n🛵 *Bikes:* 2 Allowed per flat (Unreserved)\n"
            msg += " ▫️ Type: *Open Parking*\n"
            msg += "   ⚠️ _Subject to availability._\n"
                
        Messenger.send(platform, chat_id, msg, inline_keyboard=KeyboardBuilder.resident_vehicles_grid())
    def start_wizard(self, platform: str, chat_id: str, profile):
        # Simply start the session and ask for Car or Bike
        self.session.update_session(chat_id, step="vehicle_type", module="add_vehicle", data={})
        Messenger.send(platform, chat_id, "🚗 *Add New Vehicle*\n\nStep 1/8: Select the vehicle type:", inline_keyboard=KeyboardBuilder.vehicle_type_grid())
    
    # controllers/vehicle_controller.py

    def process_wizard(self, platform: str, chat_id: str, text: str, message: dict, session_data: dict, profile):
        step = session_data.get("step")
        data = session_data.get("data", {})

        # controllers/vehicle_controller.py

        if step == "vehicle_type":
            v_type = text.replace("/vtype_", "")
            existing_vehicles = self.erp.vehicle.get_my_vehicles(profile.flat_number)
            
            if v_type == "Bike":
                # 👇 FIX: Changed bike limit to 2
                bike_count = sum(1 for v in existing_vehicles if v.get("vehicle_type") == "Bike")
                if bike_count >= 2:
                    Messenger.send(platform, chat_id, "⚠️ *Limit Reached*\n\nSociety rules allow a maximum of two registered bikes per flat.", inline_keyboard=[[{"text": "🔙 Back", "callback_data": "/my_vehicles"}]])
                    return
                data["pending_parking_slot"] = "Open Parking"
                
            elif v_type == "Car":
                car_count = sum(1 for v in existing_vehicles if v.get("vehicle_type") == "Car")
                available_slots = self.erp.vehicle.get_available_parking_slots(profile.flat_number)
                
                if available_slots:
                    data["pending_parking_slot"] = available_slots[0]
                elif car_count == 0:
                    data["pending_parking_slot"] = "Open Parking"
                else:
                    Messenger.send(platform, chat_id, "⚠️ *Limit Reached*\n\nYou have utilized all reserved slots. Open parking is only permitted for residents with zero registered cars.", inline_keyboard=[[{"text": "🔙 Back", "callback_data": "/my_vehicles"}]])
                    return

            # If it passes the checks, save the type and proceed to Registration Number
            data["vehicle_type"] = v_type
            self.session.update_session(chat_id, step="reg_no", module="add_vehicle", data=data)
            Messenger.send(platform, chat_id, "Step 2/8: Enter Registration Number (e.g., TN01AB1234):", force_reply=True)
            
        elif step == "reg_no":
            # ... [Keep existing reg_no logic]
            # Sanitize the input: Remove all spaces/hyphens/special chars and uppercase it
            raw_input = text.strip()
            clean_reg_no = re.sub(r'[^a-zA-Z0-9]', '', raw_input).upper()
            
            if not clean_reg_no:
                Messenger.send(platform, chat_id, "Please enter a valid registration number.")
                return
                
            # Check if this exact vehicle is already in the ERPNext database
            if self.erp.vehicle.check_vehicle_exists(clean_reg_no):
                Messenger.send(platform, chat_id, f"⚠️ Vehicle *{clean_reg_no}* is already registered in the system.\n\nPlease enter a different registration number, or type /cancel to exit.")
                return
                
            data["registration_number"] = clean_reg_no
            self.session.update_session(chat_id, step="make", module="add_vehicle", data=data)
            
            makes = self.erp.vehicle.get_makes(data.get("vehicle_type"))
            if not makes:
                makes = ["Other"] 
                
            keyboard = KeyboardBuilder.dynamic_select_grid(makes, "/vmake_")
            Messenger.send(platform, chat_id, f"Step 3/8: Select {data.get('vehicle_type')} Make:", inline_keyboard=keyboard)
            
        elif step == "make":        # ... [Keep your existing make block]
            if text.startswith("/vmake_"):
                # 1. Strip the prefix
                raw_make = text.replace("/vmake_", "")
                
                # 2. Restore any spaces from the safe callback string
                selected_make = raw_make.replace("_", " ") 
                
                data["make"] = selected_make
                self.session.update_session(chat_id, step="model", module="add_vehicle", data=data)
                
                models = self.erp.vehicle.get_models(selected_make)
                if not models:
                    models = ["Other"]
                    
                keyboard = KeyboardBuilder.dynamic_select_grid(models, "/vmod_")
                Messenger.send(platform, chat_id, f"Step 4/8: Select {selected_make} Model:", inline_keyboard=keyboard)
            else:
                Messenger.send(platform, chat_id, "Please select an option using the buttons.")    
       # controllers/vehicle_controller.py

        elif step == "model":
            if text.startswith("/vmod_"):
                # 1. Strip the prefix
                raw_model = text.replace("/vmod_", "")
                # 2. Restore the spaces from the safe callback string
                data["model"] = raw_model.replace("_", " ") 
                
                self.session.update_session(chat_id, step="color", module="add_vehicle", data=data)
                
                # 👇 FIX: Use your existing KeyboardBuilder method which handles permissions and fallbacks correctly
                fallback_colors = ["White", "Silver", "Grey", "Black", "Red", "Blue", "Brown", "Other"]
                colors = KeyboardBuilder._fetch_options("Resident Vehicle", "color", fallback_colors)
                
                keyboard = KeyboardBuilder.dynamic_select_grid(colors, "/vcol_")
                Messenger.send(platform, chat_id, "Step 5/8: Select Vehicle Color:", inline_keyboard=keyboard)
            else:
                Messenger.send(platform, chat_id, "Please select an option using the buttons.")
        elif step == "color":
            if text.startswith("/vcol_"):
                data["color"] = text.replace("/vcol_", "")
                self.session.update_session(chat_id, step="owner_name", module="add_vehicle", data=data)
                Messenger.send(platform, chat_id, "Step 6/8: Enter Registered Owner's Name (as per RC):", force_reply=True)
            else:
                Messenger.send(platform, chat_id, "Please select an option using the buttons.")

        # controllers/vehicle_controller.py

        elif step == "owner_name":
            data["registered_owner_name"] = text.strip()
            self.session.update_session(chat_id, step="relationship", module="add_vehicle", data=data)
            
            # 👇 NEW: Fetch options from ERPNext using your existing Keyboard Builder
            fallback_options = [
                "Self", "Spouse / Immediate Family", "Extended Family", 
                "Company / Employer Lease", "Rented / Subscription"
            ]
            relations = KeyboardBuilder._fetch_options("Resident Vehicle", "relationship_to_resident", fallback_options)
            
            keyboard = KeyboardBuilder.dynamic_select_grid(relations, "/vrel_")
            Messenger.send(platform, chat_id, "Step 7/8: Select Relationship to Resident:", inline_keyboard=keyboard)

        elif step == "relationship":
            if text.startswith("/vrel_"):
                # Strip prefix and restore spaces from the safe callback string
                raw_rel = text.replace("/vrel_", "")
                data["relationship_to_owner"] = raw_rel.replace("_", " ") 
                
                self.session.update_session(chat_id, step="rc_copy", module="add_vehicle", data=data)
                Messenger.send(platform, chat_id, "Step 8/8: Please upload a photo of the RC Book:", force_reply=True)
            else:
                Messenger.send(platform, chat_id, "Please select an option using the buttons.")
        # controllers/vehicle_controller.py

        # controllers/vehicle_controller.py

        elif step == "rc_copy":
            # Extract file_id from either a photo or a document
            file_id = None
            if message.get("photo"):
                file_id = message["photo"][-1]["file_id"]
            elif message.get("document"):
                file_id = message["document"]["file_id"]
                
            if not file_id:
                Messenger.send(platform, chat_id, "Please upload an image or document of the RC Book.")
                return
                
            data["rc_file_id"] = file_id
            
            relationship = data.get("relationship_to_owner", "")
            if relationship not in ["Self", "Family(Residing)"]:
                self.session.update_session(chat_id, step="noc_copy", module="add_vehicle", data=data)
                Messenger.send(platform, chat_id, "Step 9: Since this vehicle belongs to someone else, please upload a photo/document of the NOC:", force_reply=True)
            else:
                self._submit_vehicle(platform, chat_id, data, profile)

        elif step == "noc_copy":
            # Extract file_id from either a photo or a document
            file_id = None
            if message.get("photo"):
                file_id = message["photo"][-1]["file_id"]
            elif message.get("document"):
                file_id = message["document"]["file_id"]
                
            if not file_id:
                Messenger.send(platform, chat_id, "Please upload an image or document of the NOC.")
                return
                
            data["noc_file_id"] = file_id
            self._submit_vehicle(platform, chat_id, data, profile)
    def _download_telegram_file(self, file_id: str) -> bytes:
        bot_token = os.getenv("SOCIETY_BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
        if not bot_token:
            return None
            
        file_info_url = f"https://api.telegram.org/bot{bot_token}/getFile?file_id={file_id}"
        file_info = requests.get(file_info_url).json()
        
        if not file_info.get("ok"):
            return None
            
        file_path = file_info["result"]["file_path"]
        download_url = f"https://api.telegram.org/file/bot{bot_token}/{file_path}"
        return requests.get(download_url).content

    def _submit_vehicle(self, platform, chat_id, data, profile):
        Messenger.send(platform, chat_id, "⏳ Registering vehicle and confirming parking allocation...")
        
        # Retrieve the slot we secured at the start of the wizard
        allocated_slot = data.get("pending_parking_slot")
        
        if allocated_slot == "Open Parking":
            # Pass a blank string to satisfy the ERPNext Link field validation
            data["parking_slot"] = "" 
            # Inject a remark so the Estate Office knows it's an Open Parking vehicle
            data["remarks"] = "Assigned to Open Parking" 
            Messenger.send(platform, chat_id, "🅿️ Registered as an Unreserved Open Parking vehicle.")
            
        elif allocated_slot:
            data["parking_slot"] = allocated_slot
            Messenger.send(platform, chat_id, f"🅿️ Linked to available parking slot: *{allocated_slot}*")
            
        docname = self.erp.vehicle.create_vehicle(data, profile)
        # ... [Keep the rest of your file upload logic]
        
        if not docname:
            Messenger.send(platform, chat_id, "❌ Failed to register vehicle.")
            self.session.clear_session(chat_id)
            return

        if data.get("rc_file_id"):
            rc_bytes = self._download_telegram_file(data["rc_file_id"]) 
            if rc_bytes:
                self.erp.file.upload_file(
                    doctype="Resident Vehicle", 
                    docname=docname, 
                    file_name=f"RC_{data['registration_number']}.jpg", 
                    file_data=rc_bytes, 
                    mime_type="image/jpeg", 
                    attached_to_field="rc_copy"
                )

        if data.get("noc_file_id"):
            noc_bytes = self._download_telegram_file(data["noc_file_id"])
            if noc_bytes:
                self.erp.file.upload_file(
                    doctype="Resident Vehicle", 
                    docname=docname, 
                    file_name=f"NOC_{data['registration_number']}.jpg", 
                    file_data=noc_bytes, 
                    mime_type="image/jpeg", 
                    attached_to_field="noc"
                )

        self.session.clear_session(chat_id)
        Messenger.send(platform, chat_id, f"✅ Vehicle *{data['registration_number']}* registered successfully!")
        self.show_my_vehicles(platform, chat_id, profile.flat_number)


    # controllers/vehicle_controller_5.py

    def process_open_parking_application(self, platform: str, chat_id: str, flat_number: str):
        """Creates a ticket requesting an Open Parking allocation."""
        # Check if they already have a pending request to prevent spam
        # (Assuming you have a generic check_pending_tickets method, or we just submit it)
        
        # We will use the existing Maintenance API to log the request
        try:
            from api.maintenance_api import MaintenanceService
            m_service = MaintenanceService(self.erp.base_client)
            
            # Create a ticket categorized for Parking
            ticket_id = m_service.create_maintenance_ticket(
                flat_number=flat_number,
                category="Other Issues", # Or a specific "Parking Request" category if you added one
                description="Resident is requesting an additional Open Parking slot allocation."
            )
            
            if ticket_id:
                Messenger.send(
                    platform, chat_id, 
                    f"✅ *Application Submitted*\n\nYour request for an Open Parking slot has been sent to the Estate Office (Ticket: {ticket_id}).\n\nThey will contact you regarding availability and rental fees.", 
                    inline_keyboard=[[{"text": "🔙 Back to Portal", "callback_data": "/portal_resident"}]]
                )
            else:
                Messenger.send(platform, chat_id, "❌ Failed to submit application. Please contact the Estate Office directly.")
        except Exception as e:
            Messenger.send(platform, chat_id, "❌ An error occurred while submitting your application.")
