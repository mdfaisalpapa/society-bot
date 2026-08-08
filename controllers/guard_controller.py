import requests
import numpy as np
import cv2
from pyzbar.pyzbar import decode
from services.messenger import Messenger
from api.erp import ERPClient
from conversation.session import SessionManager # Import this

class GuardController:
    # Ensure it accepts erp AND session
    def __init__(self, erp: ERPClient, session: SessionManager): 
        self.erp = erp
        self.session = session

    def handle_scan_prompt(self, platform: str, chat_id: str):
        """Instructs the guard how to use the native QR scanner."""
        msg = ("📷 *QR Scanner Instructions*\n\n"
               "To scan a pass:\n"
               "1. Click the *paperclip/attach* icon.\n"
               "2. Select *Camera*.\n"
               "3. Point at the visitor's QR code.\n"
               "4. Send the image to me!")
        Messenger.send(platform, chat_id, msg)

    def process_qr_image(self, platform, chat_id, message, file_id):
        """Downloads the image, decodes the QR code, and triggers verification."""
        
        # 1. Get the direct file URL from the platform
        file_url = Messenger.get_file_url(platform, file_id)
        if not file_url:
            Messenger.send(platform, chat_id, "❌ Could not retrieve image.")
            return

        # 2. Download and decode
        try:
            response = requests.get(file_url)
            image_array = np.asarray(bytearray(response.content), dtype=np.uint8)
            img = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
            
            decoded_objects = decode(img)
            if not decoded_objects:
                Messenger.send(platform, chat_id, "❌ No QR code detected. Please ensure the image is clear and well-lit.")
                return
            
            # 3. Extract the deep link data
            qr_data = decoded_objects[0].data.decode('utf-8')
            
            if "verify_" in qr_data:
                passcode = qr_data.split("verify_")[1]
                
                # 4. Use the ERP logic to verify
                result = self.erp.verify_visitor_passcode(passcode)
                
                # 5. Send the result back to the guard
                if result.get("success"):
                    success_msg = (f"✅ *ACCESS GRANTED*\n\n"
                                   f"👤 *Visitor:* {result['visitor_name']}\n"
                                   f"🏠 *Going to:* {result['resident']}\n"
                                   f"🚗 *Vehicle:* {result.get('vehicle', 'N/A')}\n\n"
                                   f"_Visitor has been automatically logged as 'Entered'._")
                    Messenger.send(platform, chat_id, success_msg)
                    # 👇 NEW: Notify the Resident 👇
                    resident_flat = result.get("resident")
                    resident_chat_id = self.erp.get_resident_chat_id(resident_flat)
                
                    if resident_chat_id:
                        msg_to_resident = (f"🔔 *Visitor Arrival*\n\n"
                                           f"Your visitor *{result['visitor_name']}* has just arrived at the gate "
                                           f"and has been granted access.")
                        Messenger.send(platform, resident_chat_id, msg_to_resident)
                else:
                    error_msg = f"❌ *ACCESS DENIED*\n\n{result.get('error')}"
                    Messenger.send(platform, chat_id, error_msg)
            else:
                Messenger.send(platform, chat_id, "❌ Invalid QR Code format. This does not appear to be a Gate Pass.")
            
        except Exception as e:
            Messenger.send(platform, chat_id, f"❌ Error processing image: {str(e)}")

    def process_staff_scan(self, platform: str, guard_chat_id: str, staff_id: str, entry_type: str):
        """Processes staff entry/exit, checks status, and notifies linked flats."""
        
        # 1. Fetch Staff details from ERP
        staff = self.erp.get_doc("Domestic Staff", staff_id)
        if not staff:
            Messenger.send(platform, guard_chat_id, "❌ Invalid Staff ID.")
            return

        status = staff.get("status")
        staff_name = staff.get("staff_name")
        # Ensure 'staff_flat_link' is the correct child table name
        linked_flats = [row["flat"] for row in staff.get("staff_flat_link", [])]

        # 2. Blacklist Check
        if status == "Blacklisted":
            alert_msg = f"🚨 *SECURITY ALERT*\n\n*{staff_name}* (ID: {staff_id}) is *BLACKLISTED*. Entry DENIED."
            for flat in linked_flats:
                resident_chat_id = self.session.get_chat_id_by_flat(flat)
                if resident_chat_id: 
                    Messenger.send(platform, resident_chat_id, alert_msg)
            Messenger.send(platform, guard_chat_id, f"🛑 Access Denied: {staff_name} is Blacklisted.")
            return

        # 3. Handle Active Entry/Exit
        if status == "Active":
            msg = f"🟢 *Staff {entry_type}*\n\nYour staff member *{staff_name}* has performed an {entry_type} at the gate."
            for flat in linked_flats:
                resident_chat_id = self.session.get_chat_id_by_flat(flat)
                if resident_chat_id: 
                    Messenger.send(platform, resident_chat_id, msg)
            Messenger.send(platform, guard_chat_id, f"✅ {entry_type} logged for {staff_name}.")