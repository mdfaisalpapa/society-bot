import traceback
import os
import requests
import urllib.parse
from urllib.parse import urlparse
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from flask_cors import CORS
from conversation.engine import ConversationEngine
from utils.ocr_verifier import OCRVerifier

# ? 1. FORCE LOAD .ENV GLOBALLY ON STARTUP
load_dotenv()

app = Flask(__name__)

# CRITICAL: Enable CORS so the ERPNext webpage is allowed to talk to this bot server
CORS(app) 

engine = ConversationEngine()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") 

# ---------------------------------------------------------
# 1. TELEGRAM WEBHOOK ROUTE
# ---------------------------------------------------------
@app.route('/', methods=['POST'])
def test_webhook():
    update = request.get_json()
    print(f"DEBUG: Received update: {update}")
    
    if update:
        try:
            engine.process_update(update)
        except Exception as e:
            print("--- FULL TRACEBACK ---")
            traceback.print_exc() 
            print("----------------------")
            
    return "OK", 200

# ---------------------------------------------------------
# 2. ERPNEXT WEB FORM API ROUTE (OCR Verification)
# ---------------------------------------------------------
@app.route('/api/verify_doc', methods=['POST'])
def verify_doc():
    data = request.json
    print(f"DEBUG: Web Form Verification Request: {data}")
    
    file_url = data.get('file_url')
    flat_no = data.get('flat_number')
    email = data.get('email')
    
    if not file_url or not flat_no or not email:
        return jsonify({"status": "Fail", "reason": "Missing required details."})

    try:
        profile = engine.erp_client.get_resident_profile(flat_no)
        if not profile:
             return jsonify({"status": "Fail", "reason": f"Flat {flat_no} is not registered in the database."})

        expected_owner = profile.owner_name 
        expected_parking = getattr(profile, 'parking_slot', '') or ""
        expected_reg_no = getattr(profile, 'CGEWHO_reg_no', '') or ""
             
        # 1. Fetch API Keys securely
        import os
        from dotenv import load_dotenv
        load_dotenv()
        API_KEY = os.getenv("ERPNEXT_API_KEY")
        API_SECRET = os.getenv("ERPNEXT_API_SECRET")

        headers = {}
        if API_KEY and API_SECRET:
            headers["Authorization"] = f"token {API_KEY}:{API_SECRET}"
        
        # ? 2. THE ULTIMATE FIX
        # Force HTTPS to prevent Nginx from dropping the API Keys on redirect.
        # Do NOT manually URL-encode the spaces. Let the requests library handle it natively!
        if file_url.startswith("http://"):
            file_url = file_url.replace("http://", "https://")
            
        print(f"DEBUG: Attempting secure private download: {file_url}")
        
        # 3. Download the PRIVATE file using System Manager API Keys
        response = requests.get(file_url, headers=headers)
        
        if response.status_code != 200:
            print(f"FAILED TO DOWNLOAD. Status: {response.status_code}")
            return jsonify({"status": "Fail", "reason": "Bot was denied access. Please check API keys."})
            
        file_bytes = response.content
                
        # 4. Run the OCR Logic
        print(f"Running OCR on web upload for {profile.owner_name}...")
        ocr_result = OCRVerifier.verify_sale_deed(
            file_data=file_bytes,
            expected_flat=flat_no,
            expected_owner=expected_owner,
            expected_parking=expected_parking,
            expected_reg_no=expected_reg_no
        )
        
        if ocr_result.get("error"):
            return jsonify({"status": "Fail", "reason": ocr_result["error"]})
        else:
            return jsonify({"status": "Pass", "reason": "Document verified successfully."})
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"status": "Fail", "reason": "An internal server error occurred."})
# ---------------------------------------------------------
# START SERVER
# ---------------------------------------------------------
if __name__ == '__main__':
    # Keep host 0.0.0.0 and port 8085 for Nginx
    app.run(host='0.0.0.0', port=8085, debug=True)