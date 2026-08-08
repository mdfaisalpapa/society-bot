import requests
import json
from utils.logger import app_logger

class FileService:
    def __init__(self, base_client):
        self.headers = base_client.headers
        self.base_url = base_client.base_url

    # 👇 NEW: Added attached_to_field parameter
    def upload_file(self, doctype: str, docname: str, file_name: str, file_data: bytes, mime_type: str, is_private: int = 1, attached_to_field: str = None) -> dict:
        try:
            root_url = self.base_url.replace("/api/resource", "")
            url = f"{root_url}/api/method/upload_file"
            
            upload_headers = self.headers.copy()
            upload_headers.pop("Content-Type", None)
            
            files = {"file": (file_name, file_data, mime_type)}
            data = {"is_private": is_private, "folder": "Home/Attachments", "doctype": doctype, "docname": docname}
            
            if attached_to_field:
                data["docfield"] = attached_to_field 
                
            upload_res = requests.post(url, headers=upload_headers, files=files, data=data, timeout=30)
            
            if upload_res.status_code == 200:
                app_logger.info(f"Successfully uploaded {file_name} to {doctype} {docname}")
                
                # ? NEW: Extract the file_url from Frappe's response
                file_info = upload_res.json().get("message", {})
                return {"success": True, "file_url": file_info.get("file_url")}
                
            app_logger.error(f"File upload failed. HTTP {upload_res.status_code}: {upload_res.text}")
            return {"success": False, "error": f"ERPNext Error: {upload_res.status_code}"}
            
        except requests.exceptions.Timeout:
            app_logger.warning(f"Upload timed out for {doctype} {docname}")
            return {"success": False, "error": "Upload timed out."}
        except Exception as e:
            app_logger.exception(f"Unexpected error during file upload: {str(e)}") 
            return {"success": False, "error": str(e)}

    # ... keep get_attachments and download_file exactly as they are ...
    def get_attachments(self, doctype: str, docname: str) -> list:
        url = f"{self.base_url}/File" 
        filters = [["attached_to_doctype", "=", doctype], ["attached_to_name", "=", docname]]
        params = {"filters": json.dumps(filters), "fields": '["name", "file_name", "file_url"]', "limit_page_length": 10}
        
        response = requests.get(url, headers=self.headers, params=params)
        return response.json().get("data", []) if response.status_code == 200 else []

    def download_file(self, file_name: str) -> bytes:
        url = f"{self.base_url}/File/{file_name}"
        response = requests.get(url, headers=self.headers)
        
        if response.status_code == 200:
            file_url = response.json().get("data", {}).get("file_url")
            if file_url:
                root_url = self.base_url.split("/api/")[0]
                img_response = requests.get(f"{root_url}{file_url}", headers=self.headers)
                if img_response.status_code == 200:
                    return img_response.content
        return None