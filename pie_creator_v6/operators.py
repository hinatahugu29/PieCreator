import bpy
import os
import json
import mathutils
import blf
from bpy_extras.io_utils import ExportHelper, ImportHelper
from .storage import load_config, save_config, load_menus, save_menus, sanitize_command

# --- HUD (通知) 表示用 ---
hud_notifications = [] # (text, timestamp, x, y)
last_mouse_pos = (400, 400) # 最後に記録されたマウス位置

def draw_hud_callback(space_type):
    import time
    import gpu
    from gpu_extras.batch import batch_for_shader
    
    curr_time = time.time()
    
    # 期限切れの削除
    global hud_notifications
    hud_notifications = [n for n in hud_notifications if curr_time - n[1] < 1.5]
    
    if not hud_notifications: return

    font_id = 0
    blf.size(font_id, 24)
    shader = gpu.shader.from_builtin('UNIFORM_COLOR')
    
    for text, ts, x, y in hud_notifications:
        alpha = 1.0 - (curr_time - ts) / 1.5
        size = blf.dimensions(font_id, text)
        width, height = size[0], size[1]
        
        # 背景ボックスの描画
        padding = 10
        rect_coords = [
            (x - padding, y - padding), (x + width + padding, y - padding),
            (x - padding, y + height + padding), (x + width + padding, y + height + padding)
        ]
        indices = [(0, 1, 2), (2, 1, 3)]
        
        gpu.state.blend_set('ALPHA')
        batch = batch_for_shader(shader, 'TRIS', {"pos": rect_coords}, indices=indices)
        shader.bind()
        shader.uniform_float("color", (0.1, 0.1, 0.1, alpha * 0.7)) # ダークな半透明背景
        batch.draw(shader)
        
        # テキストの描画
        # 影
        blf.position(font_id, x + 1, y - 1, 0)
        blf.color(font_id, 0, 0, 0, alpha * 0.5)
        blf.draw(font_id, text)
        # 本体
        blf.position(font_id, x, y, 0)
        blf.color(font_id, 0.0, 0.8, 1.0, alpha) # より鮮やかなブルー
        blf.draw(font_id, text)

def show_hud(text, x=None, y=None):
    import time
    global hud_notifications, last_mouse_pos
    if x is None or y is None:
        x, y = last_mouse_pos
    hud_notifications.append((text, time.time(), x, y))

def update_mouse_pos(event):
    global last_mouse_pos
    last_mouse_pos = (event.mouse_region_x, event.mouse_region_y)

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

def get_prop_info(context):
    """右クリックされた箇所のプロパティ情報を取得する"""
    if not hasattr(context, "button_prop") or not context.button_prop:
        return None, None, None
    
    prop = context.button_prop
    ptr = context.button_pointer
    
    # プロパティ名
    prop_name = prop.identifier
    
    # データパスの生成
    # IDブロック（Material, Object, Scene等）からの相対パスを取得
    try:
        if ptr.id_data:
            id_type = ptr.id_data.rna_type.name
            # IDタイプに応じたベースパスの構築
            id_name = ptr.id_data.name
            id_type_rna = ptr.id_data.rna_type.identifier
            
            # --- スマートなパス生成 (コンテキスト優先) ---
            obj = context.active_object
            base = None
            
            if ptr.id_data == context.scene:
                base = "bpy.context.scene"
            elif obj and ptr.id_data == obj:
                base = "bpy.context.active_object"
            elif obj and obj.active_material and ptr.id_data == obj.active_material:
                base = "bpy.context.active_object.active_material"
            elif obj and obj.active_material and obj.active_material.node_tree and ptr.id_data == obj.active_material.node_tree:
                base = "bpy.context.active_object.active_material.node_tree"
            elif id_type_rna == "World" and context.scene.world and ptr.id_data == context.scene.world:
                base = "bpy.context.scene.world"
            
            # --- フォールバック (名前固定パス) ---
            if not base:
                if id_type_rna == "Scene": base = f"bpy.data.scenes['{id_name}']"
                elif id_type_rna == "Object": base = f"bpy.data.objects['{id_name}']"
                elif id_type_rna == "Material": base = f"bpy.data.materials['{id_name}']"
                elif id_type_rna == "World": base = f"bpy.data.worlds['{id_name}']"
                elif id_type_rna == "Screen": base = f"bpy.context.screen"
                elif "NodeTree" in id_type_rna:
                    # ノードグループとして存在するかチェック、無ければマテリアル等に属する特殊なツリー
                    if id_name in bpy.data.node_groups:
                        base = f"bpy.data.node_groups['{id_name}']"
                    else:
                        # 特定のマテリアルに属するツリーとして記録 (フォールバック)
                        base = f"bpy.data.node_groups.get('{id_name}')" # 安全策
                elif id_type_rna == "Brush": base = f"bpy.data.brushes['{id_name}']"
                else:
                    base = f"bpy.data.{ptr.id_data.rna_type.identifier.lower()}s['{id_name}']"
            
            path = ptr.path_from_id()
            full_path = f"{base}.{path}" if path else base
            return full_path, prop_name, prop.name
    except:
        pass
    
    return None, None, None

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
    def invoke(self, context, event):
        update_mouse_pos(event)
        execute_pie_command(self.command, label="Manual Exec")
        return {'FINISHED'}

    def execute(self, context):
        execute_pie_command(self.command, label="Manual Exec")
        return {'FINISHED'}

class PIECREATOR_OT_CallMenu(bpy.types.Operator):
    bl_idname = "wm.pie_creator_call"
    bl_label = "Call Pie Menu"
    menu_id: bpy.props.StringProperty()
    def invoke(self, context, event):
        update_mouse_pos(event)
        return self.execute(context)

    def execute(self, context):
        menus = load_menus()
        menu_data = next((m for m in menus if m["id"] == self.menu_id), None)
        menu_idname = f"PIECREATOR_MT_{self.menu_id}"
        
        wm = context.window_manager
        wm.pie_creator_active_pie_id = self.menu_id
        
        m_type = menu_data.get("type", "PIE") if menu_data else "PIE"
        
        if m_type == "PIE":
            bpy.ops.wm.call_menu_pie(name=menu_idname)
        elif m_type == "POPUP":
            # ライブ型ポップアップ (OKなし)
            bpy.ops.wm.pie_creator_popup('INVOKE_DEFAULT', menu_id=self.menu_id, use_dialog=False)
        elif m_type == "DIALOG":
            # 確定型ダイアログ (OKあり)
            bpy.ops.wm.pie_creator_popup('INVOKE_DEFAULT', menu_id=self.menu_id, use_dialog=True)
        elif m_type == "STACK":
            bpy.ops.wm.pie_creator_stack('INVOKE_DEFAULT', menu_id=self.menu_id)
        elif m_type == "STICKY":
            bpy.ops.wm.pie_creator_sticky('INVOKE_DEFAULT', menu_id=self.menu_id)
        else: # MENU
            bpy.ops.wm.call_menu(name=menu_idname)
        return {'FINISHED'}

stack_indices = {}
class PIECREATOR_OT_CallStack(bpy.types.Operator):
    bl_idname = "wm.pie_creator_stack"
    bl_label = "Call Stack Item"
    menu_id: bpy.props.StringProperty()
    def invoke(self, context, event):
        update_mouse_pos(event)
        return self.execute(context)

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
            show_hud(f"Stack: {item.get('label', 'Action')}")
        stack_indices[self.menu_id] = (idx + 1) % len(items)
        return {'FINISHED'}

class PIECREATOR_OT_StickyKey(bpy.types.Operator):
    bl_idname = "wm.pie_creator_sticky"
    bl_label = "Sticky Key Action"
    bl_options = {'REGISTER', 'UNDO'}
    
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
        update_mouse_pos(event)
        # どのキーが押されたかを記憶し、リリース判定に利用する
        self.key_type = event.type if event else 'UNKNOWN'
        self.execute_sticky(0, "Press")
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

# --- マクロレコーダー ---

macro_recording_buffer = []
last_seen_op_id = None       # 策B: 最後に記録したオペレーターの id()
current_recording_menu_id = ""

# 策A: Undoハンドラー — Undo/Redo時にスナップショットを再同期
from bpy.app.handlers import persistent

@persistent
def _macro_on_undo_redo(scene):
    """Undo/Redo 後にオペレーター追跡の基準点を再同期する"""
    global last_seen_op_id, macro_recording_buffer
    try:
        wm = bpy.context.window_manager
        if not getattr(wm, 'pie_creator_is_recording', False):
            return
        ops = list(wm.operators)
        # 基準点を現在の末尾に再設定
        last_seen_op_id = id(ops[-1]) if ops else None
        # Undoされた操作 = 「なかったこと」なのでバッファの最後を削除
        if macro_recording_buffer:
            removed = macro_recording_buffer.pop()
            print(f"PieCreator Recorder: Undo detected, removed '{removed.get('label', '?')}' from buffer")
    except Exception as e:
        print(f"PieCreator: Undo handler error: {e}")

def macro_recorder_timer():
    """策B: スナップショットベースの差分検出タイマー"""
    global last_seen_op_id, macro_recording_buffer
    wm = bpy.context.window_manager
    if not wm.pie_creator_is_recording:
        return None
    try:
        ops = list(wm.operators)
        if not ops:
            return 0.1

        current_last_id = id(ops[-1])
        
        # 初回（基準点未設定）の場合は現在位置を基準にして次回から検出開始
        if last_seen_op_id is None:
            last_seen_op_id = current_last_id
            return 0.1
        
        # 基準点と同じ → 新規操作なし
        if current_last_id == last_seen_op_id:
            return 0.1
        
        # 末尾から逆走査して、前回記録した地点を見つける
        new_ops = []
        for op in reversed(ops):
            if id(op) == last_seen_op_id:
                break
            # PieCreator自身のオペレーターは除外
            bl_idname = getattr(op, 'bl_idname', '')
            if not bl_idname or "pie_creator" in bl_idname.lower():
                continue
            cmd = get_op_command(op)
            label = get_op_label(op)
            if cmd:
                new_ops.append({"type": "COMMAND", "label": label, "command": cmd, "icon": "NONE"})
        
        if new_ops:
            new_ops.reverse()  # 時系列順に戻す
            macro_recording_buffer.extend(new_ops)
            count = len(macro_recording_buffer)
            latest = new_ops[-1]['label']
            # HUDで最新のキャプチャを通知
            show_hud(f"● REC [{count}]: {latest}")
        
        # 基準点を更新
        last_seen_op_id = current_last_id

    except Exception as e:
        print(f"PieCreator Timer Error: {e}")
    return 0.1

class PIECREATOR_OT_MacroRecorder(bpy.types.Operator):
    bl_idname = "wm.pie_creator_macro_recorder"
    bl_label = "Macro Recorder"
    menu_id: bpy.props.StringProperty()
    def execute(self, context):
        wm = context.window_manager
        global last_seen_op_id, current_recording_menu_id, macro_recording_buffer
        if not wm.pie_creator_is_recording:
            # === 録画開始 ===
            wm.pie_creator_is_recording = True
            macro_recording_buffer = []
            ops = list(wm.operators)
            last_seen_op_id = id(ops[-1]) if ops else None
            current_recording_menu_id = self.menu_id
            # タイマー登録
            if not bpy.app.timers.is_registered(macro_recorder_timer):
                bpy.app.timers.register(macro_recorder_timer)
            # Undoハンドラー登録
            if _macro_on_undo_redo not in bpy.app.handlers.undo_post:
                bpy.app.handlers.undo_post.append(_macro_on_undo_redo)
            if _macro_on_undo_redo not in bpy.app.handlers.redo_post:
                bpy.app.handlers.redo_post.append(_macro_on_undo_redo)
            self.report({'INFO'}, "録画開始")
        else:
            # === 録画停止 ===
            wm.pie_creator_is_recording = False
            # Undoハンドラー解除
            if _macro_on_undo_redo in bpy.app.handlers.undo_post:
                bpy.app.handlers.undo_post.remove(_macro_on_undo_redo)
            if _macro_on_undo_redo in bpy.app.handlers.redo_post:
                bpy.app.handlers.redo_post.remove(_macro_on_undo_redo)
            
            if not macro_recording_buffer:
                self.report({'WARNING'}, "録画した操作がありません")
                return {'FINISHED'}
            
            # menu_id が未指定の場合は最初のメニューに追加
            target_menu_id = current_recording_menu_id
            if not target_menu_id:
                menus = load_menus()
                if menus:
                    target_menu_id = menus[0]["id"]
                    self.report({'INFO'}, f"保存先未指定のため '{menus[0]['name']}' に追加します")
                else:
                    self.report({'ERROR'}, "保存先メニューがありません")
                    return {'CANCELLED'}
            
            menus = load_menus()
            menu = next((m for m in menus if m["id"] == target_menu_id), None)
            if menu:
                menu["items"].extend(macro_recording_buffer)
                save_menus(menus); bpy.ops.wm.pie_creator_reload()
                self.report({'INFO'}, f"{len(macro_recording_buffer)} 件を '{menu['name']}' に追加しました")
            else:
                self.report({'ERROR'}, f"メニュー '{target_menu_id}' が見つかりません")
        return {'FINISHED'}

# --- キャプチャ & コンテキストメニュー対応 ---

class PIECREATOR_OT_Capture(bpy.types.Operator):
    bl_idname = "wm.pie_creator_capture"
    bl_label = "Capture Active Command"
    def execute(self, context):
        wm = context.window_manager
        
        # 1. コンテキストメニュー表示時に事前保存されたバッファを優先
        cmd = wm.pie_creator_ctx_command
        label = wm.pie_creator_ctx_label
        
        # 2. バッファが空の場合は、従来のヒストリからの取得を試みる (フォールバック)
        if not cmd and wm.operators:
            target_op = wm.operators[-1]
            op_id = getattr(target_op, "bl_idname", "").lower()
            if "pie_creator" in op_id and len(wm.operators) > 1:
                target_op = wm.operators[-2]
                op_id = getattr(target_op, "bl_idname", "").lower()
            
            if target_op and "pie_creator" not in op_id:
                cmd = get_op_command(target_op)
                label = get_op_label(target_op)
        
        if cmd:
            wm.pie_creator_buffer_command = cmd
            wm.pie_creator_buffer_label = label
            wm.pie_creator_has_buffer = True
            
            # OSのクリップボードにもコピー (Clibor等で確認可能にする)
            context.window_manager.clipboard = cmd
            
            self.report({'INFO'}, f"Captured: {label}")
            return {'FINISHED'}
        
        self.report({'WARNING'}, "No command captured.")
        return {'CANCELLED'}

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
            op_id = getattr(target_op, "bl_idname", "").lower()
            if "pie_creator" in op_id and len(wm.operators) > 1:
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

class PIECREATOR_OT_CaptureProperty(bpy.types.Operator):
    bl_idname = "wm.pie_creator_capture_prop"
    bl_label = "Capture Property"
    def execute(self, context):
        wm = context.window_manager
        
        # コンテキストメニュー表示時に事前保存されたバッファを利用
        path = wm.pie_creator_ctx_data_path
        prop = wm.pie_creator_ctx_prop_name
        label = wm.pie_creator_ctx_label
        
        if not path or not prop:
            # フォールバック: 直接の取得も試みる
            path, prop, label = get_prop_info(context)
            
        if path and prop:
            cmd_str = f"PROP|{path}|{prop}"
            wm.pie_creator_buffer_command = cmd_str
            wm.pie_creator_buffer_label = label
            wm.pie_creator_has_buffer = True
            
            # OSのクリップボードにもコピー
            context.window_manager.clipboard = cmd_str
            
            self.report({'INFO'}, f"Captured Property: {label}")
            return {'FINISHED'}
            
        self.report({'WARNING'}, "No property to capture.")
        return {'CANCELLED'}

class PIECREATOR_OT_AddPropertyToMenu(bpy.types.Operator):
    bl_idname = "wm.pie_creator_add_prop_to_menu"
    bl_label = "Add Property to Menu"
    menu_id: bpy.props.StringProperty()
    def execute(self, context):
        path, prop, label = get_prop_info(context)
        if not path or not prop: return {'CANCELLED'}
        
        menus = load_menus()
        menu = next((m for m in menus if m["id"] == self.menu_id), None)
        if menu:
            menu["items"].append({
                "type": "PROPERTY",
                "label": label,
                "data_path": path,
                "prop_name": prop,
                "icon": 'NONE',
                "poll": ""
            })
            save_menus(menus); bpy.ops.wm.pie_creator_reload()
            self.report({'INFO'}, f"Added Property to {menu['name']}: {label}")
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
            cmd = wm.pie_creator_buffer_command
            label = wm.pie_creator_buffer_label
            # PROP|data_path|prop_name 形式の場合はPROPERTYタイプとして保存
            if cmd.startswith("PROP|"):
                parts = cmd.split("|", 2)
                if len(parts) == 3:
                    menu["items"].append({"type": "PROPERTY", "label": label, "data_path": parts[1], "prop_name": parts[2], "icon": 'NONE', "poll": ""})
                else:
                    menu["items"].append({"type": "COMMAND", "label": label, "command": cmd, "icon": 'NONE'})
            else:
                menu["items"].append({"type": "COMMAND", "label": label, "command": cmd, "icon": 'NONE'})
            save_menus(menus); bpy.ops.wm.pie_creator_reload()
        return {'FINISHED'}

class PIECREATOR_OT_AddBufferedToMenu(bpy.types.Operator):
    """draw_context_menu で先取り保存されたバッファから、指定メニューに項目を追加する"""
    bl_idname = "wm.pie_creator_add_buffered_to_menu"
    bl_label = "Add Buffered Item to Menu"
    menu_id: bpy.props.StringProperty()
    
    def execute(self, context):
        wm = context.window_manager
        is_prop = wm.pie_creator_ctx_is_prop
        
        menus = load_menus()
        menu = next((m for m in menus if m["id"] == self.menu_id), None)
        if not menu:
            self.report({'WARNING'}, "Menu not found.")
            return {'CANCELLED'}
        
        if is_prop:
            # プロパティタイプの追加
            path = wm.pie_creator_ctx_data_path
            prop = wm.pie_creator_ctx_prop_name
            label = wm.pie_creator_ctx_label
            if not path or not prop:
                self.report({'WARNING'}, "No property data captured.")
                return {'CANCELLED'}
            menu["items"].append({
                "type": "PROPERTY",
                "label": label,
                "data_path": path,
                "prop_name": prop,
                "icon": 'NONE',
                "poll": ""
            })
        else:
            # コマンドタイプの追加
            cmd = wm.pie_creator_ctx_command
            label = wm.pie_creator_ctx_label
            if not cmd:
                self.report({'WARNING'}, "No command captured.")
                return {'CANCELLED'}
            menu["items"].append({
                "type": "COMMAND",
                "label": label,
                "command": cmd,
                "icon": 'NONE'
            })
        
        save_menus(menus)
        bpy.ops.wm.pie_creator_reload()
        self.report({'INFO'}, f"Added to {menu['name']}: {wm.pie_creator_ctx_label}")
        return {'FINISHED'}


# --- コマンドプール (パーツ倉庫) ---

class PIECREATOR_OT_AddToPool(bpy.types.Operator):
    bl_idname = "wm.pie_creator_add_to_pool"
    bl_label = "Add to Command Pool"
    command: bpy.props.StringProperty()
    label: bpy.props.StringProperty()
    
    def execute(self, context):
        from .storage import load_config, save_config
        config = load_config()
        pool = config.setdefault("command_pool", [])
        
        # すでにバッファにあるか、引数から取得
        cmd = self.command if self.command else context.window_manager.pie_creator_ctx_command
        lbl = self.label if self.label else context.window_manager.pie_creator_ctx_label
        
        if not cmd:
            self.report({'WARNING'}, "No command to add.")
            return {'CANCELLED'}
            
        pool.append({"label": lbl, "command": cmd})
        save_config(config)
        self.report({'INFO'}, f"Added to Pool: {lbl}")
        return {'FINISHED'}

class PIECREATOR_OT_CaptureValueAsCommand(bpy.types.Operator):
    bl_idname = "wm.pie_creator_capture_value_as_cmd"
    bl_label = "Capture Current Value as Part"
    
    def execute(self, context):
        from .storage import load_config, save_config
        wm = context.window_manager
        
        # 事前保存バッファを利用
        path = wm.pie_creator_ctx_data_path
        prop = wm.pie_creator_ctx_prop_name
        label = wm.pie_creator_ctx_label
        
        if not path or not prop:
            path, prop, label = get_prop_info(context)
            
        if not path or not prop:
            self.report({'WARNING'}, "No property to capture value from.")
            return {'CANCELLED'}
        
        # 現在の値を取得して代入文を作る
        try:
            data = eval(path, {"bpy": bpy, "context": context})
            val = getattr(data, prop)
            # 値の型に応じて整形
            if isinstance(val, str): val_str = f"'{val}'"
            else: val_str = str(val)
            
            cmd = f"{path}.{prop} = {val_str}"
            
            config = load_config()
            pool = config.setdefault("command_pool", [])
            pool.append({"label": f"Set {label} to {val_str}", "command": cmd})
            save_config(config)
            
            # OSのクリップボードにもコピー
            context.window_manager.clipboard = cmd
            
            self.report({'INFO'}, f"Captured Value: {label} = {val_str}")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Capture Failed: {e}")
            return {'CANCELLED'}

class PIECREATOR_OT_MovePoolItem(bpy.types.Operator):
    bl_idname = "wm.pie_creator_move_pool_item"
    bl_label = "Move Pool Item"
    index: bpy.props.IntProperty()
    direction: bpy.props.EnumProperty(items=[('UP', "Up", ""), ('DOWN', "Down", "")])
    
    def execute(self, context):
        from .storage import load_config, save_config
        config = load_config()
        pool = config.get("command_pool", [])
        
        idx = self.index
        new_idx = idx - 1 if self.direction == 'UP' else idx + 1
        
        if 0 <= new_idx < len(pool):
            pool[idx], pool[new_idx] = pool[new_idx], pool[idx]
            save_config(config)
            
            # 選択インデックスも追従させる
            wm = context.window_manager
            current = wm.pie_creator_pool_selections.split(",") if wm.pie_creator_pool_selections else []
            if str(idx) in current and str(new_idx) not in current:
                current.remove(str(idx)); current.append(str(new_idx))
            elif str(new_idx) in current and str(idx) not in current:
                current.remove(str(new_idx)); current.append(str(idx))
            wm.pie_creator_pool_selections = ",".join(sorted(current, key=int))
            
        return {'FINISHED'}

class PIECREATOR_OT_RemoveFromPool(bpy.types.Operator):
    bl_idname = "wm.pie_creator_remove_from_pool"
    bl_label = "Remove from Pool"
    index: bpy.props.IntProperty()
    
    def execute(self, context):
        from .storage import load_config, save_config
        config = load_config()
        pool = config.get("command_pool", [])
        if 0 <= self.index < len(pool):
            pool.pop(self.index)
            save_config(config)
        return {'FINISHED'}

class PIECREATOR_OT_PoolAssembleToMenu(bpy.types.Operator):
    bl_idname = "wm.pie_creator_pool_assemble"
    bl_label = "Assemble to Menu"
    menu_id: bpy.props.StringProperty()
    
    # どのパーツを合体させるかのインデックスをカンマ区切りで受け取る
    selected_indices: bpy.props.StringProperty() 
    
    def execute(self, context):
        from .storage import load_config, save_config
        config = load_config()
        pool = config.get("command_pool", [])
        menus = config.get("menus", [])
        menu = next((m for m in menus if m["id"] == self.menu_id), None)
        
        if not menu or not self.selected_indices: return {'CANCELLED'}
        
        indices = [int(i) for i in self.selected_indices.split(",") if i.strip()]
        selected_parts = [pool[i] for i in indices if 0 <= i < len(pool)]
        
        if not selected_parts: return {'CANCELLED'}
        
        # セミコロンで合体
        combined_cmd = " ; ".join([p["command"] for p in selected_parts])
        combined_label = " + ".join([p["label"] for p in selected_parts])[:40]
        
        menu["items"].append({
            "type": "COMMAND",
            "label": combined_label,
            "command": combined_cmd,
            "icon": 'NONE'
        })
        
        save_config(config)
        bpy.ops.wm.pie_creator_reload()
        self.report({'INFO'}, f"Assembled {len(selected_parts)} parts into {menu['name']}")
        return {'FINISHED'}

# --- クリップボード (Move/Copy) ---

class PIECREATOR_OT_CopyItem(bpy.types.Operator):
    bl_idname = "wm.pie_creator_copy_item"
    bl_label = "Copy Item"
    menu_id: bpy.props.StringProperty()
    item_index: bpy.props.IntProperty()
    
    def execute(self, context):
        menus = load_menus()
        menu = next((m for m in menus if m["id"] == self.menu_id), None)
        if not menu or not (0 <= self.item_index < len(menu["items"])):
            return {'CANCELLED'}
        
        item = menu["items"][self.item_index]
        wm = context.window_manager
        wm.pie_creator_item_clipboard = json.dumps(item)
        wm.pie_creator_clipboard_source_menu = self.menu_id
        wm.pie_creator_clipboard_is_cut = False
        
        self.report({'INFO'}, f"Copied: {item.get('label', 'Item')}")
        return {'FINISHED'}

class PIECREATOR_OT_CutItem(bpy.types.Operator):
    bl_idname = "wm.pie_creator_cut_item"
    bl_label = "Cut Item"
    menu_id: bpy.props.StringProperty()
    item_index: bpy.props.IntProperty()
    
    def execute(self, context):
        menus = load_menus()
        menu = next((m for m in menus if m["id"] == self.menu_id), None)
        if not menu or not (0 <= self.item_index < len(menu["items"])):
            return {'CANCELLED'}
        
        item = menu["items"][self.item_index]
        wm = context.window_manager
        wm.pie_creator_item_clipboard = json.dumps(item)
        wm.pie_creator_clipboard_source_menu = self.menu_id
        wm.pie_creator_clipboard_is_cut = True
        
        # Cutの場合はUI上で「予約」状態にするだけでも良いが、
        # シンプルに一度抜いてしまうか、Paste時に抜くか。
        # ここではPaste時に抜く（またはキャンセル時に戻す）のは複雑なので、
        # 「移動準備」として扱い、Paste時に元の場所から消す。
        # ただし、UIのフィードバックのためにここでは何もしないか、フラグだけ立てる。
        
        self.report({'INFO'}, f"Cut: {item.get('label', 'Item')}")
        return {'FINISHED'}

class PIECREATOR_OT_PasteItem(bpy.types.Operator):
    bl_idname = "wm.pie_creator_paste_item"
    bl_label = "Paste Item"
    menu_id: bpy.props.StringProperty()
    item_index: bpy.props.IntProperty(default=-1) # -1 means append
    
    def execute(self, context):
        wm = context.window_manager
        if not wm.pie_creator_item_clipboard:
            self.report({'WARNING'}, "Clipboard is empty")
            return {'CANCELLED'}
            
        try:
            item = json.loads(wm.pie_creator_item_clipboard)
        except:
            return {'CANCELLED'}
            
        menus = load_menus()
        target_menu = next((m for m in menus if m["id"] == self.menu_id), None)
        if not target_menu:
            return {'CANCELLED'}
            
        # Cutの場合は元の場所から削除
        if wm.pie_creator_clipboard_is_cut:
            src_menu_id = wm.pie_creator_clipboard_source_menu
            src_menu = next((m for m in menus if m["id"] == src_menu_id), None)
            if src_menu:
                # 内容が一致するものを探して削除（インデックスだとズレる可能性があるため）
                # ただし、全く同じ項目がある可能性もあるので、まずは単純に検索
                for i, it in enumerate(src_menu["items"]):
                    if json.dumps(it) == wm.pie_creator_item_clipboard:
                        src_menu["items"].pop(i)
                        break
            wm.pie_creator_item_clipboard = "" # 使い切り
            wm.pie_creator_clipboard_is_cut = False
            
        if self.item_index == -1:
            target_menu["items"].append(item)
        else:
            target_menu["items"].insert(self.item_index, item)
            
        save_menus(menus)
        bpy.ops.wm.pie_creator_reload()
        return {'FINISHED'}

class PIECREATOR_OT_TogglePoolSelection(bpy.types.Operator):
    bl_idname = "wm.pie_creator_toggle_pool_selection"
    bl_label = "Toggle Pool Selection"
    index: bpy.props.IntProperty()
    
    def execute(self, context):
        wm = context.window_manager
        current = wm.pie_creator_pool_selections.split(",") if wm.pie_creator_pool_selections else []
        idx_str = str(self.index)
        
        if idx_str in current:
            current.remove(idx_str)
        else:
            current.append(idx_str)
            
        wm.pie_creator_pool_selections = ",".join(sorted(current, key=int))
        return {'FINISHED'}

class PIECREATOR_OT_DuplicateItem(bpy.types.Operator):
    bl_idname = "wm.pie_creator_duplicate_item"
    bl_label = "Duplicate Item"
    menu_id: bpy.props.StringProperty()
    item_index: bpy.props.IntProperty()
    
    def execute(self, context):
        menus = load_menus()
        menu = next((m for m in menus if m["id"] == self.menu_id), None)
        if not menu or not (0 <= self.item_index < len(menu["items"])):
            return {'CANCELLED'}
        
        import copy
        item_copy = copy.deepcopy(menu["items"][self.item_index])
        menu["items"].insert(self.item_index + 1, item_copy)
        
        save_menus(menus)
        bpy.ops.wm.pie_creator_reload()
        return {'FINISHED'}

# --- ユーティリティ ---

class PIECREATOR_OT_ReloadMenus(bpy.types.Operator):
    bl_idname = "wm.pie_creator_reload"
    bl_label = "Reload & Sync"
    def execute(self, context):
        from .storage import load_config, save_config
        # 現在の設定をロードして保存し直すことで、現在のキーマップをJSONに同期・永続化する
        config = load_config()
        save_config(config)
        
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
            m_type = menu_data.get("type", "PIE")
            
            if m_type in {"PIE", "DIALOG"}:
                bpy.ops.wm.pie_creator_call('INVOKE_DEFAULT', menu_id=m_id)
            elif m_type == "STACK":
                bpy.ops.wm.pie_creator_stack('INVOKE_DEFAULT', menu_id=m_id)
            elif m_type == "STICKY":
                bpy.ops.wm.pie_creator_sticky('INVOKE_DEFAULT', menu_id=m_id)
            elif m_type == "POPUP":
                bpy.ops.wm.pie_creator_popup('INVOKE_DEFAULT', menu_id=m_id)
            else:
                bpy.ops.wm.pie_creator_call('INVOKE_DEFAULT', menu_id=m_id)
        return {'FINISHED'}

class PIECREATOR_OT_ExportSettings(bpy.types.Operator, ExportHelper):
    bl_idname = "wm.pie_creator_export"
    bl_label = "Export Settings"
    
    filename_ext = ".json"
    filter_glob: bpy.props.StringProperty(default="*.json", options={'HIDDEN'})
    
    def execute(self, context):
        config = load_config()
        with open(self.filepath, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        self.report({'INFO'}, f"Exported: {os.path.basename(self.filepath)}")
        return {'FINISHED'}

class PIECREATOR_OT_ImportSettings(bpy.types.Operator, ImportHelper):
    bl_idname = "wm.pie_creator_import"
    bl_label = "Import Settings"
    
    filename_ext = ".json"
    filter_glob: bpy.props.StringProperty(default="*.json", options={'HIDDEN'})

    def execute(self, context):
        if os.path.exists(self.filepath):
            with open(self.filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, dict) and "menus" in data:
                save_config(data)
                bpy.ops.wm.pie_creator_reload()
                self.report({'INFO'}, f"Imported: {os.path.basename(self.filepath)}")
            else:
                self.report({'ERROR'}, "Invalid settings file.")
        return {'FINISHED'}

class PIECREATOR_OT_CreateAndLinkSubmenu(bpy.types.Operator):
    bl_idname = "wm.pie_creator_create_link_submenu"
    bl_label = "Create & Link New Menu"
    menu_id: bpy.props.StringProperty()
    item_index: bpy.props.IntProperty(default=-1)
    label: bpy.props.StringProperty()
    icon: bpy.props.StringProperty()
    def execute(self, context):
        from .storage import generate_unique_id
        menus = load_menus()
        parent = next((m for m in menus if m["id"] == self.menu_id), None)
        if not parent:
            self.report({'ERROR'}, "親メニューが見つかりませんでした")
            return {'CANCELLED'}

        # 新しいサブメニューの作成
        new_id = generate_unique_id("sub_menu", menus)
        parent_deck = parent.get("deck_id", "default")
        new_menu = {
            "id": new_id, 
            "name": f"Sub of {parent['name']}", 
            "type": "PIE", 
            "deck_id": parent_deck, 
            "modes": [], 
            "areas": [], 
            "items": []
        }
        menus.append(new_menu)

        # 親メニューへのリンク項目の作成/更新
        items = parent.get("items", [])
        new_item = {
            "type": "MENU", 
            "label": self.label if self.label else "New Submenu", 
            "icon": self.icon if self.icon else "NONE", 
            "menu_id": new_id
        }

        if self.item_index == -1:
            items.append(new_item)
        elif 0 <= self.item_index < len(items):
            items[self.item_index] = new_item
        
        save_menus(menus)
        bpy.ops.wm.pie_creator_reload()
        
        self.report({'INFO'}, f"サブメニュー '{new_id}' を作成してリンクしました")
        
        # 重要な変更: これを呼ぶことで、AddItemダイアログ側の保存をスキップさせる（あるいはダイアログを閉じる）
        # ただし直接閉じるのは難しいため、完了を強調する
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

class PIECREATOR_OT_PopupDialog(bpy.types.Operator):
    bl_idname = "wm.pie_creator_popup"
    bl_label = "PieCreator Dialog"
    bl_options = {'REGISTER', 'UNDO'}
    
    menu_id: bpy.props.StringProperty()
    use_dialog: bpy.props.BoolProperty(default=True)
    
    def draw(self, context):
        from .storage import load_menus
        from .menus import draw_menu_items
        menus = load_menus()
        menu_data = next((m for m in menus if m["id"] == self.menu_id), None)
        if menu_data:
            layout = self.layout
            # プロパティの分割をオフにする (左側の余白を消す)
            layout.use_property_split = False
            draw_menu_items(layout, menu_data["items"], context)
            
    def execute(self, context):
        return {'FINISHED'}
        
    def invoke(self, context, event):
        update_mouse_pos(event)
        if self.use_dialog:
            # 確定型 (OKボタンあり)
            return context.window_manager.invoke_props_dialog(self)
        else:
            # ライブ型 (マウスを離すと消える)
            return context.window_manager.invoke_popup(self)

classes = (
    PIECREATOR_OT_Exec,
    PIECREATOR_OT_CallMenu,
    PIECREATOR_OT_CallStack,
    PIECREATOR_OT_StickyKey,
    PIECREATOR_OT_PopupDialog,
    PIECREATOR_OT_MacroRecorder,
    PIECREATOR_OT_CallMaster,
    PIECREATOR_OT_ExportSettings,
    PIECREATOR_OT_ImportSettings,
    PIECREATOR_OT_ReloadMenus,
    PIECREATOR_OT_Capture,
    PIECREATOR_OT_CaptureProperty,
    PIECREATOR_OT_CaptureValueAsCommand,
    PIECREATOR_OT_AddToPool,
    PIECREATOR_OT_RemoveFromPool,
    PIECREATOR_OT_MovePoolItem,
    PIECREATOR_OT_PoolAssembleToMenu,
    PIECREATOR_OT_TogglePoolSelection,
    PIECREATOR_OT_AddToMenu,
    PIECREATOR_OT_AddPropertyToMenu,
    PIECREATOR_OT_Paste,
    PIECREATOR_OT_AddBufferedToMenu,
    PIECREATOR_OT_CreateAndLinkSubmenu,
    PIECREATOR_OT_ImportFromInfo,
    PIECREATOR_OT_CopyItem,
    PIECREATOR_OT_CutItem,
    PIECREATOR_OT_PasteItem,
    PIECREATOR_OT_DuplicateItem,
)

hud_handles = []

def register():
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
        except RuntimeError:
            pass
    
    global hud_handles
    # マルチスペース対応
    space_types = [
        ('SpaceView3D', 'WINDOW'),
        ('SpaceNodeEditor', 'WINDOW'),
        ('SpaceImageEditor', 'WINDOW'),
        ('SpaceSequenceEditor', 'WINDOW'),
        ('SpaceTextEditor', 'WINDOW'),
    ]
    for st_name, region in space_types:
        try:
            st = getattr(bpy.types, st_name)
            handle = st.draw_handler_add(draw_hud_callback, (st_name,), region, 'POST_PIXEL')
            hud_handles.append((st, handle, region))
        except:
            pass

def unregister():
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass
            
    global hud_handles
    for st, handle, region in hud_handles:
        try:
            st.draw_handler_remove(handle, region)
        except:
            pass
    hud_handles.clear()
