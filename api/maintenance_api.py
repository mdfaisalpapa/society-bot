import requests
import json

class MaintenanceService:
    def __init__(self, base_client, file_service):
        self.headers = base_client.headers
        self.base_url = base_client.base_url
        self.file_service = file_service

    def create_maintenance_ticket(self, flat_number: str, category: str, description: str) -> str:
        url = f"{self.base_url}/Maintenance Ticket"
        payload = {"resident": flat_number, "category": category, "description": description, "status": "Open"}
        try:
            response = requests.post(url, headers=self.headers, json=payload)
            if response.status_code == 200:
                return response.json().get("data", {}).get("name")
            return None
        except Exception:
            return None

    def get_user_tickets(self, flat_number: str, offset: int = 0, status_filter: str = "Open") -> list:
        
        # This single line handles both Handover and Routine phases permanently!
        if status_filter == "Open":
            status_criteria = ["Open", "Assigned", "Pending"]
        else:
            # Handles "Closed", "Resolved", or anything else you consider finished
            status_criteria = ["Resolved", "Closed"] 
            
        params = {
            "filters": json.dumps([["resident", "=", flat_number.strip().upper()], ["status", "in", status_criteria]]), 
            "fields": json.dumps(["name", "status"]),
            "order_by": "creation desc", # <--- Add this!
            "limit_start": offset, 
            "limit_page_length": 10
        }
        
        response = requests.get(f"{self.base_url}/Maintenance Ticket", headers=self.headers, params=params)
        return response.json().get("data", []) if response.status_code == 200 else []

    def get_ticket_details(self, ticket_name: str) -> dict:
        try:
            response = requests.get(f"{self.base_url}/Maintenance Ticket/{ticket_name}", headers=self.headers)
            return response.json().get("data", {}) if response.status_code == 200 else {}
        except:
            return {}

    def upload_file_to_ticket(self, ticket_name: str, file_data: bytes) -> bool:
        result = self.file_service.upload_file(doctype="Maintenance Ticket", docname=ticket_name, file_name="attachment.jpg", file_data=file_data, mime_type="image/jpeg", is_private=0)
        return result.get("success", False)