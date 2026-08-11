# SPDX-License-Identifier: GPL-3.0-or-later
import bpy
import time
from bpy.app.handlers import persistent
from ..storage import load_menus, save_menus
from ..log import log_error, log_error_once, clear_error_once

# --- バッファ ---
macro_recording_buffer = []
last_seen_op_id = None
current_recording_menu_id = ""

@persistent
def _macro_on_undo_redo(scene):
    """Undo/Redo 後にオペレーター追跡の基準点を再同期する"""
    global last_seen_op_id, macro_recording_buffer
    try:
        wm = bpy.context.window_manager
        if not getattr(wm, 'pie_creator_is_recording', False):
            return
        ops = list(wm.operators)
        last_seen_op_id = id(ops[-1]) if ops else None
        if macro_recording_buffer:
            macro_recording_buffer.pop()
    except Exception as e:
        log_error("Failed to resync the recording baseline after undo/redo", e)

def macro_recorder_timer():
    """スナップショットベースの差分検出タイマー"""
    global last_seen_op_id, macro_recording_buffer
    wm = bpy.context.window_manager
    if not wm.pie_creator_is_recording:
        return None
    try:
        ops = list(wm.operators)
        if not ops: return 0.1
        current_last_id = id(ops[-1])
        if last_seen_op_id is None:
            last_seen_op_id = current_last_id
            return 0.1
        if current_last_id == last_seen_op_id:
            return 0.1
        
        from .core import get_op_command, get_op_label, show_hud
        new_ops = []
        for op in reversed(ops):
            if id(op) == last_seen_op_id: break
            bl_idname = getattr(op, 'bl_idname', '')
            if not bl_idname or "pie_creator" in bl_idname.lower(): continue
            cmd = get_op_command(op)
            label = get_op_label(op)
            if cmd:
                new_ops.append({"type": "COMMAND", "label": label, "command": cmd, "icon": "NONE"})
        
        if new_ops:
            new_ops.reverse()
            macro_recording_buffer.extend(new_ops)
            show_hud(f"● REC [{len(macro_recording_buffer)}]: {new_ops[-1]['label']}")
        
        last_seen_op_id = current_last_id
        clear_error_once("macro_timer")
    except Exception as e:
        # 黙って止まると「録画したのに何も入らない」という最悪の症状になる。
        # タイマーは 0.1 秒ごとに走るので、同じ失敗は一度だけ報告する。
        if log_error_once("macro_timer", "Failed to capture an operator while recording", e):
            # 画面にも出して、失敗していることを利用者に伝える
            try:
                from .core import show_hud
                show_hud("REC: capture failed (see the console)")
            except Exception as hud_error:
                log_error("Could not show the recording failure on the HUD either", hud_error)
    return 0.1

class PIECREATOR_OT_MacroRecorder(bpy.types.Operator):
    """Start or stop recording. Operators you use while recording are appended to the menu as items"""
    bl_idname = "wm.pie_creator_macro_recorder"
    bl_label = "Macro Recorder"
    menu_id: bpy.props.StringProperty()
    def execute(self, context):
        wm = context.window_manager
        global last_seen_op_id, current_recording_menu_id, macro_recording_buffer
        if not wm.pie_creator_is_recording:
            wm.pie_creator_is_recording = True
            macro_recording_buffer = []
            ops = list(wm.operators)
            last_seen_op_id = id(ops[-1]) if ops else None
            current_recording_menu_id = self.menu_id
            if not bpy.app.timers.is_registered(macro_recorder_timer):
                bpy.app.timers.register(macro_recorder_timer)
            if _macro_on_undo_redo not in bpy.app.handlers.undo_post:
                bpy.app.handlers.undo_post.append(_macro_on_undo_redo)
            self.report({'INFO'}, "Recording started")
        else:
            wm.pie_creator_is_recording = False
            if _macro_on_undo_redo in bpy.app.handlers.undo_post:
                bpy.app.handlers.undo_post.remove(_macro_on_undo_redo)
            
            if not macro_recording_buffer:
                self.report({'WARNING'}, "No actions recorded")
                return {'FINISHED'}
            
            target_menu_id = current_recording_menu_id
            menus = load_menus()
            if not target_menu_id and menus:
                target_menu_id = menus[0]["id"]
            
            menu = next((m for m in menus if m["id"] == target_menu_id), None)
            if menu:
                menu["items"].extend(macro_recording_buffer)
                save_menus(menus)
                bpy.ops.wm.pie_creator_reload()
                self.report({'INFO'}, f"Added {len(macro_recording_buffer)} items to '{menu['name']}'")
        return {'FINISHED'}

class PIECREATOR_OT_Capture(bpy.types.Operator):
    """Capture the operator you last used, so it can be added to a menu"""
    bl_idname = "wm.pie_creator_capture"
    bl_label = "Capture Active Command"
    def execute(self, context):
        wm = context.window_manager
        cmd = wm.pie_creator_ctx_command
        label = wm.pie_creator_ctx_label
        
        if not cmd and wm.operators:
            target_op = wm.operators[-1]
            if "pie_creator" in getattr(target_op, "bl_idname", "").lower() and len(wm.operators) > 1:
                target_op = wm.operators[-2]
            
            from .core import get_op_command, get_op_label
            cmd = get_op_command(target_op)
            label = get_op_label(target_op)
        
        if cmd:
            wm.pie_creator_buffer_command = cmd
            wm.pie_creator_buffer_label = label
            wm.pie_creator_has_buffer = True
            context.window_manager.clipboard = cmd
            self.report({'INFO'}, f"Captured: {label}")
            return {'FINISHED'}
        return {'CANCELLED'}

class PIECREATOR_OT_CaptureProperty(bpy.types.Operator):
    """Capture the property under the cursor, so it can be added to a menu as a slider or toggle"""
    bl_idname = "wm.pie_creator_capture_prop"
    bl_label = "Capture Property"
    def execute(self, context):
        wm = context.window_manager
        path = wm.pie_creator_ctx_data_path
        prop = wm.pie_creator_ctx_prop_name
        label = wm.pie_creator_ctx_label
        
        if not path or not prop:
            from .core import get_prop_info
            path, prop, label = get_prop_info(context)
            
        if path and prop:
            cmd_str = f"PROP|{path}|{prop}"
            wm.pie_creator_buffer_command = cmd_str
            wm.pie_creator_buffer_label = label
            wm.pie_creator_has_buffer = True
            context.window_manager.clipboard = cmd_str
            self.report({'INFO'}, f"Captured Property: {label}")
            return {'FINISHED'}
        return {'CANCELLED'}

classes = (
    PIECREATOR_OT_MacroRecorder,
    PIECREATOR_OT_Capture,
    PIECREATOR_OT_CaptureProperty,
)
