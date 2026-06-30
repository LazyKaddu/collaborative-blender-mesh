import bpy
from . import network_client, config
from . import protocol_packer

def network_sync_tick():
    # 1. Drain the outbound queue (what the user changed)
    while not config.OUTBOUND_QUEUE.empty():
        op = config.OUTBOUND_QUEUE.get()
        # Add room context to operation
        op["room_id"] = config.ROOM_ID
        packed_op = protocol_packer.pack_operation(op)
        network_client.client.send_operation(packed_op)
        config.OUTBOUND_QUEUE.task_done()
    
    # 2. Trigger the inbound executor (what the server sent back)
    from .inbound_executor import execute_inbound_operations
    execute_inbound_operations()
    
    return 0.01 # Run every 0.01 seconds

def start_sync():
    bpy.app.timers.register(network_sync_tick)

def stop_sync():
    """Stops the network sync timer."""
    try:
        bpy.app.timers.unregister(network_sync_tick)
    except:
        pass