import bpy
import os
import json
import mathutils
import blf
import webbrowser
from bpy_extras.io_utils import ExportHelper, ImportHelper
from .storage import load_config, save_config, load_menus, save_menus, sanitize_command

# --- HUD (通知) 表示用 ---
hud_notifications = [] # (text, timestamp, x, y)
last_mouse_pos = (400, 400) # 最後に記録されたマウス位置

# --- メニュースクレイピング用基盤 ---

class PIECREATOR_ScrapedItem(bpy.types.PropertyGroup):
    """スクレイピングされた一時的な項目を保持するクラス"""
    label: bpy.props.StringProperty()
    idname: bpy.props.StringProperty()
    props_json: bpy.props.StringProperty() # JSON形式でプロパティを保存
    icon: bpy.props.StringProperty(default="NONE")
    selected: bpy.props.BoolProperty(default=True)
    item_type: bpy.props.EnumProperty(
        items=[('COMMAND', "Command", ""), ('MENU', "Menu", ""), ('LABEL', "Label", "")],
        default='COMMAND'
    )

class PropertySniffer:
    """オペレーターのプロパティ代入を検知する"""
    def __init__(self, target_dict):
        self.target_dict = target_dict
    def __setattr__(self, name, value):
        if name == "target_dict":
            super().__setattr__(name, value)
        else:
            self.target_dict[name] = value
    def __getattr__(self, name):
        return self

class MockLayout:
    """UILayoutのメソッド呼び出しをインターセプトして記録する"""
    def __init__(self, verbose=True):
        self.results = []
        self.verbose = verbose
    
    def operator(self, idname, text="", icon="NONE", emboss=True, depress=False, icon_value=0):
        if self.verbose:
            print(f"  [Scraper] Found Op: {idname} (Label: '{text}')")
        item = {
            "type": "COMMAND",
            "idname": idname,
            "label": text,
            "icon": icon,
            "properties": {}
        }
        self.results.append(item)
        return PropertySniffer(item["properties"])

    def menu(self, menu_id, text="", icon="NONE"):
        if self.verbose:
            print(f"  [Scraper] Found Submenu: {menu_id} (Label: '{text}')")
        self.results.append({
            "type": "MENU",
            "idname": menu_id,
            "label": text,
            "icon": icon
        })

    def label(self, text="", icon="NONE"):
        if text:
            if self.verbose: print(f"  [Scraper] Found Label: '{text}'")
            self.results.append({"type": "LABEL", "label": text, "icon": icon})

    def separator(self, factor=1.0): pass
    def row(self, align=False, heading="", heading_ctxt=""): return self
    def column(self, align=False, heading="", heading_ctxt=""): return self
    def box(self): return self
    def split(self, factor=0.0, align=False): return self
    def grid_flow(self, **kwargs): return self
    
    def __getattr__(self, name):
        """UILayoutの未知のプロパティやメソッドへのアクセスを安全にフォールバックする"""
        # よくアクセスされる UILayout プロパティのデフォルト値
        if name in {'operator_context', 'alignment', 'direction', 'emboss'}:
            return 'INVOKE_DEFAULT'
        if name in {'enabled', 'active'}:
            return True
        if name.startswith('use_'):
            return False
        if name in {'scale_x', 'scale_y', 'ui_units_x', 'ui_units_y'}:
            return 1.0
            
        # 未知のメソッド呼び出し (layout.prop() や layout.template_xxx() など) に対しては
        # エラーにならないように自身を返すダミー関数を返す
        return lambda *args, **kwargs: self

def update_blender_menus_list():
    """Blender内に登録されている全メニュークラスをスキャンしてリスト化する"""
    import bpy
    wm = bpy.context.window_manager
    wm.pie_creator_blender_menus.clear()
    
    # 登録されている全クラスを走査
    for attr in dir(bpy.types):
        if attr.startswith("PIECREATOR_MT_"): continue # 自身は除外
        
        cls = getattr(bpy.types, attr)
        # Menuのサブクラスかつ、idnameを持っているものを抽出
        if isinstance(cls, type) and issubclass(cls, bpy.types.Menu):
            if hasattr(cls, "bl_idname") or attr.isupper():
                label = getattr(cls, "bl_label", "No Label")
                item = wm.pie_creator_blender_menus.add()
                # 検索しやすさのため ID と Label を併記するハック
                item.name = f"{attr}  | {label}"

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
    
    idname = getattr(op, "bl_idname", None)
    if not idname and hasattr(op, "bl_rna"):
        idname = op.bl_rna.identifier
    
    # --- Debug Logging ---
    print(f"\nPieCreator Debug: --- Capture Start ---")
    print(f"PieCreator Debug: Operator ID: {idname}")
    print(f"PieCreator Debug: Has 'properties' attr: {hasattr(op, 'properties')}")
    if not hasattr(op, "properties"):
        print(f"PieCreator Debug: Available attributes: {dir(op)}")
    
    if not idname: return ""
    
    try:
        if "_OT_" in idname:
            parts = idname.split("_OT_")
            if len(parts) == 2:
                cat, name = parts
                cmd_base = f"bpy.ops.{cat.lower()}.{name}"
            else:
                cmd_base = f"bpy.ops.{idname.lower()}"
        else:
            cmd_base = f"bpy.ops.{idname}"
            
        p_list = []
        
        # プロパティの取得元を特定 (通常のインスタンス or ボタン定義)
        props_source = None
        if hasattr(op, "properties"):
            props_source = op.properties
        elif hasattr(op, "p"): # 一部の内部構造
            props_source = op.p
        
        # rna情報の取得
        rna_source = None
        if hasattr(op, "bl_rna"): rna_source = op.bl_rna
        elif hasattr(op, "rna_type"): rna_source = op.rna_type
        
        if rna_source:
            rna_props = rna_source.properties
            print(f"PieCreator Debug: RNA properties count: {len(rna_props)}")
            
            for p_id in rna_props.keys():
                if p_id in {'rna_type'}: continue
                prop = rna_props[p_id]
                if prop.is_readonly: continue
                
                # インスタンスがあれば設定状況を確認
                is_set = False
                if hasattr(op, "is_property_set"):
                    is_set = op.is_property_set(p_id)
                
                try:
                    # プロパティ値の取得を試行
                    val = None
                    if props_source:
                        val = getattr(props_source, p_id)
                    elif hasattr(op, p_id):
                        val = getattr(op, p_id)
                    
                    if val is None: continue
                    
                    # デバッグ用
                    if "add_node" in idname.lower() and p_id in {"type", "use_transform"}:
                        print(f"PieCreator Debug:   Found {p_id}='{val}' (is_set={is_set})")
                    
                    if not is_set and p_id != "type":
                        continue
                    
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
                    continue
                
        props_str = ", ".join(p_list)
        print(f"PieCreator Debug: Generated: {cmd_base}({props_str})")
        print(f"PieCreator Debug: --- Capture End ---\n")
        
        return f"{cmd_base}({props_str})"
    except Exception as e:
        print(f"PieCreator: Error: {e}")
        return ""

def get_op_label(op):
    """オペレーターの正確なラベルを取得する"""
    if not op: return "Unknown"
    
    idname = getattr(op, "bl_idname", None)
    if not idname and hasattr(op, "bl_rna"):
        idname = op.bl_rna.identifier

    try:
        # --- 特別対応: ノード追加 (add_node) の場合 ---
        if idname == "NODE_OT_add_node" or (idname and "add_node" in idname.lower()):
            node_type = None
            if hasattr(op, "type"):
                node_type = op.type
            elif hasattr(op, "properties") and hasattr(op.properties, "type"):
                node_type = op.properties.type
            
            if node_type:
                # bpy.types から本来の表示名を取得を試みる
                if hasattr(bpy.types, node_type):
                    node_cls = getattr(bpy.types, node_type)
                    if hasattr(node_cls, "bl_rna"):
                        return f"Add {node_cls.bl_rna.name}"
                return f"Add {node_type.replace('ShaderNode', '').replace('GeometryNode', '').replace('Node', '')}"

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
    
    # 1. ノード追加コマンドの特殊解析
    if "node.add_node" in command:
        try:
            import re
            # type='...' または type="..." を抽出
            match = re.search(r"type=['\"](.+?)['\"]", command)
            if match:
                node_type = match.group(1)
                if hasattr(bpy.types, node_type):
                    node_cls = getattr(bpy.types, node_type)
                    if hasattr(node_cls, "bl_rna"):
                        return f"Add {node_cls.bl_rna.name}"
                return f"Add {node_type.replace('ShaderNode', '').replace('GeometryNode', '').replace('Node', '')}"
        except:
            pass

    # 2. 標準的なオペレーター解析
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
        error_msg = str(e)
        print(f"PieCreator Error [{label}]: {error_msg}")
        
        # --- 親切設計: エラーの解釈と通知 ---
        friendly_msg = None
        
        # ノード関連のよくあるミス
        if "Not a shader node tree" in error_msg:
            friendly_msg = "Error: シェーダー用のノードです (GNでは使えません)"
        elif "Not a geometry node tree" in error_msg:
            friendly_msg = "Error: GN用のノードです (シェーダーでは使えません)"
        elif "Cannot add node of type" in error_msg and "Not a" in error_msg:
            friendly_msg = "Error: ノードの種類とエディターが一致しません"
        elif "incorrect context" in error_msg.lower():
            friendly_msg = "Error: 適切なエディターを開いてください"
            
        # その他の構文エラーや実行エラー
        if not friendly_msg:
            # 短縮して表示
            if len(error_msg) > 30:
                friendly_msg = f"Error: {error_msg[:27]}..."
            else:
                friendly_msg = f"Error: {error_msg}"
        
        # HUD でユーザーに通知
        show_hud(friendly_msg)
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

# --- メニュースクレイピング実行オペレーター ---

class PIECREATOR_OT_ScrapeMenu(bpy.types.Operator):
    bl_idname = "wm.pie_creator_scrape_menu"
    bl_label = "Scrape Blender Menu"
    bl_description = "指定したBlenderメニューの内容を解析して抽出します"
    
    target_id: bpy.props.StringProperty(name="Menu ID", description="解析するメニューのidname (例: VIEW3D_MT_mesh_add)")
    
    def execute(self, context):
        if not self.target_id:
            self.report({'WARNING'}, "Menu ID を入力してください")
            return {'CANCELLED'}
            
        # prop_searchのハック用： "VIEW3D_MT_mesh_add  | Mesh" のような文字列からID部分だけを抽出
        clean_target_id = self.target_id.split("  |")[0].strip()
            
        if not hasattr(bpy.types, clean_target_id):
            self.report({'ERROR'}, f"メニュー '{clean_target_id}' が見つかりません。正確なIDを入力してください")
            return {'CANCELLED'}
            
        menu_cls = getattr(bpy.types, clean_target_id)
        mock = MockLayout(verbose=True)
        
        print(f"\n--- PieCreator: Scraping Start [{clean_target_id}] ---")
        success = False
        
        # --- モックコンテキストの構築 (ノードエディタ等での実行時エラー回避) ---
        class MockSpaceData:
            def __init__(self, real_sd): self.real = real_sd
            def __getattr__(self, name):
                if name == 'tree_type': return 'ShaderNodeTree'  # ノードメニュー判定用ダミー
                if name == 'edit_tree': return None
                return getattr(self.real, name, None)
                
        class MockContext:
            def __init__(self, real_ctx): self.real = real_ctx
            def __getattr__(self, name):
                if name == 'space_data': return MockSpaceData(getattr(self.real, 'space_data', None))
                return getattr(self.real, name, None)
                
        mock_context = MockContext(context)

        # --- ダックタイピング用: self.layout 等を要求する draw 関数のための偽装インスタンス ---
        class DummySelf:
            def __init__(self, layout):
                self.layout = layout
            def __getattr__(self, name):
                # NodeAddMenu 等の独自メソッド (self.node_operator) に対応
                if name == 'node_operator':
                    def _node_op(layout, type, text="", icon='NONE', **kwargs):
                        label = text if text else type.replace('ShaderNode', '').replace('CompositorNode', '')
                        op = layout.operator("node.add_node", text=label, icon=icon)
                        op.type = type
                        return op
                    return _node_op
                # 未知のメソッド呼び出しには、何もしない関数を返す
                return lambda *args, **kwargs: None
        
        dummy_self = DummySelf(mock)
        
        # 1. 最も一般的な draw(self, context) への呼び出し
        try:
            print("  [Step 1] Attempting draw(dummy_self, mock_context)...")
            menu_cls.draw(dummy_self, mock_context)
            success = True
        except Exception as e:
            print(f"  [Step 1 Info] Failed: {e}")
            
            # 2. まれにある self を使わず、直接引数で layout を受け取る形式
            try:
                print("  [Step 2] Attempting draw(mock, mock_context)...")
                menu_cls.draw(mock, mock_context)
                success = True
            except Exception as e2:
                print(f"  [Step 2 Info] Failed: {e2}")
                
                # 3. 最終手段: 引数なしなど
                try:
                    print("  [Step 3] Attempting draw(mock) without context...")
                    menu_cls.draw(mock)
                    success = True
                except Exception as e3:
                    import traceback
                    print("  [Scraper Error] All steps failed. Detailed Traceback:")
                    traceback.print_exc()
                    self.report({'ERROR'}, f"解析に失敗しました。詳細はシステムコンソールを確認してください。")
                    return {'CANCELLED'}
        
        if success:
            print(f"--- PieCreator: Scraping Finished. Found {len(mock.results)} items. ---\n")
        
        wm = context.window_manager
        wm.pie_creator_scraped_items.clear()
        
        for item in mock.results:
            si = wm.pie_creator_scraped_items.add()
            si.item_type = item["type"]
            si.idname = item["idname"]
            si.label = item["label"] if item["label"] else item["idname"]
            si.icon = item["icon"]
            if "properties" in item:
                si.props_json = json.dumps(item["properties"])
        
        wm.pie_creator_is_scraping = True
        self.report({'INFO'}, f"{len(mock.results)} 項目を抽出しました")
        return {'FINISHED'}

class PIECREATOR_OT_CommitImport(bpy.types.Operator):
    bl_idname = "wm.pie_creator_commit_import"
    bl_label = "Import Selected Items"
    bl_description = "選択した項目を指定のメニューに追加します"
    
    target_menu_id: bpy.props.StringProperty(name="Destination Menu")
    
    def execute(self, context):
        wm = context.window_manager
        selected_items = [i for i in wm.pie_creator_scraped_items if i.selected]
        
        if not selected_items:
            self.report({'WARNING'}, "項目が選択されていません")
            return {'CANCELLED'}
            
        menus_data = load_menus()
        target_menu = next((m for m in menus_data if m["id"] == self.target_menu_id), None)
        
        if not target_menu:
            self.report({'ERROR'}, "宛先メニューが見つかりません")
            return {'CANCELLED'}
            
        added_count = 0
        for si in selected_items:
            new_item = {
                "label": si.label,
                "icon": si.icon,
                "type": "COMMAND" if si.item_type == 'COMMAND' else "MENU"
            }
            
            if si.item_type == 'COMMAND':
                props = json.loads(si.props_json) if si.props_json else {}
                p_list = []
                for k, v in props.items():
                    if isinstance(v, str): p_list.append(f"{k}='{v}'")
                    else: p_list.append(f"{k}={repr(v)}")
                p_str = ", ".join(p_list)
                
                idname = si.idname
                if "_OT_" in idname:
                    cat, name = idname.split("_OT_")
                    cmd = f"bpy.ops.{cat.lower()}.{name}({p_str})"
                else:
                    cmd = f"bpy.ops.{idname}({p_str})"
                new_item["command"] = cmd
            else:
                new_item["menu_id"] = si.idname
                
            target_menu["items"].append(new_item)
            added_count += 1
            
        save_menus(menus_data)
        bpy.ops.wm.pie_creator_reload()
        
        wm.pie_creator_is_scraping = False
        wm.pie_creator_scraped_items.clear()
        
        self.report({'INFO'}, f"{added_count} 項目を '{target_menu['name']}' に追加しました")
        return {'FINISHED'}

class PIECREATOR_OT_CancelImport(bpy.types.Operator):
    bl_idname = "wm.pie_creator_cancel_import"
    bl_label = "Cancel"
    def execute(self, context):
        wm = context.window_manager
        wm.pie_creator_is_scraping = False
        wm.pie_creator_scraped_items.clear()
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
            
            items = menu_data.get("items", [])
            item_count = len(items)
            
            if item_count > 12:
                # 12項目を超えたら多段化。24個までは2列、それ以上は3列。
                cols = 2 if item_count <= 24 else 3
                grid = layout.grid_flow(columns=cols, even_columns=True, even_rows=False, align=True)
                draw_menu_items(grid, items, context)
            else:
                draw_menu_items(layout, items, context)
            
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

class PIECREATOR_OT_GenerateMenuHandbook(bpy.types.Operator):
    """Blenderのメニュー階層をスキャンして、検索・コピー可能なHTMLハンドブックを作成・表示します"""
    bl_idname = "wm.pie_creator_generate_handbook"
    bl_label = "Generate Menu Handbook"
    bl_description = "Blenderの全メニュー階層を解析し、ブラウザで検索可能なHTMLハンドブックを開きます"

    def execute(self, context):
        import os
        import json
        import webbrowser
        
        self.report({'INFO'}, "Blender内の全メニュー(数百件)をフルスキャン中... (5〜10秒ほどかかります)")
        
        # 1. 全メニューのリストアップ
        all_menu_ids = []
        for attr in dir(bpy.types):
            cls = getattr(bpy.types, attr)
            if isinstance(cls, type) and issubclass(cls, bpy.types.Menu):
                all_menu_ids.append(attr)
        
        hierarchy = {}
        processed_ids = set()
        
        # 簡易的なラベル取得
        def get_menu_label(cls):
            label = getattr(cls, "bl_label", "")
            if not label: label = getattr(cls, "bl_idname", "")
            return label

        # 全件の基本情報をまず作成
        for mid in all_menu_ids:
            cls = getattr(bpy.types, mid)
            hierarchy[mid] = {
                "idname": mid,
                "label": get_menu_label(cls),
                "items": [],
                "is_orphan": True  # 最初はすべて「はぐれ」扱い
            }

        def scan_menu(menu_id, depth=0, max_depth=4):
            if depth > max_depth or menu_id in processed_ids: return
            processed_ids.add(menu_id)
            
            cls = getattr(bpy.types, menu_id, None)
            if not cls or not hasattr(cls, "draw"): return
            
            mock = MockLayout(verbose=False)
            try:
                class Dummy: pass
                dummy_self = Dummy()
                dummy_self.layout = mock
                cls.draw(dummy_self, context)
            except:
                return
            
            items = []
            for item in mock.results:
                if item["type"] == "MENU":
                    sub_id = item["idname"]
                    # 子として見つかったら「はぐれ」フラグを折る
                    if sub_id in hierarchy:
                        hierarchy[sub_id]["is_orphan"] = False
                    
                    # 再帰スキャン
                    scan_menu(sub_id, depth + 1)
                    
                    items.append({
                        "type": "MENU",
                        "label": item["label"],
                        "idname": sub_id
                    })
                else:
                    items.append(item)
            
            if menu_id in hierarchy:
                hierarchy[menu_id]["items"] = items

        # 主要なルートメニューから構造を解析
        root_menus = ["VIEW3D_MT_editor_menus", "NODE_MT_editor_menus", "IMAGE_MT_editor_menus", "TOPBAR_MT_editor_menus"]
        for root in root_menus:
            if root in hierarchy:
                hierarchy[root]["is_orphan"] = False
                scan_menu(root)
            
        # 2. HTMLの生成
        html_template = """
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <title>PieCreator Full Menu Handbook V9</title>
    <style>
        :root { --bg: #111; --card: #222; --text: #eee; --accent: #00aaff; --border: #333; --tag-orphan: #ff8800; --tag-tree: #00cc66; }
        body { background: var(--bg); color: var(--text); font-family: 'Segoe UI', sans-serif; margin: 0; padding: 0; display: flex; flex-direction: column; height: 100vh; }
        .header { background: #1a1a1a; padding: 20px; border-bottom: 2px solid var(--accent); }
        h1 { margin: 0 0 15px 0; font-size: 1.5em; color: var(--accent); display: flex; align-items: center; justify-content: space-between; }
        .stats { font-size: 0.4em; background: #333; color: #aaa; padding: 4px 10px; border-radius: 20px; }
        .search-container { position: relative; }
        #search { width: 100%; padding: 15px; background: #000; border: 1px solid var(--border); color: #fff; border-radius: 8px; font-size: 1.1em; outline: none; }
        #search:focus { border-color: var(--accent); box-shadow: 0 0 10px rgba(0,170,255,0.3); }
        
        .main-content { flex-grow: 1; overflow-y: auto; padding: 20px; display: grid; grid-template-columns: repeat(auto-fill, minmax(400px, 1fr)); gap: 15px; }
        
        .menu-card { background: var(--card); border: 1px solid var(--border); border-radius: 8px; transition: 0.2s; display: flex; flex-direction: column; }
        .menu-card:hover { border-color: #555; transform: translateY(-2px); box-shadow: 0 5px 15px rgba(0,0,0,0.5); }
        
        .card-header { padding: 12px; border-bottom: 1px solid var(--border); display: flex; align-items: flex-start; justify-content: space-between; cursor: pointer; }
        .card-title-area { flex-grow: 1; }
        .label { font-weight: bold; font-size: 1.1em; margin-bottom: 4px; display: block; }
        .idname { font-family: monospace; font-size: 0.85em; color: #888; }
        
        .tag { font-size: 0.7em; padding: 2px 8px; border-radius: 4px; text-transform: uppercase; margin-left: 10px; flex-shrink: 0; }
        .tag.orphan { background: rgba(255,136,0,0.1); color: var(--tag-orphan); border: 1px solid var(--tag-orphan); }
        .tag.tree { background: rgba(0,204,102,0.1); color: var(--tag-tree); border: 1px solid var(--tag-tree); }
        
        .card-body { padding: 10px; font-size: 0.9em; max-height: 300px; overflow-y: auto; background: #181818; }
        .hidden { display: none; }
        
        .item-row { display: flex; align-items: center; padding: 6px; border-bottom: 1px solid #2a2a2a; gap: 10px; }
        .item-row:last-child { border-bottom: none; }
        .i-type { font-size: 0.7em; width: 60px; color: #666; font-weight: bold; }
        .i-label { flex-grow: 1; }
        .i-id { font-size: 0.8em; color: #555; font-family: monospace; }
        
        .copy-btn { background: #333; border: 1px solid #444; color: #ccc; padding: 5px 12px; border-radius: 4px; cursor: pointer; font-size: 0.8em; }
        .copy-btn:hover { background: var(--accent); color: white; border-color: var(--accent); }
        
        ::-webkit-scrollbar { width: 8px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: #333; border-radius: 4px; }
        ::-webkit-scrollbar-thumb:hover { background: #444; }
    </style>
</head>
<body>
    <div class="header">
        <h1>
            PieCreator Full Handbook V9
            <span class="stats" id="stats">Scanning...</span>
        </h1>
        <div class="search-container">
            <input type="text" id="search" placeholder="Search ID or Name (multiple words supported)..." autofocus>
        </div>
    </div>
    <div class="main-content" id="content"></div>

    <style id="dynamic-styles"></style>
    <!-- Auto-loaded Catalog from Blender (Bypassing CORS for file://) -->
    <script src="blender_catalog.js"></script>
    <script>
        const menuData = __DATA_JSON__;
        const container = document.getElementById('content');
        const searchInput = document.getElementById('search');
        
        document.getElementById('stats').innerText = `Total: ${Object.keys(menuData).length} Menus`;

        // 検索用にカードの参照を保持
        const cards = [];

        function initRender() {
            const fragment = document.createDocumentFragment();
            Object.values(menuData).forEach(menu => {
                const card = document.createElement('div');
                card.className = 'menu-card';
                
                const tagClass = menu.is_orphan ? 'orphan' : 'tree';
                const tagText = menu.is_orphan ? 'Orphan / Internal' : 'UI Tree';
                
                // 検索用テキストをデータ属性に持たせる
                const searchText = (menu.label + ' ' + menu.idname + ' ' + JSON.stringify(menu.items)).toLowerCase();
                card.dataset.search = searchText;

                card.innerHTML = `
                    <div class="card-header">
                        <div class="card-title-area">
                            <span class="label">${menu.label}</span>
                            <span class="idname">${menu.idname}</span>
                        </div>
                        <span class="tag ${tagClass}">${tagText}</span>
                    </div>
                    <div class="card-body hidden">
                        ${menu.items.length === 0 ? '<div style="color:#555; padding:10px">No items or submenus</div>' : ''}
                        ${menu.items.map(item => `
                            <div class="item-row">
                                <span class="i-type">${item.type}</span>
                                <span class="i-label">${item.label || ''}</span>
                                <span class="i-id">${item.idname || ''}</span>
                            </div>
                        `).join('')}
                    </div>
                    <div style="padding: 10px; border-top: 1px solid #2a2a2a; display:flex; justify-content:flex-end;">
                        <button class="copy-btn" onclick="copyId('${menu.idname}', this)">Copy ID</button>
                    </div>
                `;
                
                card.querySelector('.card-header').onclick = () => {
                    card.querySelector('.card-body').classList.toggle('hidden');
                };
                
                cards.push(card);
                fragment.appendChild(card);
            });
            container.appendChild(fragment);
        }

        window.copyId = (id, btn) => {
            navigator.clipboard.writeText(id);
            const original = btn.innerText;
            btn.innerText = 'Copied!';
            btn.style.borderColor = '#00aaff';
            setTimeout(() => { btn.innerText = original; btn.style.borderColor = ''; }, 1000);
        };

        let searchTimeout;
        searchInput.addEventListener('input', (e) => {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => {
                const query = e.target.value.toLowerCase();
                const terms = query.split(/\s+/).filter(t => t.length > 0);
                
                let visibleCount = 0;
                cards.forEach(card => {
                    if (terms.length === 0) {
                        card.classList.remove('hidden');
                        visibleCount++;
                    } else {
                        const content = card.dataset.search;
                        const match = terms.every(term => content.includes(term));
                        if (match) {
                            card.classList.remove('hidden');
                            visibleCount++;
                        } else {
                            card.classList.add('hidden');
                        }
                    }
                });
                document.getElementById('stats').innerText = `Total: ${Object.keys(menuData).length} Menus (Found: ${visibleCount})`;
            }, 100); // 100ms待機
        });

        initRender();
    </script>
</body>
</html>
"""
        json_data = json.dumps(hierarchy, ensure_ascii=False)
        full_html = html_template.replace("__DATA_JSON__", json_data)
        
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        filepath = os.path.join(desktop, "blender_full_handbook_v9.html")
        
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(full_html)
            webbrowser.open(f"file:///{filepath}")
            self.report({'INFO'}, f"全件ハンドブックを生成しました({len(all_menu_ids)}件): {filepath}")
        except Exception as e:
            self.report({'ERROR'}, f"ファイル保存に失敗しました: {e}")
            
        return {'FINISHED'}

# --- Designer & Catalog Logic ---

class PIECREATOR_OT_OpenDesigner(bpy.types.Operator):
    """Scan Blender API and Open Web Designer"""
    bl_idname = "wm.pie_creator_open_designer"
    bl_label = "Open PieDesigner"
    bl_options = {'REGISTER'}

    def execute(self, context):
        self.report({'INFO'}, "Scanning Blender API & Icons...")
        
        # 1. Scan logic
        catalog = {
            "modules": {},
            "icons": []
        }
        
        # Scan Icons
        icon_enum = bpy.types.UILayout.bl_rna.functions["prop"].parameters["icon"].enum_items
        catalog["icons"] = sorted([i.identifier for i in icon_enum if i.identifier != 'NONE'])
        
        # Scan Operators
        for attr in dir(bpy.ops):
            module = getattr(bpy.ops, attr)
            if str(type(module)) != "<class 'module'>":
                continue
            module_ops = []
            for op_name in dir(module):
                if op_name.startswith("_"): continue
                try:
                    op = getattr(module, op_name)
                    rna = op.get_rna_type()
                    module_ops.append({
                        "id": f"{attr}.{op_name}",
                        "name": rna.name or op_name,
                        "desc": rna.description or ""
                    })
                except:
                    continue
            if module_ops:
                catalog["modules"][attr] = module_ops

        # 2. Save to addon directory as .js (to bypass file:// protocol restrictions)
        addon_dir = os.path.dirname(__file__)
        catalog_path = os.path.join(addon_dir, "blender_catalog.js")
        try:
            with open(catalog_path, 'w', encoding='utf-8') as f:
                f.write("var BLENDER_CATALOG = ") # JS変数として定義
                json.dump(catalog, f, indent=2, ensure_ascii=False)
                f.write(";")
            self.report({'INFO'}, f"Catalog updated: {catalog_path}")
        except Exception as e:
            self.report({'ERROR'}, f"Failed to save catalog: {e}")
            return {'CANCELLED'}

        # 3. Open HTML
        html_path = os.path.join(addon_dir, "pie_designer_prototype.html")
        if os.path.exists(html_path):
            url = "file://" + html_path.replace("\\", "/")
            webbrowser.open(url)
            self.report({'INFO'}, "Designer opened in browser.")
        else:
            self.report({'ERROR'}, f"Designer HTML not found in: {addon_dir}")
            return {'CANCELLED'}

        return {'FINISHED'}

        return {'FINISHED'}

class PIECREATOR_OT_PasteDesignerData(bpy.types.Operator):
    """Paste data from PieDesigner Clipboard"""
    bl_idname = "wm.pie_creator_paste_designer_data"
    bl_label = "Paste from Designer"
    bl_options = {'REGISTER', 'UNDO'}

    import_mode: bpy.props.EnumProperty(
        items=[
            ('APPEND', "Append New", "既存のメニューを残し、新しいものだけ追加します"),
            ('OVERWRITE', "Overwrite All", "現在の設定を全て消去し、コピーした内容で上書きします")
        ],
        name="Import Mode",
        default='APPEND'
    )

    def execute(self, context):
        clipboard = context.window_manager.clipboard
        if not clipboard:
            self.report({'ERROR'}, "Clipboard is empty.")
            return {'CANCELLED'}

        try:
            data = json.loads(clipboard)
        except:
            self.report({'ERROR'}, "Clipboard content is not valid JSON.")
            return {'CANCELLED'}

        if not isinstance(data, dict) or "type" not in data:
            self.report({'ERROR'}, "Unknown format. Please copy from PieDesigner.")
            return {'CANCELLED'}

        from .storage import load_config, save_config, generate_unique_id
        config = load_config()
        existing_menus = config.get("menus", [])
        payload = data.get("payload")

        if data["type"] == "PIE_CREATOR_MENU":
            # --- 単体メニューのアペンド ---
            new_menu = payload
            # IDの重複回避
            new_menu["id"] = generate_unique_id(new_menu["id"], existing_menus)
            existing_menus.append(new_menu)
            self.report({'INFO'}, f"Appended Menu: {new_menu['name']}")

        elif data["type"] == "PIE_CREATOR_PROJECT":
            # --- プロジェクト全体のマージ/上書き ---
            new_menus = payload.get("menus", [])
            if self.import_mode == 'OVERWRITE':
                config["menus"] = new_menus
                self.report({'INFO'}, f"Overwritten with {len(new_menus)} menus.")
            else:
                for nm in new_menus:
                    nm["id"] = generate_unique_id(nm["id"], existing_menus)
                    existing_menus.append(nm)
                self.report({'INFO'}, f"Merged {len(new_menus)} new menus.")

        save_config(config)
        bpy.ops.wm.pie_creator_reload()
        return {'FINISHED'}

class PIECREATOR_OT_PasteDesignerData(bpy.types.Operator):
    """Paste data from PieDesigner Clipboard"""
    bl_idname = "wm.pie_creator_paste_designer_data"
    bl_label = "Paste from Designer"
    bl_options = {'REGISTER', 'UNDO'}

    import_mode: bpy.props.EnumProperty(
        items=[
            ('APPEND', "Append New", "既存のメニューを残し、新しいものだけ追加します"),
            ('OVERWRITE', "Overwrite All", "現在の設定を全て消去し、コピーした内容で上書きします")
        ],
        name="Import Mode",
        default='APPEND'
    )

    def execute(self, context):
        clipboard = context.window_manager.clipboard
        if not clipboard:
            self.report({'ERROR'}, "Clipboard is empty.")
            return {'CANCELLED'}
        try:
            data = json.loads(clipboard)
        except:
            self.report({'ERROR'}, "Clipboard content is not valid JSON.")
            return {'CANCELLED'}
        if not isinstance(data, dict) or "type" not in data:
            self.report({'ERROR'}, "Unknown format. Please copy from PieDesigner.")
            return {'CANCELLED'}

        from .storage import load_config, save_config, generate_unique_id
        config = load_config()
        existing_menus = config.get("menus", [])
        payload = data.get("payload")

        if data["type"] == "PIE_CREATOR_MENU":
            new_menu = payload
            new_menu["id"] = generate_unique_id(new_menu["id"], existing_menus)
            existing_menus.append(new_menu)
            self.report({'INFO'}, f"Appended Menu: {new_menu['name']}")
        elif data["type"] == "PIE_CREATOR_PROJECT":
            new_menus = payload.get("menus", [])
            if self.import_mode == 'OVERWRITE':
                config["menus"] = new_menus
                self.report({'INFO'}, f"Overwritten with {len(new_menus)} menus.")
            else:
                for nm in new_menus:
                    nm["id"] = generate_unique_id(nm["id"], existing_menus)
                    existing_menus.append(nm)
                self.report({'INFO'}, f"Merged {len(new_menus)} new menus.")

        save_config(config)
        bpy.ops.wm.pie_creator_reload()
        return {'FINISHED'}

    def invoke(self, context, event):
        clipboard = context.window_manager.clipboard
        try:
            data = json.loads(clipboard)
            if data.get("type") == "PIE_CREATOR_PROJECT":
                return context.window_manager.invoke_props_dialog(self)
        except: pass
        return self.execute(context)

class PIECREATOR_OT_CopyDesignerData(bpy.types.Operator):
    """Copy current config to clipboard for PieDesigner"""
    bl_idname = "wm.pie_creator_copy_designer_data"
    bl_label = "Copy for Designer"
    bl_options = {'REGISTER'}

    def execute(self, context):
        from .storage import load_config
        config = load_config()
        data = {"type": "PIE_CREATOR_PROJECT", "payload": config}
        context.window_manager.clipboard = json.dumps(data, indent=2, ensure_ascii=False)
        self.report({'INFO'}, "Config copied for Designer.")
        return {'FINISHED'}

classes = (
    PIECREATOR_OT_OpenDesigner,
    PIECREATOR_OT_PasteDesignerData,
    PIECREATOR_OT_CopyDesignerData,
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
    PIECREATOR_OT_ScrapeMenu,
    PIECREATOR_OT_CommitImport,
    PIECREATOR_OT_CancelImport,
    PIECREATOR_OT_GenerateMenuHandbook,
)

hud_handles = []

def register():
    try:
        update_blender_menus_list()
    except Exception as e:
        print(f"PieCreator: Menu list update failed: {e}")
        
    for cls in classes:
        # 強制的なクリーンアップ: Blenderのメモリ(bpy.types)から古いクラスを探して解除する
        if hasattr(bpy.types, cls.__name__):
            old_cls = getattr(bpy.types, cls.__name__)
            try:
                bpy.utils.unregister_class(old_cls)
            except:
                pass
            
        try:
            bpy.utils.register_class(cls)
        except Exception as e:
            print(f"PieCreator: Failed to register {cls.__name__}: {e}")
    
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
