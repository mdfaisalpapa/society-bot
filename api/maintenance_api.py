import json

class MaintenanceService:
    def __init__(self, erp_client, file_service):
        self.erp = erp_client
        self.file_service = file_service

    def create_maintenance_ticket(self, flat_number: str, category: str, description: str) -> str:
        payload = {"resident": flat_number, "category": category, "description": description, "status": "Open"}
        res = self.erp.create_document("Maintenance Ticket", payload)
        
        # Safely extract the newly created document name
        return res.get("name") if isinstance(res, dict) else None

    def get_user_tickets(self, flat_number: str, offset: int = 0, status_filter: str = "Open") -> list:
        import json
        import requests
        from utils.logger import app_logger
        
        clean_status = str(status_filter).strip().title()
        if clean_status in ["Open", "Assigned", "Pending", "In Progress"]:
            status_criteria = ["Open", "Assigned", "Pending", "In Progress"]
        else:
            status_criteria = ["Resolved", "Closed"] 
        
        safe_offset = int(offset) if offset else 0
        
        params = {
            "filters": json.dumps([
                ["resident", "=", str(flat_number).strip().upper()], 
                ["status", "in", status_criteria]
            ]), 
            "fields": '["name", "status"]',
            "order_by": "creation desc",
            "limit_start": safe_offset, 
            "limit_page_length": 10
        }
        
        # 🐛 API DIAGNOSTICS: Correctly referencing self.erp.base_url
        app_logger.info(f"API: Sending Request to ERPNext -> {self.erp.base_url}/Maintenance Ticket")
        app_logger.info(f"API: Params -> {params}")
        
        try:
            # 🐛 API DIAGNOSTICS: Correctly referencing self.erp.headers and self.erp.base_url
            response = requests.get(f"{self.erp.base_url}/Maintenance Ticket", headers=self.erp.headers, params=params)
            
            app_logger.info(f"API: ERPNext HTTP Status -> {response.status_code}")
            app_logger.info(f"API: ERPNext Response Body -> {response.text}")
            
            if response.status_code == 200:
                data = response.json().get("data", [])
                return data if isinstance(data, list) else []
            else:
                return []
                
        except Exception as e:
            app_logger.error(f"API CRASH in get_user_tickets: {str(e)}")
            return []
    def get_ticket_details(self, ticket_name: str) -> dict:
        filters = json.dumps([["name", "=", ticket_name]])
        res = self.erp.get_list("Maintenance Ticket", filters=filters, fields='["*"]')
        
        data = res.get("data", []) if isinstance(res, dict) else res
        return data[0] if data else {}

    def upload_file_to_ticket(self, ticket_name: str, file_data: bytes) -> bool:
        result = self.file_service.upload_file(
            doctype="Maintenance Ticket", 
            docname=ticket_name, 
            file_name="attachment.jpg", 
            file_data=file_data, 
            mime_type="image/jpeg", 
            is_private=0
        )
        return result.get("success", False)
