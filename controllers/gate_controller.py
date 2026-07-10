import requests
import numpy as np
import cv2
from pyzbar.pyzbar import decode
from services.messenger import Messenger
from api.erp import ERPClient

class GateController:
    def __init__(self, erp: ERPClient):
        self.erp = erp

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
                else:
                    error_msg = f"❌ *ACCESS DENIED*\n\n{result.get('error')}"
                    Messenger.send(platform, chat_id, error_msg)
            else:
                Messenger.send(platform, chat_id, "❌ Invalid QR Code format. This does not appear to be a Gate Pass.")
            
        except Exception as e:
            Messenger.send(platform, chat_id, f"❌ Error processing image: {str(e)}")