import json
# In production, you will run: pip install msgpack inside Blender's python binary
try:
    import msgpack
    HAS_MSGPACK = True
except ImportError:
    HAS_MSGPACK = False

def pack_operation(op_dict):
    """Converts a live operational dictionary into binary wire formats."""
    if HAS_MSGPACK:
        return msgpack.packb(op_dict, use_bin_type=True)
    else:
        # Robust fallback tracking for local development debugging
        return json.dumps(op_dict).encode('utf-8')

def unpack_operation(binary_payload):
    """Decodes an incoming network byte stream back into Python structures."""
    if HAS_MSGPACK:
        return msgpack.unpackb(binary_payload, raw=False)
    else:
        return json.loads(binary_payload.decode('utf-8'))