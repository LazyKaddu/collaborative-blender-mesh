import threading
import queue
import time
import traceback
from . import config
from . import protocol_packer

def mock_network_worker():
    print("[Network Thread] Background Consumer & Listener Online.")
    while config.IS_NETWORK_ALIVE:
        # 1. OUTBOUND HANDLING (What we send to server)
        try:
            operation = config.OUTBOUND_QUEUE.get_nowait()
            
            try:
                # Attempt to pack the operation into wire format
                binary_bytes = protocol_packer.pack_operation(operation)
                
                # Success Log: Visual confirmation that data is processing cleanly
                print(f"[Network Thread] Sent Outbound Op: {operation.get('type')} | Bytes: {len(binary_bytes)}")
                
                # In production: websocket.send(binary_bytes)
            except Exception as packing_err:
                # Catching the exact protocol conversion failure without killing the loop
                print(f"[Network Thread ERROR] Failed to pack operation layout: {packing_err}")
                traceback.print_exc()
            
            config.OUTBOUND_QUEUE.task_done()
            
        except queue.Empty:
            pass

        # 2. INBOUND HANDLING MOCK
        # (Left open for Phase 2 implementation)
        
        time.sleep(0.01) # Yield execution execution to save CPU cycles
        
    print("[Network Thread] Background Consumer & Listener Offline.")

def start_network_thread():
    config.IS_NETWORK_ALIVE = True
    net_thread = threading.Thread(target=mock_network_worker, daemon=True)
    net_thread.start()

def stop_network_thread():
    config.IS_NETWORK_ALIVE = False