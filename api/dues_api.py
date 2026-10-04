import json

class DuesService:
    def __init__(self, erp_client):
        self.erp = erp_client

    def get_outstanding_dues(self, flat_number: str) -> float:
        filters = json.dumps([
            ["customer", "=", flat_number.strip().upper()], 
            ["docstatus", "=", 1], 
            ["outstanding_amount", ">", 0]
        ])
        res = self.erp.get_list("Sales Invoice", filters=filters, fields='["outstanding_amount"]')
        
        if isinstance(res, list):
            return sum(float(inv.get("outstanding_amount", 0)) for inv in res)
        return 0.0
