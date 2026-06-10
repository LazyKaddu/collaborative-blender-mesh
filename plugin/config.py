import queue

# Core network pipelines
OUTBOUND_QUEUE = queue.Queue()
IS_NETWORK_ALIVE = False
TRACKED_OBJECTS = set()
ENTITY_LOCAL_CACHE = {}
INBOUND_QUEUE = queue.Queue()
IS_PROCESSING_REMOTE_OP = False
# Throttling configurations
LAST_FRAME_TIME = 0
THROTTLE_INTERVAL = 0.033  # ~30hz

# Connection Settings
SERVER_URL = "ws://localhost:8765"
CLIENT_ID = "LOCAL_DEV_USER"

# Room & Session Management
ROOM_ID = None
SNAPSHOT_TIMESTAMP = None