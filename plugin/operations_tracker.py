from . import config

class OperationsTracker:
    def __init__(self):
        self.undo_stack = []
        self.redo_stack = []

    def record_local_operation(self, op_dict):
        """Generates and stores the inverse algebraic operation for local modifications."""
        if op_dict["type"] != "ENTITY_TRANSFORM":
            return # Node graph logic handled separately
            
        payload = op_dict["payload"]
        entity_id = payload["entity_id"]
        
        # Calculate inverse based on previous cache point delta
        # If we shifted +5, the inverse is -5
        inverse_op = {
            "type": "ENTITY_TRANSFORM",
            "client_id": config.CLIENT_ID,
            "payload": {
                "entity_id": entity_id,
                "position": [-pos for pos in payload["position"]],
                "rotation": [-rot for rot in payload["rotation"]],
                "scale":    [1.0 / s if s != 0 else 1.0 for s in payload["scale"]]
            }
        }
        self.undo_stack.append(inverse_op)
        # Clear out redo chain on a fresh action path
        self.redo_stack.clear()

    def process_undo(self):
        """Pops the last action, swaps it, and feeds it into the network queue."""
        if not self.undo_stack:
            print("[Undo Engine] Stack empty.")
            return None
            
        inv_op = self.undo_stack.pop()
        # Move original to redo stack
        self.redo_stack.append(inv_op) 
        return inv_op

# Instantiate global state worker instance
local_pipeline_tracker = OperationsTracker()