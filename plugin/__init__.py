bl_info = {
    "name": "Multiuser Collaboration Engine",
    "author": "Aashish Negi",
    "version": (1, 0),
    "blender": (5, 1, 0),
    "location": "View3D > Sidebar",
    "description": "Real-time operations-based sync engine",
    "category": "Development",
}

import bpy
import sys


def register():
    """Dynamically import and activate modules at execution time."""
    
    print("Registering Multiuser Collaboration Engine...")
    
    # Import configuration first
    from . import config
    from . import ui_panel
    from . import core_handlers
    from . import inbound_executor
    from . import thread_worker
    
    # Register PropertyGroup for UI
    bpy.utils.register_class(ui_panel.MultiuserCollabProperties)
    
    # Register UI Panel
    bpy.utils.register_class(ui_panel.MULTIUSER_PT_collaboration_panel)
    
    # Register Operators
    bpy.utils.register_class(ui_panel.MULTIUSER_OT_create_room)
    bpy.utils.register_class(ui_panel.MULTIUSER_OT_join_room)
    bpy.utils.register_class(ui_panel.MULTIUSER_OT_disconnect_session)
    bpy.utils.register_class(ui_panel.MULTIUSER_OT_flush_update)
    
    # Register scene properties
    bpy.types.Scene.multiuser_collab_props = bpy.props.PointerProperty(
        type=ui_panel.MultiuserCollabProperties
    )
    
    def delayed_register():
        core_handlers.register_handlers()
        return None
    
    bpy.app.timers.register(delayed_register, first_interval=0.1)
    print("Multiuser Collaboration Engine registered successfully!")


def unregister():
    """Clean up and deregister all classes and handlers."""
    from . import ui_panel
    from . import core_handlers
    
    print("Unregistering Multiuser Collaboration Engine...")
    
    # Unregister handlers
    core_handlers.unregister_handlers()
    
    # Unregister operators
    bpy.utils.unregister_class(ui_panel.MULTIUSER_OT_flush_update)
    bpy.utils.unregister_class(ui_panel.MULTIUSER_OT_disconnect_session)
    bpy.utils.unregister_class(ui_panel.MULTIUSER_OT_join_room)
    bpy.utils.unregister_class(ui_panel.MULTIUSER_OT_create_room)
    
    # Unregister UI Panel
    bpy.utils.unregister_class(ui_panel.MULTIUSER_PT_collaboration_panel)
    
    # Unregister PropertyGroup
    bpy.utils.unregister_class(ui_panel.MultiuserCollabProperties)
    
    # Remove scene property
    if hasattr(bpy.types.Scene, "multiuser_collab_props"):
        del bpy.types.Scene.multiuser_collab_props
    
    print("Multiuser Collaboration Engine unregistered successfully!")

    
    # Kick off the background worker threads
    thread_worker.start_network_thread()

    
    print("[Collab Engine] Two-Way Async Architecture Operational.")

def unregister():
    """Safely tear down all hooks and worker threads."""
    from . import thread_worker
    from . import inbound_executor
    from . import ui_panel
    print("unregestering handlers", len(bpy.app.handlers.depsgraph_update_post))
    bpy.app.handlers.depsgraph_update_post.clear()
    
    # Unregister the execution loop timer cleanly
    if bpy.app.timers.is_registered(inbound_executor.execute_inbound_operations):
        bpy.app.timers.unregister(inbound_executor.execute_inbound_operations)
        
    thread_worker.stop_network_thread()
    ui_panel.unregister()
    print("[Collab Engine] Addon cleanly unregistered.")
    
if __name__ == "__main__":
    register()