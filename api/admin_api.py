import json

class AdminService:
    def __init__(self, base_client):
        self.base_client = base_client

    def get_filtered_tickets(self, status: str, category: str) -> list:
        """Fetches tickets dynamically filtered by exact status and category."""
        filters = json.dumps([
            ["status", "=", status],
            ["category", "=", category]
        ])
        
        fields = '["name", "resident", "category", "description", "status"]'
        
        # 👇 UPDATED: Passed order_by="creation asc" to sort Oldest to Newest
        response = self.base_client.get_list(
            "Maintenance Ticket", 
            filters=filters, 
            fields=fields, 
            order_by="creation asc"
        )
        return response.get("data", [])

    def get_work_permits_by_status(self, status: str) -> list:
        """Fetches Work Permits filtered by status (Pending, Approved, etc)."""
        filters = json.dumps([["status", "=", status]])
        fields = '["name", "flat_number", "contractor_name", "work_type", "status"]'
        
        response = self.base_client.get_list(
            "Work Permit", 
            filters=filters, 
            fields=fields, 
            order_by="creation desc"
        )
        return response.get("data", [])

    def get_work_permit_details(self, permit_id: str) -> dict:
        """Fetches the full details of a specific Work Permit."""
        filters = json.dumps([["name", "=", permit_id]])
        # Fetching all fields ['*'] for the detail view
        response = self.base_client.get_list("Work Permit", filters=filters, fields='["*"]')
        data = response.get("data", [])
        return data[0] if data else {}