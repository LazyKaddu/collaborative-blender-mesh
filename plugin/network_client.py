import websocket
import threading
import json
import time
from . import config
from . import protocol_packer

class CollabNetworkClient:
    def __init__(self, server_url):
        self.server_url = server_url
        self.ws = None
        self.is_running = False

    def connect(self):
        """Initializes the secure WebSocket connection."""
        self.is_running = True
        # Connect to base WebSocket (room isolation handled by server)
        self.ws = websocket.WebSocketApp(
            self.server_url,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close
        )
        # Run in a background thread to prevent UI lockup
        self.thread = threading.Thread(
            target=self.ws.run_forever, 
            kwargs={"ping_interval": 5, "ping_timeout": 2}, 
            daemon=True
        )
        self.thread.start()
        print(f"[COLLAB NETWORK] WebSocket connecting to {self.server_url}")

    def on_message(self, ws, message):
        """Routes incoming packets into the Blender inbound queue."""
        data = protocol_packer.unpack_operation(message)
        print(data)
        op_type = data.get("type")

        if op_type == "connectionStatus":
            join_packet = {
                "type": "join",
                "room_id": config.ROOM_ID,
                "client_id": config.CLIENT_ID
            }

            join_packet_packed = protocol_packer.pack_operation(join_packet)
            self.send_operation(join_packet_packed)
        
        else:
            print("data recieved from websocket ",data)
            config.INBOUND_QUEUE.put(data)

    def send_operation(self, op):
        """Outgoing pipe for local operations."""
        if self.ws and self.ws.sock and self.ws.sock.connected:
            self.ws.send(op, opcode=websocket.ABNF.OPCODE_BINARY)

    def on_error(self, ws, error):
        print(f"[COLLAB NETWORK ERROR]: {error}")

    def on_close(self, ws, close_status_code, close_msg):
        self.is_running = False
        print("[COLLAB NETWORK] Connection closed.")

# --- Singleton Instance ---
client = CollabNetworkClient(config.WS_URL)