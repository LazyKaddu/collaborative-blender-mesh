import requests
import uuid
from . import config

class CollabAPIClient:
    def __init__(self, base_url="http://localhost:8080"):
        self.base_url = base_url
        # Generate a unique client ID for this Blender instance session
        self.client_id = str(uuid.uuid4())

        config.CLIENT_ID = self.client_id


    def create_room(self, filename):
        """Asks Express for an upload ticket (Pre-signed URL)."""
        try:
            url = f"{self.base_url}/api/room/create"
            response = requests.post(url, json={
                "filename": filename, 
                "client_id": self.client_id
            }, timeout=10)
            return response.json() # Expects: { room_id, upload_url, download_url }
        except Exception as e:
            print(f"[COLLAB API ERROR] Create Room failed: {e}")
            return None

    def get_room_metadata(self, room_id):
        """Fetches the snapshot link and timestamp for a room."""
        try:
            url = f"{self.base_url}/api/room/join/{room_id}"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                return response.json() # Expects: { download_url, timestamp }
            return None
        except Exception as e:
            print(f"[COLLAB API ERROR] Fetch metadata failed: {e}")
            return None

    def upload_file(self, upload_url, filepath):
        """Pipes the binary GLB straight to Supabase via the pre-signed URL."""
        try:
            with open(filepath, 'rb') as f:
                headers = {"Content-Type": "application/octet-stream"}
                response = requests.put(upload_url, data=f, headers=headers, timeout=60)
                return response.status_code == 200
        except Exception as e:
            print(f"[COLLAB API ERROR] Binary upload failed: {e}")
            return False

    def download_file(self, download_url, target_path):
        """Downloads the baseline snapshot GLB to your local temp directory."""
        try:
            print(f"download url: {download_url}")
            response = requests.get(download_url, stream=True, timeout=60)
            if response.status_code == 200:
                with open(target_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                return True
            return False
        except Exception as e:
            print(f"[COLLAB API ERROR] Download failed: {e}")
            return False
    def get_room_history(self,room_id):
        response = requests.get(
            f"{self.base_url}/api/operation/history/{room_id}"
        )

        if response.status_code != 200:
            return []

        return response.json()["operations"]