import queue

# Core network pipelines
OUTBOUND_QUEUE = queue.Queue()
INBOUND_QUEUE = queue.Queue()

# Thread gates and operational state flags
IS_NETWORK_ALIVE = False
IS_PROCESSING_REMOTE_OP = False
IS_INITIAL_SYNC = False

# 🚀 Multiuser Entity Tracking & Locking Matrices
TRACKED_OBJECTS = set()
SELECTED_OBJECTS_CACHE = set()
LOCAL_LOCKS = set()              # 🧠 FIX: Added missing local ownership tracking set
ENTITY_LOCAL_CACHE = {}
RESTRICTED_COMMANDS = set(["OBJECT_OT_editmode_toggle",])

# Throttling configurations
LAST_FRAME_TIME = 0
THROTTLE_INTERVAL = 0.033  # ~30hz

# Connection Settings
SERVER_URL = "ws://localhost:8765"
CLIENT_ID = "LOCAL_DEV_USER"

# Room & Session Management
ROOM_ID = None
SNAPSHOT_TIMESTAMP = None



ANY_ACTIVE_SNIFFER_HANDLE = None