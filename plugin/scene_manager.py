import bpy
import os
import time

def export_draco_snapshot():
    """Exports the entire active scene into a temporary, compressed GLB file."""
    timestamp = int(time.time())
    filename = f"scene_{timestamp}.glb"
    filepath = os.path.join(bpy.app.tempdir, filename)
    
    # Run Blender's native glTF exporter
    if "export_draco_mesh_compression_enable" in bpy.ops.export_scene.gltf.get_rna_type().properties.keys():
        print("exporting using darco compression")
        bpy.ops.export_scene.gltf(
            filepath=filepath,
            export_format='GLB',
            # Enable Draco compression
            export_draco_mesh_compression_enable=True,
            # Set compression level (0 = fast/large, 10 = slow/small)
            export_draco_mesh_compression_level=6,
            export_lights=True,   # Exports Point, Sun, Spot, and Area lights
            export_cameras=True,
            export_apply=True,
            export_extras=True,
        )
    else:
        print("exporting without compression")
        bpy.ops.export_scene.gltf(
            filepath=filepath,
            export_format='GLB',
            export_lights=True,   # Exports Point, Sun, Spot, and Area lights
            export_cameras=True,
            export_apply=True,
            export_extras=True,
        )
            
    return filepath, filename

def clear_entire_scene():
    """Aggressively purges everything to prevent ID conflicts upon room entry."""
    # Deselect all, then select all objects and delete
    bpy.ops.object.select_all(action='DESELECT')
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    
    # Deep clean unused data blocks/orphans from memory
    for block in bpy.data.meshes: bpy.data.meshes.remove(block)
    for block in bpy.data.materials: bpy.data.materials.remove(block)
    for block in bpy.data.cameras: bpy.data.cameras.remove(block)
    for block in bpy.data.lights: bpy.data.lights.remove(block)
    for block in bpy.data.armatures: bpy.data.armatures.remove(block)

def import_draco_snapshot(filepath):
    """Loads the downloaded baseline snapshot into the empty viewport."""
    if os.path.exists(filepath):
        bpy.ops.import_scene.gltf(filepath=filepath)
        print("[COLLAB SCENE] Baseline snapshot successfully loaded.")
        return True
    return False