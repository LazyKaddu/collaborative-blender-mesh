import bpy
import queue
import time
from . import config
from . import lock_visualization
from . import protocol_packer

# ====================================================================
# 1. ADVANCED DATA-BLOCK FACTORY HELPERS
# ====================================================================

def spawn_remote_primitive(entity_id, obj_type):
    """Factory helper to instantly inject a missing object container into Blender."""
    try:
        print(f"[COLLAB INBOUND] Spawning missing remote entity: {entity_id} of type {obj_type}")
        
        if obj_type == 'MESH':
            mesh_data = bpy.data.meshes.new(name=entity_id)
            new_obj = bpy.data.objects.new(entity_id, mesh_data)
        elif obj_type == 'CAMERA':
            cam_data = bpy.data.cameras.new(name=entity_id)
            new_obj = bpy.data.objects.new(entity_id, cam_data)
        elif obj_type == 'LIGHT':
            light_data = bpy.data.lights.new(name=entity_id, type='POINT')
            new_obj = bpy.data.objects.new(entity_id, light_data)
        elif obj_type == 'CURVE':
            curve_data = bpy.data.curves.new(name=entity_id, type='CURVE')
            curve_data.dimensions = '3D'
            new_obj = bpy.data.objects.new(entity_id, curve_data)
        elif obj_type == 'FONT':
            text_data = bpy.data.curves.new(name=entity_id, type='FONT')
            new_obj = bpy.data.objects.new(entity_id, text_data)
        else:
            new_obj = bpy.data.objects.new(entity_id, None)

        new_obj.name = entity_id
        bpy.context.scene.collection.objects.link(new_obj)
        
        return new_obj
    except Exception as e:
        print(f"[COLLAB ERROR] Failed to factory spawn entity {entity_id}: {str(e)}")
        return None

# ====================================================================
# 2. UNIFIED DISCRETE COMMAND EXECUTOR ENGINE
# ====================================================================

def execute_inbound_operations():
    """
    Pops discrete operations from the inbound network queue and injects them 
    safely using the Context Matrix with a strict 3ms frame budget limit.
    """
    start_time = time.perf_counter()
    FRAME_BUDGET = 0.003  # 🚀 Hard 3ms allocation gate to prevent viewport stutters

    while not config.INBOUND_QUEUE.empty():
        print("inbound queue is not empty")
        # ⏱️ Budget Check: Yield immediately to keep local mouse inputs ultra-fluid
        if (time.perf_counter() - start_time) > FRAME_BUDGET:
            print("breaking because time.perf_counter() - start_time > FRAME_BUDGET", (time.perf_counter() - start_time) > FRAME_BUDGET)
            break

        try:
            op = config.INBOUND_QUEUE.get_nowait()
            client_id = op.get("client_id")
            
            # Discard mirrors of our own transmissions
            if client_id == config.CLIENT_ID:
                print("getting rid of echo operations")
                config.INBOUND_QUEUE.task_done()
                continue
            
            op_type = op.get("type")
            target_name = op.get("target")

            print(f"op_type -> {op_type}, target_name -> {target_name}")

            # ─── CORE ROUTE A: HIGH-SPEED NON-OPERATOR TRANSFORMS ───
            if op_type == "STATE_RESYNC" and target_name in bpy.data.objects:
                obj = bpy.data.objects[target_name]
                config.IS_PROCESSING_REMOTE_OP = True
                
                obj.location = op.get("location", obj.location)
                obj.rotation_euler = op.get("rotation", obj.rotation_euler)
                obj.scale = op.get("scale", obj.scale)
                
                bpy.context.view_layer.update()
                config.INBOUND_QUEUE.task_done()
                continue

            # ─── CORE ROUTE B: LOCK TRANSACTION HANDLERS ───
            if op_type == "LOCK_TRANSACTION":
                action = op.get("action")
                owner_name = op.get("client_name", "Remote User")
                if action == "ACQUIRE_EXCLUSIVE":
                    lock_visualization.apply_remote_lock(target_name, owner_name)
                elif action == "RELEASE":
                    lock_visualization.lift_remote_lock(target_name)
                
                config.INBOUND_QUEUE.task_done()
                continue

            # ─── CORE ROUTE C: UNIFIED COMMAND INJECTION EXECUTOR ───
            if op_type == "COMMAND_EXECUTION":
                op_string = op.get("operator")      # 'TRANSFORM_OT_translate'
                properties = op.get("properties", {})
                obj_type = op.get("object_type", "MESH")
                print(f"op_string -> {op_string}, properties -> {properties}, obj_type -> {obj_type}")
                
                target_name = op.get("target") 

                if not target_name:
                    print("⚠️ [INBOUND EXEC] Packet discarded: missing 'target' key allocation.")
                    config.INBOUND_QUEUE.task_done()
                    continue

                if target_name not in bpy.data.objects:
                    if op_string == "OBJECT_OT_delete":
                        config.INBOUND_QUEUE.task_done()
                        continue
                    obj = spawn_remote_primitive(target_name, obj_type)
                else:
                    obj = bpy.data.objects[target_name]

                if not obj:
                    config.INBOUND_QUEUE.task_done()
                    continue

                config.IS_PROCESSING_REMOTE_OP = True
                print("processing remote operations ")

                try:
                    # 🚀 FAST-PATH: If it's a transform digest, map spatial vector states directly
                    if op_string.startswith("TRANSFORM_OT_") and "transform_digest" in properties:
                        print(f"⚡ [INBOUND EXEC] Applying fast-path transform mapping on target: {target_name}")
                        tf = properties["transform_digest"]
                        print("FALLBACK DIGEST FOUND:", tf)

                        obj.location = tuple(tf.get("location", obj.location))
                        obj.rotation_euler = tuple(tf.get("rotation", obj.rotation_euler))
                        obj.scale = tuple(tf.get("scale", obj.scale))

                        obj.select_set(True) 
                        bpy.context.view_layer.update()
                        for area in bpy.context.screen.areas:
                            if area.type == 'VIEW_3D':
                                area.tag_redraw()

                    # 🚀 SLOW-PATH: Standard Event-Sourcing execution for discrete structural operations
                    else:
                        win = bpy.context.window_manager.windows[0]
                        scr = win.screen
                        areas = [a for a in scr.areas if a.type == 'VIEW_3D']
                        area = areas[0] if areas else None
                        region = [r for r in area.regions if r.type == 'WINDOW'][0] if area else None

                        override_ctx = {
                            "window": win,
                            "screen": scr,
                            "area": area,
                            "region": region,
                            "scene": bpy.context.scene,
                            "view_layer": bpy.context.view_layer,
                            "active_object": obj,
                            "selected_objects": [obj],
                            "selected_editable_objects": [obj]
                        }

                        parts = op_string.split("_OT_")
                        category = parts[0].lower()
                        op_name = parts[1]
                        operator_func = getattr(getattr(bpy.ops, category), op_name)

                        print(f"🎬 [INBOUND EXEC] Replicating operator '{op_string}' background targets: {target_name}")
                        with bpy.context.temp_override(**override_ctx):
                            operator_func('EXEC_DEFAULT', **properties)

                except Exception as inner_err:
                    print(f"❌ [INBOUND EXEC CRITICAL] Failed to execute remote operator {op_string}: {inner_err}")
                finally:
                    config.IS_PROCESSING_REMOTE_OP = False

                bpy.context.view_layer.update()
                config.INBOUND_QUEUE.task_done()
                continue

            # ─── 🚀 CORE ROUTE D: TRANSACTION GEOMETRY INJECTION (BMESH COMMIT) ───
            if op_type == "BMESH_COMMIT_SYNC":
                incoming_verts = op.get("vertices", [])
                
                if target_name in bpy.data.objects and incoming_verts:
                    remote_obj = bpy.data.objects[target_name]
                    
                    if remote_obj.type == 'MESH':
                        mesh_data = remote_obj.data
                        config.IS_PROCESSING_REMOTE_OP = True
                        
                        try:
                            # Verify structural topology sizes align before raw coordinate writing
                            if len(mesh_data.vertices) == len(incoming_verts):
                                print(f"⚡ [INBOUND COMMIT] Fast-aligned mesh coordinates directly for: {target_name}")
                                for i, v in enumerate(mesh_data.vertices):
                                    v.co = incoming_verts[i]
                            else:
                                print(f"⚠️ [INBOUND COMMIT] Structural geometry changes caught (vertex mismatch: {len(mesh_data.vertices)} local vs {len(incoming_verts)} remote) on {target_name}. Skipping mapping.")
                                # (Optional placeholder for asset snapshot reload engine fallback here)
                                
                        except Exception as commit_err:
                            print(f"❌ [INBOUND COMMIT ERROR] Geometric application collapsed: {commit_err}")
                        finally:
                            config.IS_PROCESSING_REMOTE_OP = False
                            
                        bpy.context.view_layer.update()
                        
                        # Trigger an instant viewport redraw so your friend sees the geometry change smoothly
                        for area in bpy.context.screen.areas:
                            if area.type == 'VIEW_3D':
                                area.tag_redraw()

                config.INBOUND_QUEUE.task_done()
                continue

        except queue.Empty:
            break
        except Exception as e:
            print(f"❌ [COLLAB INBOUND CRITICAL ERROR]: {e}")
        finally:
            config.IS_PROCESSING_REMOTE_OP = False

    return 0.01  # Keeps the scheduler loop ticking every 10ms smoothly