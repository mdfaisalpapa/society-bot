import logging
import json
from typing import Optional, Dict, List
import requests
from config import ERPNEXT_URL, ERPNEXT_API_KEY, ERPNEXT_API_SECRET, API_TIMEOUT
logger = logging.getLogger(__name__)
class ERPNextClient:
    def __init__(self, base_url=ERPNEXT_URL, api_key=ERPNEXT_API_KEY, api_secret=ERPNEXT_API_SECRET):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.api_secret = api_secret
        self.session = requests.Session()
        self.session.auth = (api_key, api_secret)
        self.session.headers.update({"Content-Type": "application/json"})
    def _handle_error(self, response):
        try:
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error: {e}")
            return None
    def _request(self, method, endpoint, **kwargs):
        url = f"{self.base_url}/api/resource/{endpoint}"
        kwargs.setdefault('timeout', API_TIMEOUT)
        try:
            response = self.session.request(method, url, **kwargs)
            return self._handle_error(response)
        except Exception as e:
            logger.error(f"Request failed: {e}")
            return None
    def get_doc(self, doctype, name):
        data = self._request("GET", f"{doctype}/{name}")
        return data.get("data") if data else None
    def get_list(self, doctype, filters=None, fields=None, limit=None, order_by=None, offset=0):
        params = {"fields": json.dumps(fields or ["name"]), "limit_page_length": limit or 20, "limit_start": offset}
        if filters:
            filter_list = [[k, "=", v] for k, v in filters.items()]
            params["filters"] = json.dumps(filter_list)
        if order_by:
            params["order_by"] = order_by
        data = self._request("GET", doctype, params=params)
        return data.get("data", []) if data else None
    def insert_doc(self, doctype, doc_data):
        doc_data["doctype"] = doctype
        payload = {"data": json.dumps(doc_data)}
        data = self._request("POST", doctype, json=payload)
        return data.get("data") if data else None
    def update_doc(self, doctype, name, doc_data):
        payload = {"data": json.dumps(doc_data)}
        data = self._request("PUT", f"{doctype}/{name}", json=payload)
        return data.get("data") if data else None
    def delete_doc(self, doctype, name):
        data = self._request("DELETE", f"{doctype}/{name}")
        return data is not None
    def check_exists(self, doctype, name):
        doc = self.get_doc(doctype, name)
        return doc is not None
erp_client = ERPNextClient()
