import hashlib
import requests
from ..utils.decorators import log

class MinervaAuth:
    """Handles OAuth2 authentication and credential management."""
    def __init__(self, base_url, database, username, password):
        self.base_url = base_url.rstrip('/')
        self.database = database
        self.username = username
        self.password = password  # Raw password for hashing
        self.token = None
        self.headers = {}
        self.credentials = {
            "username": username,
            "database": database,
            "md5_password": hashlib.md5(password.encode()).hexdigest()
        }

    def authenticate(self) -> bool:
        """Authenticates and updates headers. Returns success status."""
        url = f"{self.base_url}/OAuthServer/connect/token"
        payload = {
            'grant_type': 'password',
            'scope': 'Innovator',
            'client_id': 'IOMApp',
            'username': self.credentials["username"],
            'password': self.credentials["md5_password"],
            'database': self.credentials["database"]
        }
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}

        try:
            response = requests.post(url, headers=headers, data=payload)
            if response.status_code == 200:
                self.token = response.json()["access_token"]
                self.headers = {
                    "Database": self.credentials["database"],
                    "Authorization": f"Bearer {self.token}",
                    "Accept": "application/json"
                }
                return True
            return False
        except Exception as e:
            print(f"Auth Exception: {e}")
            return False