import hashlib
from datetime import datetime, timedelta

class Utils:
    @staticmethod
    def is_valid_date(date_text):
        if len(date_text) != 10 or date_text[4] != "-" or date_text[7] != "-":
            return False
        try:
            year, month, day = int(date_text[:4]), int(date_text[5:7]), int(date_text[8:10])
            return 1 <= month <= 12 and 1 <= day <= 31
        except:
            return False
    
    @staticmethod
    def generate_passcode(chat_id, identifier=""):
        seed = f"{chat_id}{identifier}{datetime.now().date()}"
        hash_obj = hashlib.md5(seed.encode())
        return str(abs(int(hash_obj.hexdigest(), 16)))[:5]
    
    @staticmethod
    def parse_relative_date(date_str):
        date_str = date_str.lower().strip()
        today = datetime.now().date()
        if date_str == "today":
            return str(today)
        elif date_str == "tomorrow":
            return str(today + timedelta(days=1))
        return None
