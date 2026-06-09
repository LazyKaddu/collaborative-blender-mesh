import bpy

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
            
            # Using guaranteed safe icons (PLAY and ADD)
            box_access.operator("multiuser.join_room", text="Join Existing Room", icon='PLAY')
            box_access.operator("multiuser.create_room", text="Create Fresh Room", icon='ADD')

        # --- 3. STATE SYNCHRONIZATION MOCK ---
        box_sync = layout.box()
        box_sync.label(text="State Management", icon='FILE_REFRESH')
        
        op_row = box_sync.row()
        op_row.operator("multiuser.flush_update", text="Flush Update", icon='FILE_TICK')
        
        if not props.is_connected:
            op_row.enabled = False

# ====================================================================
# OPERATOR ACTIONS STUBS
# ====================================================================

class MULTIUSER_OT_create_room(bpy.types.Operator):
    bl_idname = "multiuser.create_room"
    bl_label = "Create Fresh Room"
    
    def execute(self, context):
        props = context.scene.multiuser_collab_props
        import random, string
        props.room_id = "RM_" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
        props.is_connected = True
        self.report({'INFO'}, f"Room spawned: {props.room_id}")
        return {'FINISHED'}

class MULTIUSER_OT_join_room(bpy.types.Operator):
    bl_idname = "multiuser.join_room"
    bl_label = "Join Room"
    
    def execute(self, context):
        props = context.scene.multiuser_collab_props
        if not props.room_id.strip():
            self.report({'ERROR'}, "Room ID field cannot be empty!")
            return {'CANCELLED'}
        props.is_connected = True
        self.report({'INFO'}, f"Connected to {props.room_id}")
        return {'FINISHED'}

class MULTIUSER_OT_disconnect_session(bpy.types.Operator):
    bl_idname = "multiuser.disconnect_session"
    bl_label = "Leave Room"
    
    def execute(self, context):
        props = context.scene.multiuser_collab_props
        props.is_connected = False
        self.report({'INFO'}, "Disconnected from session.")
        return {'FINISHED'}

class MULTIUSER_OT_flush_update(bpy.types.Operator):
    bl_idname = "multiuser.flush_update"
    bl_label = "Flush Changes"
    
    def execute(self, context):
        self.report({'INFO'}, "State snapshot synchronized cleanly.")
        return {'FINISHED'}

# ====================================================================
# REGISTER HOOK LAYOUTS
# ====================================================================

class MultiuserCollabProperties(bpy.types.PropertyGroup):
    server_url: bpy.props.StringProperty(name="Server URL", default="ws://localhost:8080")
    client_name: bpy.props.StringProperty(name="Client Name", default="Artist")
    room_id: bpy.props.StringProperty(name="Room ID", default="")
    is_connected: bpy.props.BoolProperty(name="Is Connected", default=False)

classes = (
    MultiuserCollabProperties,
    MULTIUSER_PT_collaboration_panel,
    MULTIUSER_OT_create_room,
    MULTIUSER_OT_join_room,
    MULTIUSER_OT_disconnect_session,
    MULTIUSER_OT_flush_update
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.multiuser_collab_props = bpy.props.PointerProperty(type=MultiuserCollabProperties)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.multiuser_collab_props