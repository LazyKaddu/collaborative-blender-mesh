import bpy
import bmesh
import queue
from . import config
from . import lock_visualization

# ====================================================================
# 1. ADVANCED DATA-BLOCK FACTORY HELPERS
# ====================================================================

def spawn_remote_primitive(entity_id, obj_type):
    """Factory helper to instantly inject a missing object container into Blender."""
    try:
        print(f"[COLLAB INBOUND] Spawning missing remote entity: {entity_id} of type {obj_type}")
        
        if obj_type == 'MESH':
            mesh_data = bpy.data.meshes.new(name=entity_id)
            new_obj = bpy.data.objects.new(entity_id, mesh_data)
        elif obj_type == 'CAMERA':
            cam_data = bpy.data.cameras.new(name=entity_id)
            new_obj = bpy.data.objects.new(entity_id, cam_data)
        elif obj_type == 'LIGHT':
            light_data = bpy.data.lights.new(name=entity_id, type='POINT')
            new_obj = bpy.data.objects.new(entity_id, light_data)
        elif obj_type == 'CURVE':
            curve_data = bpy.data.curves.new(name=entity_id, type='CURVE')
            curve_data.dimensions = '3D'
            new_obj = bpy.data.objects.new(entity_id, curve_data)
        elif obj_type == 'FONT':
            text_data = bpy.data.curves.new(name=entity_id, type='FONT')
            new_obj = bpy.data.objects.new(entity_id, text_data)
        else:
            new_obj = bpy.data.objects.new(entity_id, None)

        new_obj.name = entity_id
        bpy.context.scene.collection.objects.link(new_obj)
        config.TRACKED_OBJECTS.add(entity_id)
        
        # 🚀 Fix: Prime empty structural UV vector slot for newly spawned remote meshes
        if obj_type == 'MESH':
            config.ENTITY_LOCAL_CACHE[f"{entity_id}_uv"] = []
            
        return new_obj
    except Exception as e:
        print(f"[COLLAB ERROR] Failed to factory spawn entity {entity_id}: {str(e)}")
        return None


def apply_uv_data(obj, uv_payload):
    """Reconstructs and applies complex UV layer coordinate unwrap data maps."""
    if obj.type != 'MESH' or not uv_payload:
        return

    mesh = obj.data
    uv_layer_name = uv_payload.get("layer_name", "UVMap")
    uv_loops_data = uv_payload.get("loops", [])  # Flattened array of [u, v, u, v...]

    # Ensure UV map channel exists
    uv_layer = mesh.uv_layers.get(uv_layer_name) or mesh.uv_layers.new(name=uv_layer_name)

    # Safe block assignment to avoid index mismatches if topologies mismatch midway
    if len(uv_loops_data) // 2 == len(mesh.loops):
        idx = 0
        for loop in mesh.loops:
            uv_layer.data[loop.index].uv = (uv_loops_data[idx], uv_loops_data[idx+1])
            idx += 2
        print(f"[COLLAB INBOUND] UV Map '{uv_layer_name}' synchronized for {obj.name}")
        
        # 🚀 Fix: Update local tracking cache to match the fresh inbound vector space state
        config.ENTITY_LOCAL_CACHE[f"{obj.name}_uv"] = uv_loops_data


def apply_topology_data(obj, topology_payload):
    """Applies raw geometry changes (vertices/faces) to the object's mesh."""
    if obj.type != 'MESH':
        return

    # Create a BMesh from the current mesh to perform edits
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    
    # 1. Clear existing geometry to rebuild from payload
    bm.faces.ensure_lookup_table()
    for face in bm.faces:
        bmesh.ops.delete(bm, geom=[face], context='FACES')

    # 2. Reconstruct from your payload
    vertices = topology_payload.get("verts", [])
    faces = topology_payload.get("faces", [])
    
    # [Your custom BMesh deserialization implementation handles verts/faces loading here...]

    # 3. Finalize
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    print(f"[COLLAB INBOUND] Topology synchronized for {obj.name}")
    
    # 🚀 Fix: Instantly refresh the coordinate tracking parameters so our local handlers don't flag an echo change
    from .core_handlers import capture_object_state
    config.ENTITY_LOCAL_CACHE[obj.name] = capture_object_state(obj)
    
    if obj.data.uv_layers.active:
        uv_layer = obj.data.uv_layers.active
        config.ENTITY_LOCAL_CACHE[f"{obj.name}_uv"] = [
            coord 
            for loop in obj.data.loops 
            for coord in [uv_layer.data[loop.index].uv.x, uv_layer.data[loop.index].uv.y]
        ]


def sync_node_tree(node_tree, nodes_payload):
    """Generic high-fidelity engine to synchronize a node group topology layout."""
    if not node_tree or not nodes_payload:
        return
        
    node_tree.nodes.clear()
    node_map = {}
    
    # Step 1: Re-spawn nodes with exact internal bl_idnames
    for n_data in nodes_payload.get("nodes", []):
        try:
            node = node_tree.nodes.new(type=n_data["bl_idname"])
            node.name = n_data["name"]
            node.location = (n_data["loc_x"], n_data["loc_y"])
            node_map[node.name] = node
            
            # Re-apply literal scalar property mutations if present
            for prop_name, prop_val in n_data.get("properties", {}).items():
                if hasattr(node, prop_name):
                    setattr(node, prop_name, prop_val)
        except Exception as e:
            print(f"[COLLAB NODE ERROR] Couldn't instantiate node {n_data.get('bl_idname')}: {e}")

    # Step 2: Re-weave connection links safely
    for link_data in nodes_payload.get("links", []):
        try:
            from_node = node_map.get(link_data["from_node"])
            to_node = node_map.get(link_data["to_node"])
            
            if from_node and to_node:
                # Find matching structural sockets safely
                output_socket = from_node.outputs.get(link_data["from_output"]) or from_node.outputs[int(link_data["from_output_idx"])]
                input_socket = to_node.inputs.get(link_data["to_input"]) or to_node.inputs[int(link_data["to_input_idx"])]
                
                node_tree.links.new(output_socket, input_socket)
        except Exception as e:
            print(f"[COLLAB LINK ERROR] Failed re-linking sockets: {e}")

# ====================================================================
# 2. CORE INBOUND EXECUTION PIPELINE
# ====================================================================

def execute_inbound_operations():
    """Pops operations from the inbound network queue and applies them to the Blender database."""
    for _ in range(30):
        try:
            op = config.INBOUND_QUEUE.get_nowait()
            config.IS_PROCESSING_REMOTE_OP = True
            op_type = op.get("type")
            client_id = op.get("client_id")
            payload = op.get("payload", {})
            
            if client_id == config.CLIENT_ID:
                config.INBOUND_QUEUE.task_done()
                continue
                
            entity_id = payload.get("entity_id")
            if not entity_id:
                config.INBOUND_QUEUE.task_done()
                continue
            
            # --- HANDLE REMOTE TRANSFORMS & STRUCTURAL SYNC ---
            if op_type == "ENTITY_TRANSFORM":
                if entity_id not in bpy.data.objects:
                    obj = spawn_remote_primitive(entity_id, payload.get("object_type", "MESH"))
                else:
                    obj = bpy.data.objects[entity_id]

                if obj:
                    pos, rot, scl = tuple(payload["position"]), tuple(payload["rotation"]), tuple(payload["scale"])
                    config.ENTITY_LOCAL_CACHE[entity_id] = (pos, rot, scl)
                    
                    obj.location = payload["position"]
                    obj.rotation_euler = payload["rotation"]
                    obj.scale = payload["scale"]
                        
                    bpy.context.view_layer.update()

            # --- HANDLE SHADER/MATERIAL NODES MUTATIONS ---
            elif op_type == "NODE_MUTATION" and payload.get("target_type") == "SHADER_MATERIAL":
                if entity_id in bpy.data.objects:
                    obj = bpy.data.objects[entity_id]
                    mat_name = payload.get("target_name")
                    
                    mat = bpy.data.materials.get(mat_name) or bpy.data.materials.new(name=mat_name)
                    mat.use_nodes = True
                    
                    sync_node_tree(mat.node_tree, payload.get("node_graph"))
                    
                    if mat.name not in obj.data.materials:
                        if len(obj.data.materials) == 0:
                            obj.data.materials.append(mat)
                        else:
                            obj.data.materials[0] = mat

            elif op_type == "MESH_TOPOLOGY_MUTATION":
                if entity_id in bpy.data.objects:
                    obj = bpy.data.objects[entity_id]
                    if obj.type == 'MESH':
                        mutation = payload.get("mutation_type")
                
                        if mutation == "UV_MAP_EDITED":
                            apply_uv_data(obj, payload)
                        elif mutation == "GEOMETRY_EDITED":
                            apply_topology_data(obj, payload)

            # --- HANDLE GEOMETRY NODES OPERATIONS ---
            elif op_type == "NODE_MUTATION" and payload.get("target_type") == "GEOMETRY_NODES":
                if entity_id in bpy.data.objects:
                    obj = bpy.data.objects[entity_id]
                    mod_name = payload.get("target_name", "GeometryNodes")
                    
                    mod = obj.modifiers.get(mod_name) or obj.modifiers.new(name=mod_name, type='NODES')
                    
                    if mod.node_group is None:
                        group = bpy.data.node_groups.new(name=f"GN_{entity_id}", type='GeometryNodeTree')
                        mod.node_group = group
                        
                    sync_node_tree(mod.node_group, payload.get("node_graph"))

            # --- HANDLE REMOTE DELETIONS ---
            elif op_type == "DELETE":
                if entity_id in bpy.data.objects:
                    obj = bpy.data.objects[entity_id]
                    data_ref = obj.data
                    bpy.data.objects.remove(obj, do_unlink=True)
                    
                    if data_ref and data_ref.users == 0:
                        if entity_id in bpy.data.meshes: bpy.data.meshes.remove(data_ref)
                        elif entity_id in bpy.data.curves: bpy.data.curves.remove(data_ref)

                    config.TRACKED_OBJECTS.discard(entity_id)
                    if entity_id in config.ENTITY_LOCAL_CACHE:
                        del config.ENTITY_LOCAL_CACHE[entity_id]
                    if f"{entity_id}_uv" in config.ENTITY_LOCAL_CACHE:
                        del config.ENTITY_LOCAL_CACHE[f"{entity_id}_uv"]

            # --- HANDLE LOCK TRANSACTION SIGNALS ---
            elif op_type == "LOCK_TRANSACTION":
                action = payload.get("action")
                owner_name = op.get("client_name", "Remote User")
                if action == "ACQUIRE_EXCLUSIVE":
                    lock_visualization.apply_remote_lock(entity_id, owner_name)
                elif action == "RELEASE":
                    lock_visualization.lift_remote_lock(entity_id)

            config.INBOUND_QUEUE.task_done()
            
        except queue.Empty:
            break
        finally:
            config.IS_PROCESSING_REMOTE_OP = False

    return 0.01