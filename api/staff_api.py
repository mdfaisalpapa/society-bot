import requests
import json
import random
from datetime import datetime
from utils.logger import app_logger

class StaffService:
    def __init__(self, base_client):
        self.headers = base_client.headers
        self.base_url = base_client.base_url

    def get_domestic_staff(self, flat_number: str) -> list:
        """Fetches Active domestic staff using Frappe's cross-table join syntax."""
        url = f"{self.base_url}/Domestic Staff"
        
        params = {
            "filters": json.dumps([
                # 👇 The Secret Frappe Syntax: [Child_Table, field, operator, value] 👇
                ["Staff Flat Link", "flat", "=", flat_number],
                
                # And we still ensure the staff member is Active
                ["status", "=", "Active"]
            ]),
            "fields": '["name", "staff_name", "role", "phone"]' 
        }
        
        res = requests.get(url, headers=self.headers, params=params)
        
        if res.status_code == 200:
            return res.json().get("data", [])
            
        app_logger.error(f"Failed to fetch staff for {flat_number}: {res.text}")
        return []
    def get_staff_by_category(self, category: str) -> list:
        from utils.logger import app_logger
        import json
        import requests
        
        url = f"{self.base_url}/Domestic%20Staff"
        params = {
            "filters": json.dumps([["role", "=", category], ["status", "=", "Active"]]),
            "fields": '["name", "staff_name", "role", "phone"]',
            "limit_page_length": 50
        }
        
        try:
            # 1. Fetch the Staff
            res = requests.get(url, headers=self.headers, params=params)
            staff_list = res.json().get("data", []) if res.status_code == 200 else []
            
            if not staff_list:
                return []
                
            # 2. Fetch the Ratings for these staff members
            staff_ids = [s["name"] for s in staff_list]
            review_url = f"{self.base_url}/Staff%20Review"
            review_params = {
                # docstatus = 1 means we only fetch "Submitted" reviews, not drafts!
                "filters": json.dumps([
                    ["staff", "in", staff_ids], 
                    ["review_type", "=", "Rating"], 
                    ["docstatus", "=", 1]
                ]),
                "fields": '["staff", "rating"]',
                "limit_page_length": 1000
            }
            
            rev_res = requests.get(review_url, headers=self.headers, params=review_params)
            reviews = rev_res.json().get("data", []) if rev_res.status_code == 200 else []
            
            # 3. Calculate Averages
            rating_map = {}
            for r in reviews:
                sid = r.get("staff")
                if sid not in rating_map:
                    rating_map[sid] = []
                rating_map[sid].append(r.get("rating", 0))
                
            # 4. Attach averages to the staff list
            for staff in staff_list:
                sid = staff["name"]
                if sid in rating_map and len(rating_map[sid]) > 0:
                    avg = sum(rating_map[sid]) / len(rating_map[sid])
                    staff["avg_rating"] = round(avg, 1)
                else:
                    staff["avg_rating"] = 0
                    
            return staff_list
            
        except Exception as e:
            app_logger.error(f"Error fetching staff by category: {e}")
            return []

    def create_staff_pass(self, flat_number: str, staff_name: str, role: str) -> dict:
        """Generates a daily pre-approved gate pass for the staff member."""
        clean_flat = flat_number.replace(" ", "_").upper()
        passcode = f"STAFF_{clean_flat}_{random.randint(1000, 9999)}"
        
        payload = {
            "resident": flat_number,
            "visitor_name": f"{staff_name} ({role})",
            "status": "Approved",
            "entry_type": "Staff",
            "expected_date": datetime.now().strftime("%Y-%m-%d"),
            "purpose_of_visit": "Routine Work",
            "passcode": passcode
        }

        url = f"{self.base_url}/Visitor%20Log"
        res = requests.post(url, headers=self.headers, json=payload)
        
        if res.status_code == 200:
            return {"success": True, "passcode": passcode}
            
        app_logger.error(f"Failed to create staff pass: {res.text}")
        return {"success": False, "error": "Could not generate pass."}
    

    def link_staff_to_flat(self, staff_id: str, flat_number: str) -> bool:
        """Links a staff member to a resident's flat in ERPNext."""
        # Note: Adjust this payload based on how your ERPNext schema connects Flats to Staff.
        # Below is an example of adding the flat to a Child Table called 'linked_flats'
        url = f"{self.base_url}/Domestic Staff/{staff_id}"
        
        # 1. Fetch current staff doc to get existing flats
        doc_res = requests.get(url, headers=self.headers)
        if doc_res.status_code != 200:
            return False
            
        staff_doc = doc_res.json().get("data", {})
        existing_flats = staff_doc.get("linked_flats", [])
        
        # Check if already linked
        if any(f.get("flat") == flat_number for f in existing_flats):
            return True 
            
        # 2. Append new flat and update
        existing_flats.append({"flat": flat_number})
        
        payload = {"linked_flats": existing_flats}
        update_res = requests.put(url, headers=self.headers, json=payload)
        
        if update_res.status_code == 200:
            app_logger.info(f"Successfully linked {staff_id} to flat {flat_number}")
            return True
            
        app_logger.error(f"Failed to link staff: {update_res.text}")
        return False

    def unlink_staff_from_flat(self, staff_id: str, flat_number: str) -> bool:
        """Removes a flat from a staff member's linked_flats child table."""
        from utils.logger import app_logger
        url = f"{self.base_url}/Domestic%20Staff/{staff_id}"
        
        try:
            # 1. Fetch current staff doc
            doc_res = requests.get(url, headers=self.headers)
            if doc_res.status_code != 200:
                return False
                
            staff_doc = doc_res.json().get("data", {})
            existing_flats = staff_doc.get("linked_flats", [])
            
            # 2. Filter out the resident's flat
            updated_flats = [f for f in existing_flats if f.get("flat") != flat_number]
            
            # If nothing changed, they are already unlinked
            if len(existing_flats) == len(updated_flats):
                return True
                
            # 3. Update ERPNext
            payload = {"linked_flats": updated_flats}
            update_res = requests.put(url, headers=self.headers, json=payload)
            
            if update_res.status_code == 200:
                app_logger.info(f"Successfully unlinked {staff_id} from {flat_number}")
                return True
                
            app_logger.error(f"Failed to unlink staff: {update_res.text}")
            return False
            
        except Exception as e:
            app_logger.error(f"Error unlinking staff: {e}")
            return False

    def verify_staff_pass(self, staff_id: str) -> dict:
        from utils.logger import app_logger
        
        try:
            res = requests.get(f"{self.base_url}/Domestic%20Staff/{staff_id}", headers=self.headers)
            
            if res.status_code == 200:
                doc = res.json().get("data", {})
                
                # ? NEW: Extract flats and details BEFORE checking status
                active_flats = [
                    row.get("flat") 
                    for row in doc.get("linked_flats", []) 
                    if row.get("is_active") == 1
                ]
                staff_name = doc.get("staff_name")
                role = doc.get("role")
                status = doc.get("status")
                
                # If they aren't active, return success=False BUT include the extra data
                if status != "Active":
                    return {
                        "success": False, 
                        "error": f"?? Access Denied: Staff profile is marked as {status}.",
                        "status": status,
                        "staff_name": staff_name,
                        "role": role,
                        "flats": active_flats
                    }
                
                return {
                    "success": True,
                    "staff_name": staff_name,
                    "role": role,
                    "flats": active_flats
                }
                
            elif res.status_code == 404:
                return {"success": False, "error": "? Invalid ID: Staff member not found in database."}
            else:
                app_logger.error(f"Staff API Error: {res.status_code} - {res.text}")
                return {"success": False, "error": f"API Error: {res.status_code}"}
                
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_staff_details(self, staff_id: str) -> dict:
        """Fetches staff profile, average rating, and recent complaints."""
        import requests
        import json
        
        url = f"{self.base_url}/Domestic%20Staff/{staff_id}"
        try:
            res = requests.get(url, headers=self.headers)
            if res.status_code != 200:
                return {}
                
            data = res.json().get("data", {})
            
            # --- 1. FETCH RATINGS ---
            rev_url = f"{self.base_url}/Staff%20Review"
            rating_params = {
                "filters": json.dumps([
                    ["staff", "=", staff_id], 
                    ["review_type", "=", "Rating"],
                    ["docstatus", "=", 0]
                ]),
                "fields": '["rating"]'
            }
            rating_res = requests.get(rev_url, headers=self.headers, params=rating_params)
            ratings = rating_res.json().get("data", []) if rating_res.status_code == 200 else []
            
            if ratings:
                avg = sum(r.get("rating", 0) for r in ratings) / len(ratings)
                data["avg_rating"] = round(avg, 1)
            else:
                data["avg_rating"] = 0
                
            # --- 2. FETCH COMPLAINTS ---
            comp_params = {
                "filters": json.dumps([
                    ["staff", "=", staff_id], 
                    ["review_type", "=", "Complaint"],
                    ["docstatus", "=", 0]
                ]),
                "fields": '["comments"]',
                "order_by": "creation desc", # Gets the newest ones first
                "limit_page_length": 3       # Only grab the latest 3 so the message isn't huge
            }
            comp_res = requests.get(rev_url, headers=self.headers, params=comp_params)
            complaints = comp_res.json().get("data", []) if comp_res.status_code == 200 else []
            
            # Extract just the text of the complaints
            data["recent_complaints"] = [c.get("comments") for c in complaints if c.get("comments")]
                
            return data
        except Exception:
            return {}

    def submit_staff_review(self, staff_id: str, flat: str, review_type: str, rating: int = 0, comments: str = "") -> bool:
        """Creates a new review, or UPDATES the existing one if the resident already reviewed them."""
        from utils.logger import app_logger
        import requests
        import json
        
        base_review_url = f"{self.base_url}/Staff%20Review"
        
        try:
            # 1. Check if this flat already submitted this type of review for this staff
            check_params = {
                "filters": json.dumps([
                    ["staff", "=", staff_id],
                    ["flat", "=", flat],
                    ["review_type", "=", review_type]
                ]),
                "fields": '["name"]'
            }
            check_res = requests.get(base_review_url, headers=self.headers, params=check_params)
            existing = check_res.json().get("data", []) if check_res.status_code == 200 else []
            
            # The data payload we want to save
            payload = {
                "staff": staff_id,
                "flat": flat,
                "review_type": review_type,
                "rating": rating,
                "comments": comments
            }
            
            if existing:
                # 2A. UPDATE Existing Record
                doc_name = existing[0]["name"]
                update_url = f"{base_review_url}/{doc_name}"
                res = requests.put(update_url, headers=self.headers, json=payload)
            else:
                # 2B. CREATE New Record
                res = requests.post(base_review_url, headers=self.headers, json=payload)
                
            if res.status_code == 200:
                return True
                
            app_logger.error(f"Failed to submit review: {res.text}")
            return False
            
        except Exception as e:
            app_logger.error(f"Review API error: {e}")
            return False