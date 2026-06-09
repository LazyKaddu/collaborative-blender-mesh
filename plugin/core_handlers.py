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

def generate_transform_op(obj):
    pos = obj.location
    rot = obj.rotation_euler
    scale = obj.scale
    return {
        "type": "ENTITY_TRANSFORM",
        "op_id": int(time.time_ns()),
        "client_id": config.CLIENT_ID,
        "payload": {
            "entity_id": obj.name,
            "object_type": obj.type,
            "position": [round(pos.x, 4), round(pos.y, 4), round(pos.z, 4)],
            "rotation": [round(rot.x, 4), round(rot.y, 4), round(rot.z, 4)],
            "scale":    [round(scale.x, 4), round(scale.y, 4), round(scale.z, 4)]
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

def generate_uv_topology_op(obj):
    """Extracts current UV map data and serializes it for network transmission."""
    if obj.type != 'MESH' or not obj.data.uv_layers.active:
        return None

    uv_layer = obj.data.uv_layers.active
    # Flatten UV data: [u0, v0, u1, v1, ...]
    uv_data = []
    for loop in obj.data.loops:
        uv = uv_layer.data[loop.index].uv
        uv_data.extend([uv.x, uv.y])

    return {
        "type": "MESH_TOPOLOGY_MUTATION",
        "op_id": int(time.time_ns()),
        "client_id": config.CLIENT_ID,
        "payload": {
            "entity_id": obj.name,
            "mutation_type": "UV_MAP_EDITED",
            "layer_name": uv_layer.name,
            "loops": uv_data
        }
    }

# ====================================================================
# CORE HIGH-PERFORMANCE DEPSGRAPH DISPATCHER
# ====================================================================

def main_scene_dependency_evaluator(scene, depsgraph):
    try:
        # 1. THE ROOM GUARD: Only run tracking if we are in an active session
        if config.IS_PROCESSING_REMOTE_OP:
            return
        
        props = getattr(scene, "multiuser_collab_props", None)

        if not props or not props.is_connected:
            return

        from . import operations_tracker
        
        current_time = time.time()
        current_objects = set(obj.name for obj in scene.objects if obj.type in COLLAB_OBJECT_TYPES)
        
        # Handle Structural Additions
        added_entities = current_objects - config.TRACKED_OBJECTS
        for entity_id in added_entities:
            if entity_id in scene.objects:
                obj = scene.objects[entity_id]
                op = generate_lifecycle_op("CREATE_PRIMITIVE", entity_id, object_type=obj.type)
                print(f"[COLLAB OUTBOUND] Queueing CREATE: {entity_id} ({obj.type})")
                config.OUTBOUND_QUEUE.put(op)
                
        # Handle Structural Deletions
        deleted_entities = config.TRACKED_OBJECTS - current_objects
        for entity_id in deleted_entities:
            op = generate_lifecycle_op("DELETE", entity_id)
            print(f"[COLLAB OUTBOUND] Queueing DELETE: {entity_id}")
            config.OUTBOUND_QUEUE.put(op)
            if entity_id in config.ENTITY_LOCAL_CACHE:
                del config.ENTITY_LOCAL_CACHE[entity_id]

        config.TRACKED_OBJECTS = current_objects

        # Throttle structural coordinate updates safely
        throttle_interval = getattr(config, "THROTTLE_INTERVAL", 0.05)
        last_frame = getattr(config, "LAST_FRAME_TIME", 0.0)
        is_throttled = (current_time - last_frame) < throttle_interval

        # 2. O(M) Data-Block Iteration
        for update in depsgraph.updates:
            id_block = update.id
            print("update in despgraph ",id_block)
            
            # --- PATH A: TRANSFORM & UV MUTATIONS ---
            if isinstance(id_block, bpy.types.Object) and id_block.type in COLLAB_OBJECT_TYPES:
                
                if (update.is_updated_transform or update.is_updated_geometry) and not is_throttled:
                    pos = [round(id_block.location.x, 4), round(id_block.location.y, 4), round(id_block.location.z, 4)]
                    rot = [round(id_block.rotation_euler.x, 4), round(id_block.rotation_euler.y, 4), round(id_block.rotation_euler.z, 4)]
                    scl = [round(id_block.scale.x, 4), round(id_block.scale.y, 4), round(id_block.scale.z, 4)]
                    
                    current_spatial_state = (tuple(pos), tuple(rot), tuple(scl))
                    
                    if config.ENTITY_LOCAL_CACHE.get(id_block.name) != current_spatial_state:
                        config.ENTITY_LOCAL_CACHE[id_block.name] = current_spatial_state
                        op = generate_transform_op(id_block)
                        
                        print(f"[COLLAB OUTBOUND] Transform update: {id_block.name} -> pos: {pos}")
                        
                        # Safely attempt to record local operation
                        if hasattr(operations_tracker, 'local_pipeline_tracker'):
                            operations_tracker.local_pipeline_tracker.record_local_operation(op)
                        config.OUTBOUND_QUEUE.put(op)
            
                elif id_block.type == 'MESH' and update.is_updated_geometry and not id_block.mode == 'EDIT':
                    op = generate_uv_topology_op(id_block)
                    config.OUTBOUND_QUEUE.put(op)

            # --- PATH B: SHADER NODE GRAPH MUTATIONS ---
            elif isinstance(id_block, bpy.types.Material):
                material = id_block
                if material.use_nodes and material.node_tree:
                    for obj in bpy.data.objects:
                        if material.name in obj.data.materials:
                            op = generate_node_mutation_op(
                                entity_id=obj.name,
                                target_type="SHADER_MATERIAL",
                                target_name=material.name,
                                action="VALUE_CHANGED",
                                details={"info": "Material node tree update detected"}
                            )
                            config.OUTBOUND_QUEUE.put(op)
                            break

            # --- PATH C: GEOMETRY NODE GRAPH MUTATIONS ---
            elif isinstance(id_block, bpy.types.NodeTree):
                nodetree = id_block
                if nodetree.type == 'GEOMETRY':
                    for obj in bpy.data.objects:
                        for mod in obj.modifiers:
                            if mod.type == 'NODES' and mod.node_group == nodetree:
                                op = generate_node_mutation_op(
                                    entity_id=obj.name,
                                    target_type="GEOMETRY_NODES",
                                    target_name=mod.name,
                                    action="VALUE_CHANGED",
                                    details={"node_graph_id": nodetree.name}
                                )
                                config.OUTBOUND_QUEUE.put(op)
                                break
                                
        if not is_throttled:
            config.LAST_FRAME_TIME = current_time

    except Exception as e:
        # MAGIC SHIELD: Prevents Blender from silently killing the handler
        print(f"\n[COLLAB FATAL ERROR] Depsgraph Handler Crashed: {e}")
        traceback.print_exc()

# ====================================================================
# SELF-HEALING REGISTRATION HOOKS
# ====================================================================
def register_handlers():
    print("regestring handler core handeler")
    if main_scene_dependency_evaluator in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(main_scene_dependency_evaluator)
    bpy.app.handlers.depsgraph_update_post.append(main_scene_dependency_evaluator)
    print("added the handeler")

def unregister_handlers():
    if main_scene_dependency_evaluator in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(main_scene_dependency_evaluator)