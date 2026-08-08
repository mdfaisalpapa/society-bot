import requests
import json

class FacilityService:
    def __init__(self, base_client):
        self.headers = base_client.headers
        self.base_url = base_client.base_url

    def book_facility(self, facility: str, flat: str, date_str: str) -> dict:
        chk = requests.get(f"{self.base_url}/Facility Booking", headers=self.headers, params={"filters": json.dumps([["facility", "=", facility], ["booking_date", "=", date_str], ["status", "=", "Confirmed"]])})
        if chk.status_code == 200 and len(chk.json().get("data", [])) > 0:
            return {"success": False, "error": "This date is already reserved."}
        
        payload = {"facility": facility, "resident": flat, "booking_date": date_str, "status": "Confirmed"}
        res = requests.post(f"{self.base_url}/Facility Booking", headers=self.headers, json=payload)
        return {"success": res.status_code == 200}