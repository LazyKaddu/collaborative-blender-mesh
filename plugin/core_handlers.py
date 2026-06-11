import bpy
import time
import traceback
from . import config

COLLAB_OBJECT_TYPES = {'MESH', 'CURVE', 'SURFACE', 'META', 'FONT', 'LIGHT', 'CAMERA'}

# ====================================================================
# ATOMIC NODE & STRUCTURAL OPERATION GENERATORS
# ====================================================================

def generate_lifecycle_op(action, entity_id, object_type="MESH"):
    return {
        "type": "ENTITY_LIFECYCLE",
        "op_id": int(time.time_ns()),
        "client_id": config.CLIENT_ID,
        "payload": {
            "action": action,
            "entity_id": entity_id,
            "object_type": object_type 
        }
    }

def generate_transform_op(obj, initial_state, end_state):
    return {
        "type": "ENTITY_TRANSFORM_TRANSACTION",
        "op_id": int(time.time_ns()),
        "client_id": config.CLIENT_ID,
        "payload": {
            "entity_id": obj.name,
            "object_type": obj.type,
            "initial": {
                "position": initial_state["position"],
                "rotation": initial_state["rotation"],
                "scale":    initial_state["scale"]
            },
            "end": {
                "position": end_state["position"],
                "rotation": end_state["rotation"],
                "scale":    end_state["scale"]
            }
        }
    }

def generate_node_mutation_op(entity_id, target_type, target_name, action, details):
    return {
        "type": "NODE_GRAPH_MUTATION",
        "op_id": int(time.time_ns()),
        "client_id": config.CLIENT_ID,
        "payload": {
            "entity_id": entity_id,
            "target_type": target_type,        
            "target_name": target_name,        
            "action": action,                  
            "details": details                 
        }
    }

def generate_uv_topology_op(obj, initial_uv_data, end_uv_data):
    """Extracts and pairs the initial vs. final UV map data structures."""
    if obj.type != 'MESH' or not obj.data.uv_layers.active:
        return None

    uv_layer = obj.data.uv_layers.active

    return {
        "type": "MESH_TOPOLOGY_MUTATION",
        "op_id": int(time.time_ns()),
        "client_id": config.CLIENT_ID,
        "payload": {
            "entity_id": obj.name,
            "mutation_type": "UV_MAP_TRANSACTION",
            "layer_name": uv_layer.name,
            "initial": {
                "loops": initial_uv_data  
            },
            "end": {
                "loops": end_uv_data      
            }
        }
    }

# ====================================================================
# CORE HIGH-PERFORMANCE DEPSGRAPH DISPATCHER
# ====================================================================

def capture_object_state(obj):
    """Capture complete spatial state of an object with absolute precision rounding."""
    if obj.type not in COLLAB_OBJECT_TYPES:
        return None
    pos = [round(obj.location.x, 4), round(obj.location.y, 4), round(obj.location.z, 4)]
    rot = [round(obj.rotation_euler.x, 4), round(obj.rotation_euler.y, 4), round(obj.rotation_euler.z, 4)]
    scl = [round(obj.scale.x, 4), round(obj.scale.y, 4), round(obj.scale.z, 4)]
    return {"position": pos, "rotation": rot, "scale": scl}


def action_completed_handler(scene):
    """
    Fires when user completes an action (committed via undo/redo step).
    Detects structural and property mutations natively in a single pass.
    """
    try:
        if config.IS_PROCESSING_REMOTE_OP:
            return
        
        props = getattr(scene, "multiuser_collab_props", None)
        if not props or not props.is_connected:
            return

        # 1. Unified Structural Auditing Passes
        current_objects = set(obj.name for obj in scene.objects if obj.type in COLLAB_OBJECT_TYPES)
        
        # Handle Structural Additions
        added_entities = current_objects - config.TRACKED_OBJECTS
        for entity_id in added_entities:
            if entity_id in scene.objects:
                obj = scene.objects[entity_id]
                op = generate_lifecycle_op("CREATE_PRIMITIVE", entity_id, object_type=obj.type)
                print(f"[COLLAB OUTBOUND] CREATE: {entity_id} ({obj.type})")
                config.OUTBOUND_QUEUE.put(op)
                
        # Handle Structural Deletions (With Safe pop checking)
        deleted_entities = config.TRACKED_OBJECTS - current_objects
        for entity_id in deleted_entities:
            op = generate_lifecycle_op("DELETE", entity_id)
            print(f"[COLLAB OUTBOUND] DELETE: {entity_id}")
            config.OUTBOUND_QUEUE.put(op)
            
            # Safe clean pop mutations
            config.ENTITY_LOCAL_CACHE.pop(entity_id, None)
            config.ENTITY_LOCAL_CACHE.pop(f"{entity_id}_uv", None)

        config.TRACKED_OBJECTS = current_objects

        # ====================================================================
        # PROPERTY MUTATION TRANSACTION CHECKS
        # ====================================================================
        for obj in scene.objects:
            if obj.type not in COLLAB_OBJECT_TYPES:
                continue

            # --- BRANCH A: Transform Space Changes ---
            current_state = capture_object_state(obj)
            if current_state is not None:
                cached_state = config.ENTITY_LOCAL_CACHE.get(obj.name)
                
                # Check if cache is completely empty OR if property vectors drifted
                if not cached_state or cached_state["position"] != current_state["position"] or cached_state["rotation"] != current_state["rotation"] or cached_state["scale"] != current_state["scale"]:
                    
                    initial_state = cached_state if cached_state else current_state
                    op = generate_transform_op(obj, initial_state, current_state)
                    print(f"[COLLAB OUTBOUND] Transform Transaction completed: {obj.name}")
                    config.OUTBOUND_QUEUE.put(op)
                    
                    config.ENTITY_LOCAL_CACHE[obj.name] = current_state

            # --- BRANCH B: UV Topology Space Changes ---
            if obj.type == 'MESH' and obj.data.uv_layers.active:
                uv_layer = obj.data.uv_layers.active
                
                current_uv_snapshot = [
                    round(coord, 4)
                    for loop in obj.data.loops 
                    for coord in [uv_layer.data[loop.index].uv.x, uv_layer.data[loop.index].uv.y]
                ]
                
                # 🚀 Fix: Fixed broken string nested token interpolation syntax bug here
                uv_cache_key = f"{obj.name}_uv"
                cached_uv_snapshot = config.ENTITY_LOCAL_CACHE.get(uv_cache_key)
                
                if cached_uv_snapshot != current_uv_snapshot:
                    initial_uv = cached_uv_snapshot if cached_uv_snapshot else current_uv_snapshot
                    op = generate_uv_topology_op(obj, initial_uv, current_uv_snapshot)
                    print(f"[COLLAB OUTBOUND] UV Topology Transaction completed: {obj.name}")
                    config.OUTBOUND_QUEUE.put(op)
                    
                    config.ENTITY_LOCAL_CACHE[uv_cache_key] = current_uv_snapshot

    except Exception as e:
        print(f"\n[COLLAB FATAL ERROR] Action Handler Crashed: {e}")
        traceback.print_exc()
        

def main_scene_dependency_evaluator(scene, depsgraph):
    """
    Lightweight runtime backup evaluator. Handles direct programmatic insertions 
    or pipeline overrides that completely step around native operator undo events.
    """
    try:
        if config.IS_PROCESSING_REMOTE_OP:
            return
        
        props = getattr(scene, "multiuser_collab_props", None)
        if not props or not props.is_connected:
            return

        current_objects = set(obj.name for obj in scene.objects if obj.type in COLLAB_OBJECT_TYPES)
        added_entities = current_objects - config.TRACKED_OBJECTS
        
        for entity_id in added_entities:
            if entity_id in scene.objects:
                obj = scene.objects[entity_id]
                op = generate_lifecycle_op("CREATE_PRIMITIVE", entity_id, object_type=obj.type)
                print(f"[COLLAB OUTBOUND] DEPSGRAPH PROCEDURAL CREATE: {entity_id}")
                config.OUTBOUND_QUEUE.put(op)
                
        config.TRACKED_OBJECTS.update(current_objects)

    except Exception as e:
        print(f"\n[COLLAB FATAL ERROR] Depsgraph Handler Crashed: {e}")
        traceback.print_exc()

# ====================================================================
# SELF-HEALING REGISTRATION HOOKS
# ====================================================================
def register_handlers():
    print("[COLLAB] Registering event handlers...")
    
    # Safely detach previous handle references
    unregister_handlers()
    
    # Append fresh system listeners
    bpy.app.handlers.depsgraph_update_post.append(main_scene_dependency_evaluator)
    bpy.app.handlers.undo_post.append(action_completed_handler)
    bpy.app.handlers.redo_post.append(action_completed_handler)
    
    print("[COLLAB] Handlers registered safely:")
    print("  - depsgraph_update_post (Procedural catch)")
    print("  - undo_post / redo_post (Committed local transactions)")

def unregister_handlers():
    if main_scene_dependency_evaluator in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(main_scene_dependency_evaluator)
    if action_completed_handler in bpy.app.handlers.undo_post:
        bpy.app.handlers.undo_post.remove(action_completed_handler)
    if action_completed_handler in bpy.app.handlers.redo_post:
        bpy.app.handlers.redo_post.remove(action_completed_handler)