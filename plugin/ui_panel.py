import bpy
import threading
import os
import random
import string
# Import the background logic blocks we created earlier
from .api_client import CollabAPIClient
from . import scene_manager
from . import config
from . import network_client
from . import sync_loop
from .core_handlers import register_handlers  # 🚀 Added handler hook

# Initialize our API client instance globally within the module
api = CollabAPIClient()

# ====================================================================
# PROPERTY GROUP FOR UI STATE PERSISTENCE
# ====================================================================
class MultiuserCollabProperties(bpy.types.PropertyGroup):
    """Stores collaboration session settings and state."""
    
    is_connected: bpy.props.BoolProperty(
        name="Connected",
        description="Whether the client is connected to a room",
        default=False
    )
    
    server_url: bpy.props.StringProperty(
        name="Server URL",
        description="WebSocket server address",
        default="http://localhost:8080"
    )
    
    client_name: bpy.props.StringProperty(
        name="Client Name",
        description="Display name for this client",
        default="User"
    )
    
    room_id: bpy.props.StringProperty(
        name="Room ID",
        description="ID of the collaboration room",
        default=""
    )


class MULTIUSER_PT_collaboration_panel(bpy.types.Panel):
    """Creates a custom UI Sidebar panel inside the 3D Viewport N-Panel."""
    bl_label = "Multiuser Collab Engine"
    bl_idname = "MULTIUSER_PT_collaboration_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Collab Engine'

    def draw(self, context):
        layout = self.layout
        props = getattr(context.scene, "multiuser_collab_props", None)
        if not props:
            layout.label(text="Error: Properties not initialized", icon='ERROR')
            return

        # --- 1. STATUS MONITOR ---
        box_status = layout.box()
        if props.is_connected:
            box_status.label(text=f"CONNECTED: {props.client_name}", icon='FUND')
            box_status.label(text=f"Room: {props.room_id}", icon='WORLD')
            box_status.operator("multiuser.disconnect_session", text="Leave Room", icon='CANCEL')
        else:
            box_status.label(text="STATUS: DISCONNECTED", icon='RADIOBUT_OFF')

        # --- 2. CONFIGURATION & ENTRY FIELDS ---
        if not props.is_connected:
            box_setup = layout.box()
            box_setup.label(text="Network Setup", icon='URL')
            box_setup.prop(props, "server_url", text="Server")
            box_setup.prop(props, "client_name", text="Name")
            
            box_access = layout.box()
            box_access.label(text="Room Access", icon='GROUP')
            box_access.prop(props, "room_id", text="Room ID")
            
            box_access.operator("multiuser.join_room", text="Join Existing Room", icon='PLAY')
            box_access.operator("multiuser.create_room", text="Create Fresh Room", icon='ADD')

        # --- 3. STATE SYNCHRONIZATION ---
        box_sync = layout.box()
        box_sync.label(text="State Management", icon='FILE_REFRESH')
        
        op_row = box_sync.row()
        op_row.operator("multiuser.flush_update", text="Flush Update", icon='FILE_TICK')
        
        if not props.is_connected:
            op_row.enabled = False


# ====================================================================
# ASYNCHRONOUS OPERATOR ACTIONS
# ====================================================================

class MULTIUSER_OT_create_room(bpy.types.Operator):
    bl_idname = "multiuser.create_room"
    bl_label = "Create Fresh Room"
    
    _thread = None
    _status = "IDLE"
    _room_id_cache = ""

    def modal(self, context, event):
        if event.type == 'TIMER':
            # Monitor background worker status
            if not self._thread.is_alive():
                props = context.scene.multiuser_collab_props
                context.window_manager.event_timer_remove(self._timer)
                
                if self._status == "SUCCESS":
                    props.room_id = self._room_id_cache
                    props.is_connected = True
                    self.report({'INFO'}, f"Room spawned and live on Supabase: {props.room_id}")
                    
                    # 1. Seed historical baseline vectors right now 🚀
                    scene_manager.prime_local_collaboration_cache()
                    
                    # 2. Connect client engine to websocket cluster
                    network_client.client.server_url = "ws://localhost:8765"
                    network_client.client.connect()
                    
                    # 3. Transmit structural identity payload map
                    network_client.client.send_operation({
                        "type": "join",
                        "room_id": props.room_id,
                        "client_id": config.CLIENT_ID
                    })
                    
                    # 4. Turn on viewport capture loops
                    register_handlers()
                    sync_loop.start_sync()
                    self.report({'INFO'}, "WebSocket connected and sync loop started.")
                else:
                    self.report({'ERROR'}, "Failed to push baseline snapshot to cloud.")
                return {'FINISHED'}
            
        return {'PASS_THROUGH'}

    def execute(self, context):
        props = context.scene.multiuser_collab_props
        api.base_url = props.server_url  # Bind base client to match user's UI config entry
        
        self.report({'INFO'}, "Compressing workspace with Draco...")
        filepath, filename = scene_manager.export_draco_snapshot()
        
        # Request access ticket from the Express server
        ticket = api.create_room(filename)
        if not ticket:
            self.report({'ERROR'}, "Express API connection dropped.")
            return {'CANCELLED'}
        
        self._room_id_cache = ticket["room_id"]
        upload_url = ticket["upload_url"]
        
        # Cache globally for background ticks
        config.ROOM_ID = self._room_id_cache

        # Worker thread executes binary pipeline safely in the background
        def upload_worker():
            if api.upload_file(upload_url, filepath):
                self._status = "SUCCESS"
                try: os.remove(filepath)
                except: pass
            else:
                self._status = "FAILED"

        self._thread = threading.Thread(target=upload_worker, daemon=True)
        self._thread.start()

        context.window_manager.modal_handler_add(self)
        self._timer = context.window_manager.event_timer_add(0.1, window=context.window)
        return {'RUNNING_MODAL'}


class MULTIUSER_OT_join_room(bpy.types.Operator):
    bl_idname = "multiuser.join_room"
    bl_label = "Join Room"
    
    _thread = None
    _status = "IDLE"
    _meta_cache = None

    def modal(self, context, event):
        if event.type == 'TIMER':
            if not self._thread.is_alive():
                props = context.scene.multiuser_collab_props
                context.window_manager.event_timer_remove(self._timer)
                
                if self._status == "SUCCESS":
                    # Wiping scene and reading snapshot must run on the main thread for safety
                    scene_manager.clear_entire_scene()
                    
                    temp_path = os.path.join(bpy.app.tempdir, "incoming_baseline.glb")
                    scene_manager.import_draco_snapshot(temp_path)
                    
                    try: os.remove(temp_path)
                    except: pass
                    
                    # 1. Seed historical baseline vectors right after scene finishes importing! 🚀
                    scene_manager.prime_local_collaboration_cache()
                    
                    props.is_connected = True
                    self.report({'INFO'}, f"Synchronized with Room: {props.room_id}")
                    
                    # 2. Match socket destination URL
                    network_client.client.server_url = "ws://localhost:8765"
                    network_client.client.connect()
                    
                    # 3. Transmit structural identity payload map
                    network_client.client.send_operation({
                        "type": "join",
                        "room_id": props.room_id,
                        "client_id": config.CLIENT_ID
                    })
                    
                    # 4. Turn on viewport capture loops
                    register_handlers()
                    sync_loop.start_sync()
                    self.report({'INFO'}, "WebSocket connected and sync loop started.")
                else:
                    self.report({'ERROR'}, "Failed downloading scene state baseline.")
                return {'FINISHED'}
            
        return {'PASS_THROUGH'}

    def execute(self, context):
        props = context.scene.multiuser_collab_props
        if not props.room_id.strip():
            self.report({'ERROR'}, "Room ID field cannot be empty!")
            return {'CANCELLED'}
            
        api.base_url = props.server_url
        config.ROOM_ID = props.room_id

        self.report({'INFO'}, f"Requesting download tokens for room {props.room_id}...")
        meta = api.get_room_metadata(props.room_id)
        if not meta:
            self.report({'ERROR'}, "Target Room doesn't exist or server timed out.")
            return {'CANCELLED'}

        download_url = meta["download_url"]
        config.SNAPSHOT_TIMESTAMP = meta["timestamp"]

        def download_worker():
            target_path = os.path.join(bpy.app.tempdir, "incoming_baseline.glb")
            if api.download_file(download_url, target_path):
                self._status = "SUCCESS"
            else:
                self._status = "FAILED"

        self._thread = threading.Thread(target=download_worker, daemon=True)
        self._thread.start()

        context.window_manager.modal_handler_add(self)
        self._timer = context.window_manager.event_timer_add(0.1, window=context.window)
        return {'RUNNING_MODAL'}


class MULTIUSER_OT_disconnect_session(bpy.types.Operator):
    bl_idname = "multiuser.disconnect_session"
    bl_label = "Leave Room"
    
    def execute(self, context):
        props = context.scene.multiuser_collab_props
        props.is_connected = False
        config.ROOM_ID = None
        
        # Stop sync loop and close WebSocket connection
        sync_loop.stop_sync()
        if network_client.client.ws:
            network_client.client.ws.close()
            network_client.client.is_running = False
        
        self.report({'INFO'}, "Disconnected from room.")
        return {'FINISHED'}


class MULTIUSER_OT_flush_update(bpy.types.Operator):
    bl_idname = "multiuser.flush_update"
    bl_label = "Flush Changes"
    
    _thread = None
    _status = "IDLE"

    def modal(self, context, event):
        if event.type == 'TIMER':
            if not self._thread.is_alive():
                context.window_manager.event_timer_remove(self._timer)
                
                if self._status == "SUCCESS":
                    self.report({'INFO'}, "Global scene state flushed and synchronized safely!")
                else:
                    self.report({'ERROR'}, "Failed to flush current workspace state to cloud storage.")
                return {'FINISHED'}
            
        return {'PASS_THROUGH'}

    def execute(self, context):
        props = context.scene.multiuser_collab_props
        
        # Guard: Ensure we are actually in a room before allowing a flush
        if not props.is_connected or not props.room_id:
            self.report({'ERROR'}, "Cannot flush changes: You are not connected to a room.")
            return {'CANCELLED'}
            
        self.report({'INFO'}, "Capturing fresh workspace state...")
        filepath, filename = scene_manager.export_draco_snapshot()
        
        # Step 1: Request a fresh upload URL specifically for an existing room update
        try:
            import requests
            url = f"{props.server_url}/api/room/flush"
            response = requests.post(url, json={
                "room_id": props.room_id,
                "filename": filename,
                "client_id": api.client_id
            }, timeout=10)
            ticket = response.json()
        except Exception as e:
            print(f"[COLLAB API ERROR] Flush request failed: {e}")
            self.report({'ERROR'}, "Express server unreachable.")
            return {'CANCELLED'}
            
        if "upload_url" not in ticket:
            self.report({'ERROR'}, "Server denied state overwrite permissions.")
            return {'CANCELLED'}
            
        upload_url = ticket["upload_url"]

        # Step 2: Thread out the upload to keep the viewports completely fluid
        def flush_worker():
            if api.upload_file(upload_url, filepath):
                self._status = "SUCCESS"
                try: os.remove(filepath)
                except: pass
            else:
                self._status = "FAILED"

        self._thread = threading.Thread(target=flush_worker, daemon=True)
        self._thread.start()

        context.window_manager.modal_handler_add(self)
        self._timer = context.window_manager.event_timer_add(0.1, window=context.window)
        return {'RUNNING_MODAL'}