import bpy
import time
import traceback
from . import config
from .lock_visualization import (
    apply_remote_lock,
    lift_remote_lock,
)

COLLAB_OBJECT_TYPES = {'MESH', 'CURVE', 'SURFACE', 'META', 'FONT', 'LIGHT', 'CAMERA'}

# ====================================================================
# 1. ATOMIC NETWORK TRANSACTION PACKAGERS
# ====================================================================

def generate_operator_packet(op, context):
    """
    Serializes a finalized local operator into an optimized network command:
    Splits execution into an explicit Operator Type and clean Parameter structures.
    """
    active_obj = context.active_object
    target_entity = active_obj.name if active_obj else None
    object_type = active_obj.type if active_obj else "MESH"

    op_props = {}
    
    # 🚀 1. FAST-PATH TRANSFORM ROUTING
    if op.bl_idname.startswith("TRANSFORM_OT_") and active_obj:
        op_props["transform_digest"] = {
            "location": tuple(active_obj.location),
            "rotation": tuple(active_obj.rotation_euler),
            "scale":    tuple(active_obj.scale)
        }
        
    # 🚀 2. DISCRETE MACRO PARAMETER DIGESTION
    else:
        for prop in op.rna_type.properties:
            if prop.is_readonly:
                continue
                
            try:
                if op.is_property_set(prop.identifier):
                    val = getattr(op, prop.identifier)
                    
                    # Ensure full JSON compatibility for primitive packaging
                    if hasattr(val, "to_tuple"):
                        val = tuple(val)
                    elif type(val).__name__ == "bpy_prop_array":
                        val = list(val)
                    elif type(val).__name__ == "Vector":
                        val = [val.x, val.y, val.z]
                        
                    op_props[prop.identifier] = val
            except Exception:
                continue

    # Return the clean addressable Operation Type and structural parameter map
    return {
        "type": "COMMAND_EXECUTION",
        "op_id": int(time.time_ns()),
        "client_id": config.CLIENT_ID,
        "operator": op.bl_idname,
        "target": target_entity,
        "object_type": object_type,
        "properties": op_props
    } 

def generate_state_resync_packet(obj):
    """Generates an absolute spatial transformation baseline payload."""
    return {
        "type": "STATE_RESYNC",
        "op_id": int(time.time_ns()),
        "client_id": config.CLIENT_ID,
        "target": obj.name,
        "location": tuple(obj.location),
        "rotation": tuple(obj.rotation_euler),
        "scale": tuple(obj.scale)
    }

# ====================================================================
# 2. DISCRETE COMMAND SNIFFER & UNDO CONTROLLER
# ====================================================================

LAST_OP_TIME = 0
LAST_OP_NAME = ""

def universal_macro_sniffer(*args):
    """
    Universally compatible fallback sniffer. Triggers instantly after any 
    operator macro finishes executing inside the viewport.
    """
    global LAST_OP_TIME, LAST_OP_NAME
    
    if config.IS_PROCESSING_REMOTE_OP:
        return

    # Grabs the last executed operator from the active context window context
    op = getattr(bpy.context, "active_operator", None)
    if not op:
        return

    # Filter out layout adjustments, UI navigation, and workspace renders
    if op.bl_idname.startswith(("WM_", "SCREEN_", "INFO_", "OUTLINER_", "VIEW3D_", "ANIM_")):
        return

    # ⏱️ 50ms Debounce Window for smooth slider adjustments
    current_time = time.time()
    if op.bl_idname == LAST_OP_NAME and (current_time - LAST_OP_TIME) < 0.05:
        return
        
    LAST_OP_TIME = current_time
    LAST_OP_NAME = op.bl_idname

    try:
        print(f"🎬 [COLLAB SNIFFER] Universally caught local action: {op.bl_idname}")
        packet = generate_operator_packet(op, bpy.context)
        config.OUTBOUND_QUEUE.put(packet)
    except Exception as e:
        print(f"❌ [COLLAB SNIFFER ERROR] Failed to parse local operator: {e}")

def unified_command_sniffer(op, context):
    """
    Global operator sniffer hook. Catches finalized discrete actions 
    instantly at the C-layer and dispatches them before they hit the undo stack.
    """
    global LAST_OP_TIME, LAST_OP_NAME
    
    if config.IS_PROCESSING_REMOTE_OP:
        return

    if op.bl_idname.startswith(("WM_", "SCREEN_", "INFO_", "OUTLINER_", "VIEW3D_", "ANIM_")):
        return

    current_time = time.time()
    if op.bl_idname == LAST_OP_NAME and (current_time - LAST_OP_TIME) < 0.05:
        return
        
    LAST_OP_TIME = current_time
    LAST_OP_NAME = op.bl_idname

    try:
        print(f"🎬 [COLLAB SNIFFER] Local Action caught: {op.bl_idname}")
        if (op.bl_idname not in config.RESTRICTED_COMMANDS):
            packet = generate_operator_packet(op, context)
            config.OUTBOUND_QUEUE.put(packet)
    except Exception as e:
        print(f"❌ [COLLAB SNIFFER ERROR] Failed to serialize local operator: {e}")


@bpy.app.handlers.persistent
def local_undo_redo_handler(scene):
    """Triggers immediately after a local Ctrl+Z or Ctrl+Y event."""
    if config.IS_PROCESSING_REMOTE_OP:
        return
        
    active_obj = bpy.context.active_object
    if active_obj and active_obj.name in config.LOCAL_LOCKS:
        try:
            print(f"⏪ [UNDO/REDO EVENT] Local history shift caught. Resyncing object: {active_obj.name}")
            packet = generate_state_resync_packet(active_obj)
            config.OUTBOUND_QUEUE.put(packet)
        except Exception as e:
            print(f"❌ [COLLAB HISTORY ERROR] Failed to broadcast state rollback: {e}")

# ====================================================================
# 3. RUNTIME DEPSGRAPH SYSTEM LOCKS & EDIT MODE SNAPSHOTS
# ====================================================================

# 🚀 Track mode changes dynamically to run our transaction commit logic
LAST_KNOWN_MODE = "OBJECT"

def tracking_and_lock_evaluator(scene, depsgraph):
    """
    Monitors object selection boundaries inside the frame graph to 
    dispatch lock assertions, state clearances, and Edit Mode commits.
    """
    global LAST_KNOWN_MODE
    if config.IS_PROCESSING_REMOTE_OP:
        return
        
    try:
        view_layer = bpy.context.view_layer
        active_obj = view_layer.objects.active if view_layer else None
        
        # ─── 🚀 THE TRANSACT-ON-EXIT EDIT MODE GATEWAY ───
        if active_obj and active_obj.type == 'MESH':
            current_mode = active_obj.mode
            
            # Detect the sharp transition out of Edit Mode back into Object Mode
            if LAST_KNOWN_MODE == 'EDIT' and current_mode == 'OBJECT':
                try:
                    mesh = active_obj.data
                    vertex_coords = [tuple(v.co) for v in mesh.vertices]
                    
                    commit_packet = {
                        "type": "BMESH_COMMIT_SYNC",
                        "op_id": int(time.time_ns()),
                        "client_id": config.CLIENT_ID,
                        "target": active_obj.name,
                        "vertices": vertex_coords
                    }
                    config.OUTBOUND_QUEUE.put(commit_packet)
                    print(f"📦 [COLLAB COMMIT] Edit Mode exited. Committing raw topology vectors for {active_obj.name} ({len(vertex_coords)} vertices).")
                except Exception as bmesh_err:
                    print(f"❌ [COLLAB COMMIT ERROR] Failed to package mesh snapshot: {bmesh_err}")
            
            LAST_KNOWN_MODE = current_mode

        # ─── LOCK EVALUATION LANE ───
        current_selected = set(
            obj.name for obj in scene.objects 
            if obj.select_get() and obj.type in COLLAB_OBJECT_TYPES
        )
        
        # 🔓 Handle Selections Released
        deselected_entities = config.SELECTED_OBJECTS_CACHE - current_selected
        for entity_id in deselected_entities:
            if entity_id in scene.objects:
                obj = scene.objects[entity_id]
                print(f"🔓 [COLLAB LOCK] Releasing lock asset: {entity_id}")
                
                sync_packet = generate_state_resync_packet(obj)
                config.OUTBOUND_QUEUE.put(sync_packet)
                
                unlock_packet = {
                    "type": "LOCK_TRANSACTION",
                    "client_id": config.CLIENT_ID,
                    "target": entity_id,
                    "action": "RELEASE"
                }
                config.OUTBOUND_QUEUE.put(unlock_packet)
                config.LOCAL_LOCKS.discard(entity_id)
        
        # 🔒 Handle New Selections
        newly_selected = current_selected - config.SELECTED_OBJECTS_CACHE
        for entity_id in newly_selected:
            print(f"🔒 [COLLAB LOCK] Requesting exclusive workspace control: {entity_id}")
            lock_packet = {
                "type": "LOCK_TRANSACTION",
                "client_id": config.CLIENT_ID,
                "target": entity_id,
                "action": "ACQUIRE_EXCLUSIVE"
            }
            config.OUTBOUND_QUEUE.put(lock_packet)
            config.LOCAL_LOCKS.add(entity_id)
            
        config.SELECTED_OBJECTS_CACHE = current_selected

    except Exception as e:
        print(f"❌ [COLLAB DEPSGRAPH ERROR] Lock evaluation failed: {e}")


def flush_active_locks():
    """Safety clear hook on addon disconnect to prevent ghost locking properties in rooms."""
    print("[COLLAB] Tearing down engine. Flushing active transaction locks...")
    for entity_id in list(config.SELECTED_OBJECTS_CACHE):
        lock_packet = {
            "type": "LOCK_TRANSACTION",
            "client_id": config.CLIENT_ID,
            "target": entity_id,
            "action": "RELEASE"
        }
        config.OUTBOUND_QUEUE.put(lock_packet)
        
    config.SELECTED_OBJECTS_CACHE.clear()
    config.LOCAL_LOCKS.clear()

# ====================================================================
# 4. SUBSYSTEM INTERFACE REGISTRATION
# ====================================================================

def register_handlers():
    """Hooks event routing engine into stable app handlers."""
    print("[COLLAB] Registering event tracking infrastructure...")
    unregister_handlers()
    
    if hasattr(bpy.app.handlers, "macro_update_post"):
        bpy.app.handlers.macro_update_post.append(universal_macro_sniffer)
        print("✅ [COLLAB] Stable app macro sniffer hooked successfully.")
    else:
        bpy.app.handlers.depsgraph_update_post.append(universal_macro_sniffer)

    bpy.app.handlers.depsgraph_update_post.append(tracking_and_lock_evaluator)
    bpy.app.handlers.undo_post.append(local_undo_redo_handler)
    bpy.app.handlers.redo_post.append(local_undo_redo_handler)


def unregister_handlers():
    """Cleans up handles securely from structural application channels."""
    flush_active_locks()
    
    if universal_macro_sniffer in getattr(bpy.app.handlers, "macro_update_post", []):
        bpy.app.handlers.macro_update_post.remove(universal_macro_sniffer)
    if universal_macro_sniffer in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(universal_macro_sniffer)
        
    if tracking_and_lock_evaluator in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(tracking_and_lock_evaluator)
    if local_undo_redo_handler in bpy.app.handlers.undo_post:
        bpy.app.handlers.undo_post.remove(local_undo_redo_handler)
    if local_undo_redo_handler in bpy.app.handlers.redo_post:
        bpy.app.handlers.redo_post.remove(local_undo_redo_handler)