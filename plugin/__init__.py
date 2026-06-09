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
    
    # ─── FORCE BLENDER TO FLUSH ITS INTERNAL MEMORY CACHE ───
    # This destroys Python's ghost references so it re-reads your live desktop files
    
    print("regestering")
    modules_to_flush = [
        "multiuser_collab.config",
        "multiuser_collab.core_handlers",
        "multiuser_collab.thread_worker",
        "multiuser_collab.inbound_executor",
        "multiuser_collab.protocol_packer",
        "multiuser_collab.operations_tracker",
        "multiuser_collab.lock_visualization"
    ]
    # for mod in modules_to_flush:
    #     if mod in sys.modules:
    #         print("flushed module",mod)
    #         del sys.modules[mod]

    # Now we can safely import the fresh files from disk
    from . import config

    from . import thread_worker
    from . import inbound_executor
    from . import ui_panel
    
    def delayed_register():
            from . import core_handlers
            core_handlers.register_handlers()
            return None
    bpy.app.timers.register(delayed_register,first_interval=0.1)
    

    ui_panel.register()
    # Initialize state sets
    config.TRACKED_OBJECTS = set()

    
   
    # Register the safe inbound execution timer loop
    bpy.app.timers.register(inbound_executor.execute_inbound_operations)

    
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