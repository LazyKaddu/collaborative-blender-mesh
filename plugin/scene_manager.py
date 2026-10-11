import os
import time
from . import config
from . import protocol_packer
import bpy
import bmesh
import base64

def serialize_node_tree(node_tree):
    """Deep serializes an entire node tree's layout, properties, and links into JSON-safe dictionaries."""
    if not node_tree:
        return None
        
    nodes_data = []
    links_data = []
    
    # 1. Capture all node instances and their specific internal properties
    for node in node_tree.nodes:
        node_props = {}
        if hasattr(node, "bl_rna"):
            for prop in node.bl_rna.properties:
                if not prop.is_readonly and prop.identifier not in {'name', 'location', 'hide', 'select'}:
                    try:
                        node_props[prop.identifier] = getattr(node, prop.identifier)
                    except:
                        pass # Skip non-serializable complex data blocks like internal pointers
                        
        nodes_data.append({
            "name": node.name,
            "bl_idname": node.bl_idname,
            "loc_x": round(node.location.x, 2),
            "loc_y": round(node.location.y, 2),
            "properties": node_props
        })
        
    # 2. Capture all topological socket connections
    for link in node_tree.links:
        links_data.append({
            "from_node": link.from_node.name,
            "to_node": link.to_node.name,
            "from_output": link.from_socket.name,
            "to_input": link.to_socket.name,
            "from_output_idx": list(link.from_node.outputs).index(link.from_socket),
            "to_input_idx": list(link.to_node.inputs).index(link.to_socket)
        })
        
    return {"nodes": nodes_data, "links": links_data}


def generate_batch_unlock_op(obj):
    """Generates a single comprehensive payload tracking all graph states right as it is being unlocked."""
    from . import config
    import time
    
    payload = {
        "entity_id": obj.name,
        "action": "RELEASE_AND_SYNC",
        "material_graph": None,
        "geometry_graph": None,
        "material_name": "",
        "geometry_modifier_name": ""
    }
    
    # Extract Active Shader Material Graph
    if obj.data and hasattr(obj.data, "materials") and len(obj.data.materials) > 0:
        active_mat = obj.data.materials[0]
        if active_mat and active_mat.use_nodes:
            payload["material_name"] = active_mat.name
            payload["material_graph"] = serialize_node_tree(active_mat.node_tree)
            
    # Extract Active Geometry Nodes Modifier Graph
    for mod in obj.modifiers:
        if mod.type == 'NODES' and mod.node_group:
            payload["geometry_modifier_name"] = mod.name
            payload["geometry_graph"] = serialize_node_tree(mod.node_group)
            break 
            
    return {
        "type": "LOCK_BATCH_SYNC",
        "op_id": int(time.time_ns()),
        "client_id": config.CLIENT_ID,
        "payload": payload
    }



def generate_scene_mesh_data():
    scene = bpy.context.scene

    mesh_data = []
    for obj in scene.objects:
        if obj.type == "MESH":
            packed_op = base64.b64encode(protocol_packer.pack_operation(generate_edit_sync_pack(obj))).decode("utf-8")
            mesh_data.append(packed_op)

    return mesh_data


def generate_edit_sync_pack(obj):
    try:
        mesh_data = obj.data
        bm = bmesh.new()
        bm.from_mesh(mesh_data)
        bm.verts.ensure_lookup_table()
        bm.faces.ensure_lookup_table()

        vertex_coords = [list(v.co) for v in bm.verts]
        face_indices = [[v.index for v in f.verts] for f in bm.faces]

        bm.free()

        geom_payload = {
            "v": vertex_coords,
            "f": face_indices
        }

        raw_geom_bytes = protocol_packer.pack_operation(geom_payload)

        compressed_geom_bytes = protocol_packer.compress_data(raw_geom_bytes)

        commit_packet = {
            "type": "BMESH_COMMIT_SYNC",
            "target": obj.name,
            "op_id": int(time.time_ns()),
            "client_id": config.CLIENT_ID,
            "target_name": obj.name, # Matches the 'target_name' key used on the receiver side
            "compressed_geom": compressed_geom_bytes # Native binary payload type
        }


        print(f"📦 [COLLAB COMMIT] Encoded & Compressed '{obj.name}' topology.")
        print(f"   ↳ Raw Verts: {len(vertex_coords)} | Raw Faces: {len(face_indices)}")
        print(f"   ↳ Compressed Geometry Size: {len(compressed_geom_bytes)} bytes")

        return commit_packet

    except Exception as bmesh_err:
        print(f"❌ [COLLAB COMMIT ERROR] Failed to package compressed mesh snapshot: {bmesh_err}")


def clear_entire_scene():
    """Aggressively purges everything to prevent ID conflicts upon room entry."""
    # Context check to handle background invocation safety
    if bpy.context.object and bpy.context.object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')

    # Deselect all, then select all objects and delete safely
    bpy.ops.object.select_all(action='DESELECT')
    for obj in bpy.context.scene.objects:
        obj.select_set(True)
    bpy.ops.object.delete(use_global=False)
    
    # 🚀 Fix: Deep clean using sliced backward notation lists to prevent loop index dropping
    for block in list(bpy.data.meshes): bpy.data.meshes.remove(block)
    for block in list(bpy.data.materials): bpy.data.materials.remove(block)
    for block in list(bpy.data.cameras): bpy.data.cameras.remove(block)
    for block in list(bpy.data.lights): bpy.data.lights.remove(block)
    for block in list(bpy.data.armatures): bpy.data.armatures.remove(block)
    print("[COLLAB SCENE] Aggressive viewport purging complete.")




def export_glb_snapshot():
    """
    Exports a binary glTF (.glb) scene snapshot using exact official API properties.
    Preserves raw quad topology and embeds all external images/textures.
    """
    timestamp = int(time.time())
    filename = f"scene_{timestamp}.glb"
    filepath = os.path.join(bpy.app.tempdir, filename)

    try:
       
        bpy.ops.export_scene.gltf(
            filepath=filepath,
            export_format='GLB',                
            
            # CRITICAL: Prevents auto-triangulation by not applying modifiers destructively
            export_apply=False,           
            
            # Match the exact property keywords from your specific build signature
            export_vertex_color='MATERIAL',      # Updated key for managing custom mesh color channels
            export_materials='EXPORT',          # Process and bundle active shader graphs
            export_extras=True,                  # Retain custom property metadata blocks (like tracking UUIDs)
            export_cameras=True,                 # Include active camera points
            export_lights=True,                  # Include scene lighting rigs
            export_animations=True,              # Correct pluralized attribute key for handling sequence state paths
            
            use_selection=False,                 # Track and export the entire outliner scene tree
            filter_glob='*.glb'                  # Standard fallback execution string
        )
        
        print(f"[COLLAB SCENE] GLB snapshot successfully generated via exact API rules: {filename}")
        return filepath, filename

    except Exception as e:
        print(f"[COLLAB SCENE ERROR] GLB export execution failed against API signatures: {e}")
        return None, None


def import_glb_snapshot(filepath):
    """
    Loads a downloaded GLB snapshot non-destructively into Blender.
    Defends against startup/UI race conditions using dynamic window overrides.
    """
    print("filepath:", filepath)

    if not os.path.exists(filepath):
        print(f"[COLLAB SCENE ERROR] Snapshot file not found: {filepath}")
        return False

    # Wait until Blender UI is fully available to avoid core API context crashes
    if not bpy.context.window or not bpy.context.screen:
        print("[COLLAB SCENE] UI not ready. Deferring import...")
        bpy.app.timers.register(
            lambda: import_glb_snapshot(filepath),
            first_interval=0.1
        )
        return True

    try:
        win = bpy.context.window
        scr = win.screen
        areas = [a for a in scr.areas if a.type == 'VIEW_3D']

        if not areas:
            bpy.app.timers.register(
                lambda: import_glb_snapshot(filepath),
                first_interval=0.1
            )
            return True

        area = areas[0]
        region = next(
            (r for r in area.regions if r.type == 'WINDOW'),
            None
        )

        override_ctx = {
            "window": win,
            "screen": scr,
            "area": area,
            "region": region,
            "scene": bpy.context.scene,
        }

        # Safe context override loop execution
        with bpy.context.temp_override(**override_ctx):
            bpy.ops.import_scene.gltf(
                filepath=filepath,
                import_pack_images=True,  # Unpacks embedded textures automatically into local memory
                merge_vertices=True
            )

        print("[COLLAB SCENE] GLB snapshot successfully integrated into active viewport.")

        # Cleanup the downloaded temporary cache file
        try:
            os.remove(filepath)
            print("[COLLAB SCENE] Temporary snapshot disk storage cleared.")
        except Exception as e:
            print(f"[COLLAB SCENE] Failed to remove temp file: {e}")

        return True

    except Exception as e:
        print(f"[COLLAB SCENE ERROR] GLB import processing pipeline failed: {e}")
        return False
# ====================================================================
# 2. LOCAL SYNC PRIMING PIPELINE (Used by ui_panel.py)
# ====================================================================

def prime_local_collaboration_cache():
    """
    Seeds the local entity tracker and spatial baseline caches 
    the exact moment a room session starts.
    """
    import bpy
    from . import config

    print("[COLLAB] Priming local entity state tracking baselines...")
    
    # 🧼 Reset existing caches to prevent data bleeding from previous room sessions
    config.ENTITY_LOCAL_CACHE.clear()
    config.TRACKED_OBJECTS.clear()
    config.SELECTED_OBJECTS_CACHE.clear()
    config.LOCAL_LOCKS.clear()

    # Allowed categories for collaborative sync
    COLLAB_OBJECT_TYPES = {'MESH', 'CURVE', 'SURFACE', 'META', 'FONT', 'LIGHT', 'CAMERA'}
    
    for obj in bpy.context.scene.objects:
        if obj.type not in COLLAB_OBJECT_TYPES:
            continue
            
        #Fix: Cache spatial transform vectors using native, lightning-fast tuples
        config.ENTITY_LOCAL_CACHE[obj.name] = {
            "position": tuple(obj.location),
            "rotation": tuple(obj.rotation_euler),
            "scale":    tuple(obj.scale)
        }
        
        # Track its existence 
        config.TRACKED_OBJECTS.add(obj.name)
        
        # If the local user already has this object highlighted upon joining, lock it locally
        if obj.select_get():
            config.SELECTED_OBJECTS_CACHE.add(obj.name)
            config.LOCAL_LOCKS.add(obj.name)
            
    print(f"[COLLAB] Baseline cache successfully seeded with {len(config.TRACKED_OBJECTS)} active objects.")