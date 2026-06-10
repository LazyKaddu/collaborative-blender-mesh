import asyncio
import json
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import websockets

# --- HTTP STORAGE CONFIG ---
STORAGE_DIR = "./mock_storage"
os.makedirs(STORAGE_DIR, exist_ok=True)
active_rooms = {}

class MockHTTPHandler(BaseHTTPRequestHandler):
    
    def do_GET(self):
        # 1. HANDLE ROOM METADATA FETCH (When your friend joins)
        if self.path.startswith("/api/room/join/"):
            room_id = self.path.split("/")[-1]
            room = active_rooms.get(room_id)
            
            if room:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(room).encode('utf-8'))
            else:
                self.send_response(404)
                self.end_headers()
                
        # 2. HANDLE BINARY DOWNLOAD (When your friend's Blender downloads the GLB file)
        elif self.path.startswith("/download/"):
            filename = self.path.split("/")[-1]
            target_path = os.path.join(STORAGE_DIR, filename)
            
            if os.path.exists(target_path):
                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                self.end_headers()
                with open(target_path, 'rb') as f:
                    self.wfile.write(f.read())
            else:
                self.send_response(404)
                self.end_headers()
    
    def do_POST(self):
        if self.path in ["/api/room/create", "/api/room/flush"]:
            content_length = int(self.headers['Content-Length'])
            body = json.loads(self.rfile.read(content_length).decode('utf-8'))
            room_id = body.get("room_id", "RM_TEST123")
            filename = body.get("filename", "scene_snapshot.glb")
            
            upload_url = f"http://localhost:8080/upload/{filename}"
            download_url = f"http://localhost:8080/download/{filename}"
            
            active_rooms[room_id] = {"filename": filename, "download_url": download_url, "timestamp": 1717945200}
            
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"room_id": room_id, "upload_url": upload_url, "download_url": download_url}).encode('utf-8'))

    def do_PUT(self):
        if self.path.startswith("/upload/"):
            filename = self.path.split("/")[-1]
            content_length = int(self.headers['Content-Length'])
            with open(os.path.join(STORAGE_DIR, filename), 'wb') as f:
                f.write(self.rfile.read(content_length))
            self.send_response(200)
            self.end_headers()

# --- WEBSOCKET REAL-TIME SYNC CONFIG ---
connected_clients = {}  # Map of room_id -> set of websockets

async def ws_handler(websocket):
    room_id = None
    
    try:
        async for message in websocket:
            data = json.loads(message)
            
            # Extract room from message payload (client sends it)
            room_id = data.get("room_id") or room_id
            
            if not room_id:
                print(f"⚠️ [WS SERVER] Message without room_id: {data}")
                continue
            
            # Register this client in the room
            if room_id not in connected_clients:
                connected_clients[room_id] = set()
            
            if websocket not in connected_clients[room_id]:
                connected_clients[room_id].add(websocket)
                print(f"\n⚡ [WS SERVER] Client connected to room '{room_id}'. Room clients: {len(connected_clients[room_id])}")
            
            print(f"📥 [WS SERVER] Room '{room_id}' - Received Data: {data}")
            
            # Broadcast to OTHER clients in same room only
            broadcast_tasks = [
                client.send(json.dumps(data)) 
                for client in connected_clients[room_id] if client != websocket
            ]
            if broadcast_tasks:
                await asyncio.gather(*broadcast_tasks)
                
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        if room_id and room_id in connected_clients:
            connected_clients[room_id].discard(websocket)
            print(f"❌ [WS SERVER] Client disconnected from room '{room_id}'. Remaining: {len(connected_clients[room_id])}")

def start_http_server():
    httpd = HTTPServer(("localhost", 8080), MockHTTPHandler)
    httpd.serve_forever()

async def main():
    # Run HTTP Server in a background thread so it doesn't block Asyncio
    threading.Thread(target=start_http_server, daemon=True).start()
    print("🚀 Local Mock S3 & Express Server running on http://localhost:8080")

    # Start WebSocket Server
    async with websockets.serve(ws_handler, "localhost", 8765):
        print("⚡ Live WebSocket Server listening on ws://localhost:8765")
        await asyncio.Event().wait() # Keep server running indefinitely

if __name__ == "__main__":
    asyncio.run(main())