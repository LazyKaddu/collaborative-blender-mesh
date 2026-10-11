import socketio
import threading
from . import config
from . import protocol_packer


class CollabNetworkClient:
    def __init__(self, server_url):
        self.server_url = server_url

        # Socket.IO client
        self.sio = socketio.Client(
            reconnection=True,
            reconnection_attempts=0,
            reconnection_delay=1
        )

        self.is_running = False

        # Bind events
        self.sio.on("connect", self.on_connect)
        self.sio.on("disconnect", self.on_close)
        self.sio.on("message", self.on_message)

    def connect(self):
        """Start Socket.IO connection in background thread"""
        self.is_running = True

        def run():
            try:
                self.sio.connect(self.server_url, transports=["websocket"])
                self.sio.wait()
            except Exception as e:
                print(f"[COLLAB NETWORK ERROR]: {e}")

        self.thread = threading.Thread(target=run, daemon=True)
        self.thread.start()

        print(f"[COLLAB NETWORK] Socket.IO connecting to {self.server_url}")

    # -------------------------
    # EVENTS
    # -------------------------

    def on_connect(self):
        print("[COLLAB NETWORK] Connected to server")

        self.sio.emit("join", {
            "room_id": config.ROOM_ID,
            "client_id": config.CLIENT_ID
        })

    def on_message(self, data):
        """Incoming messages from server"""
        print("raw data:", data)

        # If server sends binary (MsgPack), decode it
        if isinstance(data, (bytes, bytearray)):
            data = protocol_packer.unpack_operation(data)

        op_type = data.get("type")

        if op_type == "connectionStatus":
            print("[SERVER] Ready")

        elif op_type == "join_accepted":
            print("joined successfully to the network")
            print(data)

        else:
            print("data received:", data)
            config.INBOUND_QUEUE.append(data)

    def send_operation(self, op):
        """Send outgoing operation"""

        # Socket.IO binary send
        self.sio.emit("message", op)

    def on_close(self):
        self.is_running = False
        print("[COLLAB NETWORK] Connection closed.")

client = CollabNetworkClient(config.SERVER_URL)