import bpy

def apply_remote_lock(entity_id, owner_name):
    """Isolates and locks a mesh block using safe metadata attributes instead of renaming."""
    # Look for the true, unmodified entity name
    if entity_id in bpy.data.objects:
        obj = bpy.data.objects[entity_id]
        
        # 1. Store custom attribute metadata markers (This stays safe)
        obj["is_locked"] = True
        obj["lock_owner"] = owner_name
        
        # 2. Block the local user from clicking or grabbing it in the viewport
        obj.hide_select = True
        
        # 3. Viewport Override: Turn it vibrant red so the user visually knows it's locked
        obj.color = (0.85, 0.02, 0.02, 1.0) 
        obj.display_type = 'SOLID'
        
        # 4. Blender 5.1+ Safe UI Status Bar Notice
        # Instead of breaking the name property, we push a message to the status bar
        print(f"[UI Guard] Applied remote lockdown to asset: {entity_id} (Owned by {owner_name})")

def lift_remote_lock(entity_id):
    """Restores pristine selection flags and defaults color overrides on network release."""
    if entity_id in bpy.data.objects:
        obj = bpy.data.objects[entity_id]
        
        # Clean custom variables safely
        obj["is_locked"] = False
        obj["lock_owner"] = ""
        obj.hide_select = False
        
        # Clear viewport display color modifications back to standard gray
        obj.color = (1.0, 1.0, 1.0, 1.0)
        
        print(f"[UI Guard] Released lock restrictions on asset: {entity_id}")