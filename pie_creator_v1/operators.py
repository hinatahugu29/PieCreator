import bpy
import json
import os
import mathutils
from .storage import load_config, save_config, load_menus, save_menus, sanitize_command

# --- ヘルパー関数 (RNA/コマンド生成) ---

def get_op_command(op):
    """オペレーターから実行可能なコマンド文字列を正確に生成する"""
    if not op: return ""
    
    # bl_idname が取得できない場合のフォールバック
    idname = getattr(op, "bl_idname", None)
    if not idname and hasattr(op, "bl_rna"):
        idname = op.bl_rna.identifier
        
    if not idname: return ""
    
    try:
        # idnameの変換: MESH_OT_primitive_cube_add -> mesh.primitive_cube_add
        if "_OT_" in idname:
            # クラス名形式の場合のパース
            parts = idname.split("_OT_")
            if len(parts) == 2:
                cat, name = parts
                cmd_base = f"bpy.ops.{cat.lower()}.{name}"
            else:
                cmd_base = f"bpy.ops.{idname.lower()}"
        else:
            # 通常の idname 形式 (object.select_all 等)
            cmd_base = f"bpy.ops.{idname}"
            
        # プロパティの取得 (bl_rna経由で詳細に走査)
        p_list = []
        try:
            rna_props = op.bl_rna.properties
            for p_id in rna_props.keys():
                if p_id in {'rna_type'}: continue
                prop = rna_props[p_id]
                if prop.is_readonly: continue
                
                # インスタンスでない場合は getattr(op.properties, ...) が失敗する可能性がある
                if not hasattr(op, "properties"): continue
                val = getattr(op.properties, p_id)
                
                # 型に応じたシリアライズ
                if isinstance(val, str):
                    p_list.append(f"{p_id}='{val}'")
                elif isinstance(val, bool):
                    p_list.append(f"{p_id}={val}")
                elif isinstance(val, (int, float)):
                    p_list.append(f"{p_id}={val}")
                elif isinstance(val, (mathutils.Vector, mathutils.Euler, mathutils.Color, mathutils.Quaternion)):
                    p_list.append(f"{p_id}={list(val[:])}")
                elif isinstance(val, set):
                    items_str = ", ".join(f"'{v}'" for v in sorted(val))
                    p_list.append(f"{p_id}={{ {items_str} }}")
                elif hasattr(val, "to_list"):
                    p_list.append(f"{p_id}={val.to_list()}")
                else:
                    p_list.append(f"{p_id}={repr(val)}")
        except:
            # プロパティ取得に失敗しても、引数なしのコマンドとして継続
            pass
                
        props_str = ", ".join(p_list)
        return f"{cmd_base}({props_str})"
    except Exception as e:
        print(f"PieCreator: Command generation error: {e}")
        return ""

def get_op_label(op):
    """オペレーターの正確なラベルを取得する"""
    if not op: return "Unknown"
    
    idname = getattr(op, "bl_idname", None)
    if not idname and hasattr(op, "bl_rna"):
        idname = op.bl_rna.identifier

    try:
        if hasattr(op, "name") and op.name:
            return op.name
        
        if idname and "_OT_" in idname:
            parts = idname.split("_OT_")
            if len(parts) == 2:
                cat, name = parts
                op_rna = getattr(getattr(bpy.ops, cat.lower()), name).get_rna_type()
                if op_rna and op_rna.name:
                    return op_rna.name
    except:
        pass
    return idname if idname else "Unknown"

def get_label_from_command(command):
    """コマンド文字列からラベルを推測する"""
    if not command: return ""
    if "bpy.ops." in command:
        try:
            op_part = command.split("(")[0].replace("bpy.ops.", "")
            parts = op_part.split(".")
            if len(parts) == 2:
                cat, name = parts
                op_rna = getattr(getattr(bpy.ops, cat), name).get_rna_type()
                if op_rna and op_rna.name:
                    return op_rna.name
        except:
            pass
    return "Custom Command"

# --- 共通実行関数 ---

def execute_pie_command(command, label="Command"):
    if not command: return False
    cmd = sanitize_command(command)
    try:
        global_dict = {"bpy": bpy, "context": bpy.context, "mathutils": mathutils}
        exec(cmd, global_dict)
        return True
    except Exception as e:
        print(f"PieCreator Error [{label}]: {e}")
        return False

# --- 実行系オペレーター ---

class PIECREATOR_OT_Exec(bpy.types.Operator):
    bl_idname = "wm.pie_creator_exec"
    bl_label = "Execute Command"
    command: bpy.props.StringProperty()
    def execute(self, context):
        execute_pie_command(self.command, label="Manual Exec")
        return {'FINISHED'}

class PIECREATOR_OT_CallMenu(bpy.types.Operator):
    bl_idname = "wm.pie_creator_call"
    bl_label = "Call Pie Menu"
    menu_id: bpy.props.StringProperty()
    def execute(self, context):
        bpy.ops.wm.call_menu_pie(name=f"PIECREATOR_MT_{self.menu_id}")
        return {'FINISHED'}

stack_indices = {}
class PIECREATOR_OT_CallStack(bpy.types.Operator):
    bl_idname = "wm.pie_creator_stack"
    bl_label = "Call Stack Item"
    menu_id: bpy.props.StringProperty()
    def execute(self, context):
        menus = load_menus()
        menu_data = next((m for m in menus if m["id"] == self.menu_id), None)
        if not menu_data or not menu_data.get("items"): return {'CANCELLED'}
        items = menu_data["items"]
        idx = stack_indices.get(self.menu_id, 0)
        if idx >= len(items): idx = 0
        item = items[idx]
        if item.get("type") == "COMMAND":
            execute_pie_command(item.get("command", ""), label=f"Stack: {item.get('label')}")
        stack_indices[self.menu_id] = (idx + 1) % len(items)
        return {'FINISHED'}

class PIECREATOR_OT_StickyKey(bpy.types.Operator):
    bl_idname = "wm.pie_creator_sticky"
    bl_label = "Sticky Key Action"
    menu_id: bpy.props.StringProperty()
    key_type: bpy.props.StringProperty()
    def execute_sticky(self, idx, label_prefix):
        menus = load_menus()
        menu = next((m for m in menus if m["id"] == self.menu_id), None)
        if not menu or len(menu.get("items", [])) <= idx: return
        execute_pie_command(menu["items"][idx].get("command", ""), label=f"Sticky {label_prefix}")
    def modal(self, context, event):
        if event.type == self.key_type and event.value == 'RELEASE':
            self.execute_sticky(1, "Release")
            return {'FINISHED'}
        return {'RUNNING_MODAL'}
    def invoke(self, context, event):
        self.execute_sticky(0, "Press")
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

# --- マクロレコーダー ---

macro_recording_buffer = []
last_history_len = 0
current_recording_menu_id = ""

def macro_recorder_timer():
    wm = bpy.context.window_manager
    if not wm.pie_creator_is_recording:
        return None
    try:
        curr_len = len(wm.operators)
        global last_history_len, macro_recording_buffer
        if curr_len > last_history_len:
            new_ops = list(wm.operators)[last_history_len:]
            for op in new_ops:
                if "pie_creator" in op.bl_idname: continue
                cmd = get_op_command(op)
                label = get_op_label(op)
                if cmd:
                    macro_recording_buffer.append({"type": "COMMAND", "label": label, "command": cmd, "icon": 'NONE'})
            last_history_len = curr_len
    except Exception as e:
        print(f"PieCreator Timer Error: {e}")
    return 0.1

class PIECREATOR_OT_MacroRecorder(bpy.types.Operator):
    bl_idname = "wm.pie_creator_macro_recorder"
    bl_label = "Macro Recorder"
    menu_id: bpy.props.StringProperty()
    def execute(self, context):
        wm = context.window_manager
        global last_history_len, current_recording_menu_id, macro_recording_buffer
        if not wm.pie_creator_is_recording:
            wm.pie_creator_is_recording = True
            macro_recording_buffer = []
            last_history_len = len(wm.operators)
            current_recording_menu_id = self.menu_id
            if not bpy.app.timers.is_registered(macro_recorder_timer):
                bpy.app.timers.register(macro_recorder_timer)
            self.report({'INFO'}, "Recording Started")
        else:
            wm.pie_creator_is_recording = False
            if macro_recording_buffer and current_recording_menu_id:
                menus = load_menus()
                menu = next((m for m in menus if m["id"] == current_recording_menu_id), None)
                if menu:
                    menu["items"].extend(macro_recording_buffer)
                    save_menus(menus); bpy.ops.wm.pie_creator_reload()
                    self.report({'INFO'}, f"Added {len(macro_recording_buffer)} items to {menu['name']}")
        return {'FINISHED'}

# --- キャプチャ & コンテキストメニュー対応 ---

class PIECREATOR_OT_Capture(bpy.types.Operator):
    bl_idname = "wm.pie_creator_capture"
    bl_label = "Capture Active Command"
    def execute(self, context):
        wm = context.window_manager
        target_op = None
        if hasattr(context, "button_operator") and context.button_operator:
            target_op = context.button_operator
        elif wm.operators:
            target_op = wm.operators[-1]
            if "pie_creator" in target_op.bl_idname and len(wm.operators) > 1:
                target_op = wm.operators[-2]
        if not target_op or "pie_creator" in target_op.bl_idname: return {'CANCELLED'}
        cmd = get_op_command(target_op)
        label = get_op_label(target_op)
        if cmd:
            wm.pie_creator_buffer_command = cmd; wm.pie_creator_buffer_label = label; wm.pie_creator_has_buffer = True
            self.report({'INFO'}, f"Captured: {label}")
        return {'FINISHED'}

class PIECREATOR_OT_AddToMenu(bpy.types.Operator):
    bl_idname = "wm.pie_creator_add_to_menu"
    bl_label = "Add to Menu"
    menu_id: bpy.props.StringProperty()
    def execute(self, context):
        wm = context.window_manager
        target_op = None
        if hasattr(context, "button_operator") and context.button_operator:
            target_op = context.button_operator
        elif wm.operators:
            target_op = wm.operators[-1]
            if "pie_creator" in target_op.bl_idname and len(wm.operators) > 1:
                target_op = wm.operators[-2]
        if not target_op: 
            self.report({'WARNING'}, "No active operator found to capture.")
            return {'CANCELLED'}
        cmd = get_op_command(target_op); label = get_op_label(target_op)
        if not cmd: 
            self.report({'WARNING'}, "Failed to generate command for this operator.")
            return {'CANCELLED'}
        menus = load_menus()
        menu = next((m for m in menus if m["id"] == self.menu_id), None)
        if menu:
            menu["items"].append({"type": "COMMAND", "label": label, "command": cmd, "icon": 'NONE'})
            save_menus(menus); bpy.ops.wm.pie_creator_reload()
            self.report({'INFO'}, f"Added to {menu['name']}: {label}")
        return {'FINISHED'}

class PIECREATOR_OT_Paste(bpy.types.Operator):
    bl_idname = "wm.pie_creator_paste"
    bl_label = "Paste Captured Command"
    menu_id: bpy.props.StringProperty()
    def execute(self, context):
        wm = context.window_manager
        if not wm.pie_creator_has_buffer: return {'CANCELLED'}
        menus = load_menus()
        menu = next((m for m in menus if m["id"] == self.menu_id), None)
        if menu:
            menu["items"].append({"type": "COMMAND", "label": wm.pie_creator_buffer_label, "command": wm.pie_creator_buffer_command, "icon": 'NONE'})
            save_menus(menus); bpy.ops.wm.pie_creator_reload()
        return {'FINISHED'}

# --- ユーティリティ ---

class PIECREATOR_OT_ReloadMenus(bpy.types.Operator):
    bl_idname = "wm.pie_creator_reload"
    bl_label = "Reload & Sync"
    def execute(self, context):
        from . import register_dynamic_menus; register_dynamic_menus()
        return {'FINISHED'}

class PIECREATOR_OT_CallMaster(bpy.types.Operator):
    bl_idname = "wm.pie_creator_call_master"
    bl_label = "Call Master Menu"
    def execute(self, context):
        from .storage import load_config
        config = load_config()
        master_id = config.get("master_menu_id")
        active_deck = config.get("active_deck", "default")
        menus = config.get("menus", [])
        
        # 1. マスターIDを検索
        menu_data = next((m for m in menus if m["id"] == master_id), None)
        # 2. 見つからない場合は、アクティブデッキ内の最初のメニュー
        if not menu_data:
            menu_data = next((m for m in menus if m.get("deck_id", "default") == active_deck), None)
        # 3. それでもない場合は、全メニューの最初
        if not menu_data and menus:
            menu_data = menus[0]
            
        if menu_data:
            m_id = menu_data["id"]
            if menu_data.get("type", "PIE") == "PIE": bpy.ops.wm.pie_creator_call(menu_id=m_id)
            else: bpy.ops.wm.pie_creator_stack(menu_id=m_id)
        return {'FINISHED'}

class PIECREATOR_OT_ExportSettings(bpy.types.Operator):
    bl_idname = "wm.pie_creator_export"
    bl_label = "Export Settings"
    filepath: bpy.props.StringProperty(subtype="FILE_PATH")
    def execute(self, context):
        config = load_config()
        with open(self.filepath, 'w', encoding='utf-8') as f: json.dump(config, f, indent=2, ensure_ascii=False)
        return {'FINISHED'}
    def invoke(self, context, event): context.window_manager.fileselect_add(self); return {'RUNNING_MODAL'}

class PIECREATOR_OT_ImportSettings(bpy.types.Operator):
    bl_idname = "wm.pie_creator_import"
    bl_label = "Import Settings"
    filepath: bpy.props.StringProperty(subtype="FILE_PATH")
    def execute(self, context):
        if os.path.exists(self.filepath):
            with open(self.filepath, 'r', encoding='utf-8') as f: data = json.load(f)
            if isinstance(data, dict) and "menus" in data: save_config(data); bpy.ops.wm.pie_creator_reload()
        return {'FINISHED'}
    def invoke(self, context, event): context.window_manager.fileselect_add(self); return {'RUNNING_MODAL'}

class PIECREATOR_OT_CreateAndLinkSubmenu(bpy.types.Operator):
    bl_idname = "wm.pie_creator_create_link_submenu"
    bl_label = "Create & Link New Menu"
    menu_id: bpy.props.StringProperty()
    item_index: bpy.props.IntProperty(default=-1)
    label: bpy.props.StringProperty()
    icon: bpy.props.StringProperty()
    def execute(self, context):
        from .storage import generate_unique_id
        menus = load_menus(); parent = next((m for m in menus if m["id"] == self.menu_id), None)
        if not parent: return {'CANCELLED'}
        new_id = generate_unique_id("sub_menu", menus)
        menus.append({"id": new_id, "name": f"Sub of {parent['name']}", "type": "PIE", "modes": [], "items": []})
        item = {"type": "MENU", "label": self.label if self.label else "New Submenu", "icon": self.icon if self.icon else "NONE", "menu_id": new_id}
        items = parent.get("items", [])
        if self.item_index == -1: items.append(item)
        elif 0 <= self.item_index < len(items): items[self.item_index] = item
        save_menus(menus); bpy.ops.wm.pie_creator_reload()
        return {'FINISHED'}

class PIECREATOR_OT_ImportFromInfo(bpy.types.Operator):
    bl_idname = "wm.pie_creator_import_info"
    bl_label = "Import from Info"
    menu_id: bpy.props.StringProperty()

    def execute(self, context):
        wm = context.window_manager
        menus = load_menus()
        menu = next((m for m in menus if m["id"] == self.menu_id), None)
        
        if not menu:
            self.report({'ERROR'}, "Menu not found.")
            return {'CANCELLED'}
        
        added_count = 0
        # 直近10件の履歴から、自分以外のオペレーターを抽出して追加
        for op in list(wm.operators)[-10:]:
            if "pie_creator" in op.bl_idname: continue
            cmd = get_op_command(op)
            label = get_op_label(op)
            if cmd:
                menu["items"].append({
                    "type": "COMMAND",
                    "label": label,
                    "command": cmd,
                    "icon": 'NONE'
                })
                added_count += 1
        
        if added_count > 0:
            save_menus(menus)
            bpy.ops.wm.pie_creator_reload()
            self.report({'INFO'}, f"Imported {added_count} items from history.")
        else:
            self.report({'WARNING'}, "No operators found in history.")
            
        return {'FINISHED'}

classes = (
    PIECREATOR_OT_Exec,
    PIECREATOR_OT_CallMenu,
    PIECREATOR_OT_CallStack,
    PIECREATOR_OT_StickyKey,
    PIECREATOR_OT_MacroRecorder,
    PIECREATOR_OT_CallMaster,
    PIECREATOR_OT_ExportSettings,
    PIECREATOR_OT_ImportSettings,
    PIECREATOR_OT_ReloadMenus,
    PIECREATOR_OT_Capture,
    PIECREATOR_OT_AddToMenu,
    PIECREATOR_OT_Paste,
    PIECREATOR_OT_CreateAndLinkSubmenu,
    PIECREATOR_OT_ImportFromInfo,
)

def register():
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
        except RuntimeError:
            pass

def unregister():
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass
