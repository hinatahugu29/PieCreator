# SPDX-License-Identifier: GPL-3.0-or-later
import bpy
import mathutils
import blf
from ..storage import (
    load_config, save_config, load_menus, sanitize_command, ensure_exec_context,
    format_arg,
)
from ..log import log_debug, log_error, log_error_once, clear_error_once, ADDON_ID

# --- HUD (通知) 表示用 ---
hud_notifications = [] # (text, timestamp, x, y)
last_mouse_pos = (400, 400)

def show_hud(text, x=None, y=None):
    import time
    global hud_notifications, last_mouse_pos
    if x is None or y is None:
        x, y = last_mouse_pos
    hud_notifications.append((text, time.time(), x, y))

def update_mouse_pos(event):
    global last_mouse_pos
    last_mouse_pos = (event.mouse_region_x, event.mouse_region_y)

def draw_hud_callback(space_name):
    import time
    from ..compat import safe_draw_text
    global hud_notifications
    if not hud_notifications: return
    
    font_id = 0
    now = time.time()
    alive = []
    
    try:
        for i, (text, ts, x, y) in enumerate(hud_notifications):
            dt = now - ts
            if dt > 2.0: continue
            
            alpha = 1.0 if dt < 1.0 else 1.0 - (dt - 1.0)
            offset_y = i * 25
            safe_draw_text(font_id, text, x + 20, y + 20 + offset_y, size=20, color=(1.0, 0.8, 0.2, alpha))
            alive.append((text, ts, x, y))
        
        hud_notifications = alive
        clear_error_once("hud_callback")
    except Exception as e:
        # 描画ハンドラなので毎フレーム通る。同じ失敗は一度だけ報告する。
        log_error_once("hud_callback", "HUD の描画に失敗した", e)

# --- 実行系ヘルパー ---

def auto_invoke_enabled():
    """自動 INVOKE の安全弁。プリファレンスが読めない場面では ON とみなす。"""
    try:
        addon = bpy.context.preferences.addons.get(ADDON_ID)
        if addon and addon.preferences:
            return bool(getattr(addon.preferences, "auto_invoke_context", True))
    except Exception:
        pass
    return True


def execute_pie_command(command, label="Command"):
    """コマンド文字列を実行し、(成功したか, エラー文) を返す。

    エラー文を返すのは、呼び出し側が self.report で画面に出せるようにするため。
    以前はここで print するだけだったので、失敗はシステムコンソールにしか
    現れず、利用者からは「押しても何も起きない」としか見えなかった。
    実行コンテキストの取り違えも poll の失敗も同じ無反応に見えるため、
    切り分けができない状態だった。
    """
    if not command:
        return False, "Empty command"

    cmd = sanitize_command(command)
    if auto_invoke_enabled():
        # 取り込み済みの古い項目を救済するため、実行時にも補う。取り込み側
        # (get_op_command) ですでに付いていれば、ここでは何もしない。
        cmd = ensure_exec_context(cmd)

    try:
        global_dict = {"bpy": bpy, "context": bpy.context, "mathutils": mathutils}
        exec(cmd, global_dict)
        return True, ""
    except Exception as e:
        message = f"{label}: {type(e).__name__}: {e}"
        log_error(f"コマンドの実行に失敗した\n  command: {cmd}\n  {message}")
        return False, message

def get_op_command(op):
    if not op: return ""
    idname = getattr(op, "bl_idname", None)
    if not idname and hasattr(op, "bl_rna"): idname = op.bl_rna.identifier
    if not idname: return ""
    try:
        if "_OT_" in idname:
            parts = idname.split("_OT_")
            cmd_base = f"bpy.ops.{parts[0].lower()}.{parts[1]}" if len(parts)==2 else f"bpy.ops.{idname.lower()}"
        else: cmd_base = f"bpy.ops.{idname}"
        
        p_list = []
        props_source = op.properties if hasattr(op, "properties") else (op.p if hasattr(op, "p") else None)
        rna_source = op.bl_rna if hasattr(op, "bl_rna") else (op.rna_type if hasattr(op, "rna_type") else None)
        
        if rna_source:
            for p_id in rna_source.properties.keys():
                if p_id == 'rna_type': continue
                prop = rna_source.properties[p_id]
                if prop.is_readonly: continue
                is_set = op.is_property_set(p_id) if hasattr(op, "is_property_set") else False
                val = getattr(props_source, p_id) if props_source else getattr(op, p_id, None)
                if val is None or (not is_set and p_id != "type"): continue
                
                # 文字列は必ず repr を通す。手で引用符を付けると、値に
                # アポストロフィが入ったとき（"Bob's Cube" のような
                # オブジェクト名は普通に存在する）壊れた Python になる。
                if isinstance(val, (mathutils.Vector, mathutils.Euler, mathutils.Color, mathutils.Quaternion)):
                    p_list.append(f"{p_id}={list(val[:])}")
                elif isinstance(val, set):
                    items_str = ", ".join(repr(v) for v in sorted(val))
                    p_list.append(f"{p_id}={{ {items_str} }}")
                else:
                    p_list.append(format_arg(p_id, val))
        command = f"{cmd_base}({', '.join(p_list)})"
        # ボタンを押したときと同じ挙動になるよう、取り込んだ時点で実行
        # コンテキストを書き込む。項目エディタにもそのまま表示されるので、
        # 利用者が 'EXEC_DEFAULT' に書き換えて上書きできる。
        if auto_invoke_enabled():
            command = ensure_exec_context(command)
        return command
    except Exception as e:
        log_error("オペレーターからコマンド文字列を組み立てられなかった", e)
        return ""

def get_op_label(op):
    if not op: return "未知の物"
    
    # 1. 属性から直接取得を試みる
    idname = getattr(op, "bl_idname", None)
    if not idname and hasattr(op, "bl_rna"):
        idname = op.bl_rna.identifier
        
    label = getattr(op, "bl_label", None)
    if not label: label = getattr(op, "name", None)
    if not label and hasattr(op, "bl_rna"):
        # RNAのnameが単なるID（例: MESH_OT_...）でない場合のみ採用
        rna_name = op.bl_rna.name
        if rna_name and not rna_name.endswith("_OT_"):
            label = rna_name
    
    try:
        # 2. ノード追加オペレーターの特別対応
        if idname and "add_node" in idname.lower():
            node_type = getattr(op, "type", getattr(getattr(op, "properties", None), "type", None))
            if node_type and hasattr(bpy.types, node_type):
                return f"Add {getattr(bpy.types, node_type).bl_rna.name}"
        
        # 3. RNAからの詳細な名前取得を試みる
        if idname:
            # ID形式 (mesh.primitive_cube_add) または クラス形式 (MESH_OT_cube_add)
            parts = idname.split(".") if "." in idname else idname.split("_OT_")
            if len(parts) >= 2:
                cat = parts[0].lower()
                name = parts[-1]
                if hasattr(bpy.ops, cat):
                    op_cat = getattr(bpy.ops, cat)
                    if hasattr(op_cat, name):
                        op_rna = getattr(op_cat, name).get_rna_type()
                        if op_rna and op_rna.name: return op_rna.name
            
        # 4. ラベルが見つかっていればそれを使う
        if label: return label
        
        # 5. 最終手段として ID 名をそのまま使う
        if idname: return idname
    except Exception as e:
        log_debug(f"ラベルの解決に失敗した (idname={idname}): {type(e).__name__}: {e}")

    return label if label else "未知の物"

def get_prop_info(context):
    if not hasattr(context, "button_prop") or not context.button_prop: return None, None, None
    prop = context.button_prop
    ptr = context.button_pointer
    try:
        if ptr.id_data:
            id_name = ptr.id_data.name
            id_type_rna = ptr.id_data.rna_type.identifier
            obj = context.active_object
            base = None
            if ptr.id_data == context.scene: base = "bpy.context.scene"
            elif obj and ptr.id_data == obj: base = "bpy.context.active_object"
            elif obj and obj.active_material and ptr.id_data == obj.active_material: base = "bpy.context.active_object.active_material"
            
            if not base:
                if id_type_rna.endswith("NodeTree"):
                    if hasattr(context.scene, "node_tree") and context.scene.node_tree and ptr.id_data == context.scene.node_tree:
                        base = "bpy.context.scene.node_tree"
                    elif getattr(context.scene, "world", None) and getattr(context.scene.world, "node_tree", None) and ptr.id_data == context.scene.world.node_tree:
                        base = "bpy.context.scene.world.node_tree"
                    elif obj and getattr(obj, "active_material", None) and getattr(obj.active_material, "node_tree", None) and ptr.id_data == obj.active_material.node_tree:
                        base = "bpy.context.active_object.active_material.node_tree"
                    else:
                        if obj and hasattr(obj, "modifiers"):
                            for mod in obj.modifiers:
                                if mod.type == 'NODES' and getattr(mod, "node_group", None) == ptr.id_data:
                                    base = f"bpy.context.active_object.modifiers['{mod.name}'].node_group"
                                    break
                        if not base:
                            base = f"bpy.data.node_groups[{id_name!r}]"
                else:
                    cat = id_type_rna.lower() + "s"
                    base = f"bpy.data.{cat}[{id_name!r}]"
            
            path = ptr.path_from_id()
            full_path = f"{base}.{path}" if path else base
            return full_path, prop.identifier, prop.name
    except Exception as e:
        log_error("プロパティのデータパスを解決できなかった", e)
    return None, None, None

def get_label_from_command(command):
    if not command: return ""
    if "bpy.ops." in command:
        try:
            # 引数部分を除去
            base = command.split("(")[0].strip()
            op_path = base.replace("bpy.ops.", "")
            parts = op_path.split(".")
            if len(parts) >= 2:
                cat = parts[0]
                name = parts[-1]
                if hasattr(bpy.ops, cat):
                    op_cat = getattr(bpy.ops, cat)
                    if hasattr(op_cat, name):
                        op_rna = getattr(op_cat, name).get_rna_type()
                        if op_rna and op_rna.name: return op_rna.name
                # RNAがダメなら名前を整形 (primitive_cube_add -> Primitive Cube Add)
                return name.replace("_", " ").title()
        except Exception as e:
            log_debug(f"コマンド文字列からラベルを引けなかった ({command}): {type(e).__name__}: {e}")
    return "未知の物"

# --- 実行オペレーター ---

class PIECREATOR_OT_Exec(bpy.types.Operator):
    """Run the command stored in this menu item"""
    bl_idname = "wm.pie_creator_exec"
    bl_label = "Execute Command"
    command: bpy.props.StringProperty()

    def _run(self, label):
        ok, message = execute_pie_command(self.command, label=label)
        if not ok:
            self.report({'ERROR'}, message)
            return {'CANCELLED'}
        return {'FINISHED'}

    def invoke(self, context, event):
        update_mouse_pos(event)
        return self._run("Exec")

    def execute(self, context):
        return self._run("Exec")

class PIECREATOR_OT_CallMenu(bpy.types.Operator):
    """Open the PieCreator menu with this identifier"""
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
        context.window_manager.pie_creator_active_pie_id = self.menu_id
        m_type = menu_data.get("type", "PIE") if menu_data else "PIE"
        
        if m_type == "PIE": bpy.ops.wm.call_menu_pie(name=menu_idname)
        elif m_type == "POPUP": bpy.ops.wm.pie_creator_popup('INVOKE_DEFAULT', menu_id=self.menu_id, use_dialog=False)
        elif m_type == "DIALOG": bpy.ops.wm.pie_creator_popup('INVOKE_DEFAULT', menu_id=self.menu_id, use_dialog=True)
        elif m_type == "STACK": bpy.ops.wm.pie_creator_stack('INVOKE_DEFAULT', menu_id=self.menu_id)
        elif m_type == "STICKY": bpy.ops.wm.pie_creator_sticky('INVOKE_DEFAULT', menu_id=self.menu_id)
        else: bpy.ops.wm.call_menu(name=menu_idname)
        return {'FINISHED'}

stack_indices = {}
class PIECREATOR_OT_CallStack(bpy.types.Operator):
    """Run the next command in this stack menu, cycling through its items on each press"""
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
            ok, message = execute_pie_command(item.get("command", ""), label=f"Stack: {item.get('label')}")
            if not ok:
                self.report({'ERROR'}, message)
            show_hud(f"Stack: {item.get('label', 'Action')}")
        stack_indices[self.menu_id] = (idx + 1) % len(items)
        return {'FINISHED'}

class PIECREATOR_OT_StickyKey(bpy.types.Operator):
    """Run one command while the key is held and another when it is released"""
    bl_idname = "wm.pie_creator_sticky"
    bl_label = "Sticky Key Action"
    bl_options = {'REGISTER', 'UNDO'}
    menu_id: bpy.props.StringProperty()
    key_type: bpy.props.StringProperty()
    def execute_sticky(self, idx, label_prefix):
        menus = load_menus()
        menu = next((m for m in menus if m["id"] == self.menu_id), None)
        if not menu or len(menu.get("items", [])) <= idx: return
        ok, message = execute_pie_command(menu["items"][idx].get("command", ""), label=f"Sticky {label_prefix}")
        if not ok:
            self.report({'ERROR'}, message)
    def modal(self, context, event):
        if event.type == self.key_type and event.value == 'RELEASE':
            self.execute_sticky(1, "Release")
            return {'FINISHED'}
        return {'RUNNING_MODAL'}
    def invoke(self, context, event):
        self.key_type = event.type if event else 'UNKNOWN'
        self.execute_sticky(0, "Press")
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

class PIECREATOR_OT_PopupDialog(bpy.types.Operator):
    """Show this menu as a popup or as a dialog box"""
    bl_idname = "wm.pie_creator_popup"
    bl_label = "PieCreator Dialog"
    bl_options = {'REGISTER', 'UNDO'}
    menu_id: bpy.props.StringProperty()
    use_dialog: bpy.props.BoolProperty(default=True)
    def draw(self, context):
        from ..ui.menus import draw_menu_items
        menus = load_menus()
        menu_data = next((m for m in menus if m["id"] == self.menu_id), None)
        if menu_data:
            layout = self.layout
            draw_menu_items(layout, menu_data.get("items", []), context)
    def execute(self, context): return {'FINISHED'}
    def invoke(self, context, event):
        if self.use_dialog: return context.window_manager.invoke_props_dialog(self)
        return context.window_manager.invoke_popup(self)

class PIECREATOR_OT_ReloadMenus(bpy.types.Operator):
    """Reload the configuration and re-register every menu and shortcut"""
    bl_idname = "wm.pie_creator_reload"
    bl_label = "Reload & Sync"
    def execute(self, context):
        config = load_config(); save_config(config)
        from .. import register_dynamic_menus; register_dynamic_menus()
        return {'FINISHED'}

class PIECREATOR_OT_CallMaster(bpy.types.Operator):
    """Open the menu matching the current mode, falling back to the master menu"""
    bl_idname = "wm.pie_creator_call_master"
    bl_label = "Call Master Menu"
    def execute(self, context):
        config = load_config()
        menus = config.get("menus", [])
        active_deck = config.get("active_deck", "default")
        curr_mode = context.mode

        log_debug(f"CallMaster (Mode: {curr_mode}, Deck: {active_deck}, Menus: {len(menus)})")

        # 1. 現在のモードに最適なメニューを探す
        for m in menus:
            m_id = m.get("id", "unknown")
            m_deck = m.get("deck_id", "default")
            modes = m.get("modes", [])

            if m_deck != active_deck:
                log_debug(f"  skip {m_id}: デッキ不一致 ({m_deck} != {active_deck})")
                continue

            if curr_mode in modes:
                log_debug(f"  match {m_id}: モード {curr_mode}")
                bpy.ops.wm.pie_creator_call(menu_id=m_id)
                return {'FINISHED'}

        # 2. 該当がなければマスターメニュー
        m_id = config.get("master_menu_id")
        if m_id:
            # メニューが存在するか最終確認
            if any(m["id"] == m_id for m in menus):
                log_debug(f"  マスターメニューを使う: {m_id}")
                bpy.ops.wm.pie_creator_call(menu_id=m_id)
            elif menus:
                log_debug(f"  マスターメニュー {m_id} が見つからない。{menus[0]['id']} で代替する")
                bpy.ops.wm.pie_creator_call(menu_id=menus[0]["id"])
            else:
                self.report({'WARNING'}, "呼び出せるメニューがありません")
        else:
            self.report({'WARNING'}, "現在のモードに一致するメニューがなく、マスターメニューも未設定です")
        return {'FINISHED'}

classes = (
    PIECREATOR_OT_Exec,
    PIECREATOR_OT_CallMenu,
    PIECREATOR_OT_CallStack,
    PIECREATOR_OT_StickyKey,
    PIECREATOR_OT_PopupDialog,
    PIECREATOR_OT_ReloadMenus,
    PIECREATOR_OT_CallMaster,
)
