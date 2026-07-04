import sqlite3
import json
import logging
from typing import Optional, Dict
from datetime import datetime, timedelta
from config import DATABASE_PATH
logger = logging.getLogger(__name__)
class SessionManager:
    def __init__(self, db_path=DATABASE_PATH):
        self.db_path = db_path
        self._init_db()
    def _init_db(self):
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""CREATE TABLE IF NOT EXISTS sessions (chat_id TEXT PRIMARY KEY, module TEXT, step TEXT, state_data TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
                conn.execute("""CREATE TABLE IF NOT EXISTS user_data (chat_id TEXT PRIMARY KEY, customer_name TEXT, is_tenant INTEGER DEFAULT 0, is_guard INTEGER DEFAULT 0, user_name TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
                conn.commit()
        except Exception as e:
            logger.error(f"DB init failed: {e}")
    def create_session(self, chat_id, module, step):
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("INSERT OR REPLACE INTO sessions (chat_id, module, step, state_data, updated_at) VALUES (?, ?, ?, ?, ?)", (str(chat_id), module, step, json.dumps({}), datetime.now()))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Session creation failed: {e}")
            return False
    def get_session(self, chat_id):
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("SELECT * FROM sessions WHERE chat_id = ?", (str(chat_id),))
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Session retrieval failed: {e}")
            return None
    def set_session_value(self, chat_id, key, value):
        try:
            session = self.get_session(chat_id)
            if not session:
                return False
            state_data = json.loads(session.get('state_data', '{}'))
            state_data[key] = str(value)
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("UPDATE sessions SET state_data = ?, updated_at = ? WHERE chat_id = ?", (json.dumps(state_data), datetime.now(), str(chat_id)))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Failed to set session value: {e}")
            return False
    def get_session_value(self, chat_id, key):
        try:
            session = self.get_session(chat_id)
            if not session:
                return ""
            state_data = json.loads(session.get('state_data', '{}'))
            return state_data.get(key, "")
        except Exception as e:
            logger.error(f"Failed to get session value: {e}")
            return ""
    def set_session_step(self, chat_id, step):
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("UPDATE sessions SET step = ?, updated_at = ? WHERE chat_id = ?", (step, datetime.now(), str(chat_id)))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Failed to set session step: {e}")
            return False
    def clear_session(self, chat_id):
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM sessions WHERE chat_id = ?", (str(chat_id),))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Session deletion failed: {e}")
            return False
    def set_user_data(self, chat_id, customer_name, is_tenant=False, is_guard=False, user_name=""):
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("INSERT OR REPLACE INTO user_data (chat_id, customer_name, is_tenant, is_guard, user_name, updated_at) VALUES (?, ?, ?, ?, ?, ?)", (str(chat_id), customer_name, int(is_tenant), int(is_guard), user_name, datetime.now()))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Failed to set user data: {e}")
            return False
    def get_user_data(self, chat_id):
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("SELECT * FROM user_data WHERE chat_id = ?", (str(chat_id),))
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Failed to get user data: {e}")
            return None
    def cleanup_old_sessions(self, days=7):
        try:
            cutoff = datetime.now() - timedelta(days=days)
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("DELETE FROM sessions WHERE updated_at < ?", (cutoff,))
                conn.commit()
                return cursor.rowcount
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")
            return 0
session_manager = SessionManager()
