import bpy
import os
import time
from . import config

def export_draco_snapshot():
    """Exports the entire active scene into a temporary, compressed GLB file."""
    timestamp = int(time.time())
    filename = f"scene_{timestamp}.glb"
    filepath = os.path.join(bpy.app.tempdir, filename)
    
    # 🚀 Step 1: Strict runtime evaluation to see which operator is ACTUALLY available
    use_modern_op = False
    props_keys = []

    # Check if the modern Window Manager operator is truly registered and executable
    if hasattr(bpy.ops.wm, "gltf_export"):
        try:
            # If this succeeds, the operator is fully loaded in the runtime memory space
            props_keys = bpy.ops.wm.gltf_export.get_rna_type().properties.keys()
            use_modern_op = True
        except Exception:
            pass # It's a ghost attribute; fallback below

    # If modern op isn't alive, fallback to validating the legacy structural block
    if not use_modern_op:
        if hasattr(bpy.ops.export_scene, "gltf"):
            try:
                props_keys = bpy.ops.export_scene.gltf.get_rna_type().properties.keys()
            except Exception:
                props_keys = []

    # 🚀 Step 2: Determine compression support
    enable_draco = "export_draco_mesh_compression_enable" in props_keys

    if enable_draco:
        print("[COLLAB] Exporting baseline using Draco mesh compression...")
        if use_modern_op:
            bpy.ops.wm.gltf_export(
                filepath=filepath,
                export_format='GLB',
                export_draco_mesh_compression_enable=True,
                export_draco_mesh_compression_level=6,
                export_lights=True,
                export_cameras=True,
                export_apply=True,
                export_extras=True,
            )
        else:
            bpy.ops.export_scene.gltf(
                filepath=filepath,
                export_format='GLB',
                export_draco_mesh_compression_enable=True,
                export_draco_mesh_compression_level=6,
                export_lights=True,
                export_cameras=True,
                export_apply=True,
                export_extras=True,
            )
    else:
        print("[COLLAB WARNING] Draco compression missing or exporter uninitialized. Exporting uncompressed...")
        if use_modern_op:
            bpy.ops.wm.gltf_export(
                filepath=filepath,
                export_format='GLB',
                export_lights=True,
                export_cameras=True,
                export_apply=True,
                export_extras=True,
            )
        elif hasattr(bpy.ops.export_scene, "gltf"):
            bpy.ops.export_scene.gltf(
                filepath=filepath,
                export_format='GLB',
                export_lights=True,
                export_cameras=True,
                export_apply=True,
                export_extras=True,
            )
        else:
            raise RuntimeError("[COLLAB CRITICAL] No valid glTF/GLB export operators found in Blender system context. Verify glTF addon is enabled.")
            
    return filepath, filename


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


def import_draco_snapshot(filepath):
    """Loads the downloaded baseline snapshot into the empty viewport."""
    if os.path.exists(filepath):
        # Handle modern vs legacy runtime operations
        if hasattr(bpy.ops.wm, "gltf_import"):
            bpy.ops.wm.gltf_import(filepath=filepath)
        else:
            bpy.ops.import_scene.gltf(filepath=filepath)
            
        print("[COLLAB SCENE] Baseline snapshot successfully loaded.")
        return True
    return False


# ====================================================================
# 2. LOCAL SYNC PRIMING PIPELINE (Used by ui_panel.py)
# ====================================================================

def prime_local_collaboration_cache():
    """
    Seeds the local entity cache with baseline positions and UV layouts 
    the exact moment a room session starts.
    """
    print("[COLLAB] Priming local entity state and topology caches...")
    
    # Reset existing caches to prevent bleed from previous sessions
    config.ENTITY_LOCAL_CACHE.clear()
    
    # Deferred dynamic import to prevent cyclical initialization references inside core_handlers
    from .core_handlers import COLLAB_OBJECT_TYPES, capture_object_state
    
    for obj in bpy.context.scene.objects:
        if obj.type not in COLLAB_OBJECT_TYPES:
            continue
            
        # Cache initial spatial transform vectors
        config.ENTITY_LOCAL_CACHE[obj.name] = capture_object_state(obj)
        
        # Cache initial UV layout snapshot spaces
        if obj.type == 'MESH' and obj.data.uv_layers.active:
            uv_layer = obj.data.uv_layers.active
            config.ENTITY_LOCAL_CACHE[f"{obj.name}_uv"] = [
                coord 
                for loop in obj.data.loops 
                for coord in [uv_layer.data[loop.index].uv.x, uv_layer.data[loop.index].uv.y]
            ]
            
    # Sync structural tracker tracking sets
    config.TRACKED_OBJECTS = set(obj.name for obj in bpy.context.scene.objects if obj.type in COLLAB_OBJECT_TYPES)
    print(f"[COLLAB] Cache successfully seeded with {len(config.TRACKED_OBJECTS)} tracked objects.")