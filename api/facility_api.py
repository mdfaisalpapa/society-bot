import json

class FacilityService:
    def __init__(self, erp_client):
        self.erp = erp_client

    def book_facility(self, facility: str, flat: str, date_str: str) -> dict:
        # 1. Check for existing booking
        filters = json.dumps([["facility", "=", facility], ["booking_date", "=", date_str], ["status", "=", "Confirmed"]])
        existing = self.erp.get_list("Facility Booking", filters=filters)
        
        if isinstance(existing, list) and len(existing) > 0:
            return {"success": False, "error": "This date is already reserved."}
        
        # 2. Create new booking using our new generic POST method
        payload = {"facility": facility, "resident": flat, "booking_date": date_str, "status": "Confirmed"}
        created_doc = self.erp.create_document("Facility Booking", payload)
        
        return {"success": bool(created_doc)}
