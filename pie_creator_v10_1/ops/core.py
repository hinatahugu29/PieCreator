import bpy
import os
import json
import mathutils
import blf
from ..storage import load_config, save_config, load_menus, save_menus, sanitize_command

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
    global hud_notifications
    if not hud_notifications: return
    
    font_id = 0
    blf.size(font_id, 20)
    blf.enable(font_id, blf.SHADOW)
    blf.shadow(font_id, 3, 0.0, 0.0, 0.0, 1.0)
    blf.shadow_offset(font_id, 2, -2)
    
    now = time.time()
    alive = []
    for i, (text, ts, x, y) in enumerate(hud_notifications):
        dt = now - ts
        if dt > 2.0: continue
        
        alpha = 1.0 if dt < 1.0 else 1.0 - (dt - 1.0)
        blf.color(font_id, 1.0, 0.8, 0.2, alpha)
        
        offset_y = i * 25
        blf.position(font_id, x + 20, y + 20 + offset_y, 0)
        blf.draw(font_id, text)
        alive.append((text, ts, x, y))
    
    hud_notifications = alive

# --- 実行系ヘルパー ---

def execute_pie_command(command, label="Command"):
    if not command: return False
    cmd = sanitize_command(command)
    try:
        global_dict = {"bpy": bpy, "context": bpy.context, "mathutils": mathutils}
        exec(cmd, global_dict)
        return True
    except Exception as e:
        error_msg = str(e)
        show_hud(f"Error: {error_msg[:25]}...")
        return False

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
                
                if isinstance(val, str): p_list.append(f"{p_id}='{val}'")
                elif isinstance(val, bool): p_list.append(f"{p_id}={val}")
                elif isinstance(val, (int, float)): p_list.append(f"{p_id}={val}")
                elif isinstance(val, (mathutils.Vector, mathutils.Euler, mathutils.Color, mathutils.Quaternion)):
                    p_list.append(f"{p_id}={list(val[:])}")
                elif isinstance(val, set):
                    items_str = ", ".join(f"'{v}'" for v in sorted(val))
                    p_list.append(f"{p_id}={{ {items_str} }}")
                else: p_list.append(f"{p_id}={repr(val)}")
        return f"{cmd_base}({', '.join(p_list)})"
    except: return ""

def get_op_label(op):
    if not op: return "Unknown"
    idname = getattr(op, "bl_idname", None)
    try:
        if idname and "add_node" in idname.lower():
            node_type = getattr(op, "type", getattr(getattr(op, "properties", None), "type", None))
            if node_type and hasattr(bpy.types, node_type):
                return f"Add {getattr(bpy.types, node_type).bl_rna.name}"
        if hasattr(op, "name") and op.name: return op.name
        if idname and "_OT_" in idname:
            parts = idname.split("_OT_")
            return getattr(getattr(bpy.ops, parts[0].lower()), parts[1]).get_rna_type().name
    except: pass
    return idname if idname else "Unknown"

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
                cat = id_type_rna.lower() + "s"
                base = f"bpy.data.{cat}['{id_name}']"
            
            path = ptr.path_from_id()
            full_path = f"{base}.{path}" if path else base
            return full_path, prop.identifier, prop.name
    except: pass
    return None, None, None

def get_label_from_command(command):
    if not command: return ""
    if "bpy.ops." in command:
        try:
            op_part = command.split("(")[0].replace("bpy.ops.", "")
            cat, name = op_part.split(".")
            return getattr(getattr(bpy.ops, cat), name).get_rna_type().name
        except: pass
    return "Custom Command"

# --- 実行オペレーター ---

class PIECREATOR_OT_Exec(bpy.types.Operator):
    bl_idname = "wm.pie_creator_exec"
    bl_label = "Execute Command"
    command: bpy.props.StringProperty()
    def invoke(self, context, event):
        update_mouse_pos(event)
        execute_pie_command(self.command, label="Exec")
        return {'FINISHED'}
    def execute(self, context):
        execute_pie_command(self.command, label="Exec")
        return {'FINISHED'}

class PIECREATOR_OT_CallMenu(bpy.types.Operator):
    bl_idname = "wm.pie_creator_call"
    bl_label = "Call Pie Menu"
    menu_id: bpy.props.StringProperty()
    def invoke(self, context, event):
        update_mouse_pos(event)
        return self.execute(context)
    def execute(self, context):
        from ..storage import load_menus
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
        self.key_type = event.type if event else 'UNKNOWN'
        self.execute_sticky(0, "Press")
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

class PIECREATOR_OT_PopupDialog(bpy.types.Operator):
    bl_idname = "wm.pie_creator_popup"
    bl_label = "PieCreator Dialog"
    bl_options = {'REGISTER', 'UNDO'}
    menu_id: bpy.props.StringProperty()
    use_dialog: bpy.props.BoolProperty(default=True)
    def draw(self, context):
        from ..menus import draw_menu_items
        menus = load_menus()
        menu_data = next((m for m in menus if m["id"] == self.menu_id), None)
        if menu_data:
            layout = self.layout
            layout.use_property_split = False
            items = menu_data.get("items", [])
            cols = 2 if 12 < len(items) <= 24 else (3 if len(items) > 24 else 1)
            if cols > 1:
                grid = layout.grid_flow(columns=cols, even_columns=True, even_rows=False, align=True)
                draw_menu_items(grid, items, context)
            else: draw_menu_items(layout, items, context)
    def execute(self, context): return {'FINISHED'}
    def invoke(self, context, event):
        update_mouse_pos(event)
        if self.use_dialog: return context.window_manager.invoke_props_dialog(self)
        return context.window_manager.invoke_popup(self)

class PIECREATOR_OT_ReloadMenus(bpy.types.Operator):
    bl_idname = "wm.pie_creator_reload"
    bl_label = "Reload & Sync"
    def execute(self, context):
        config = load_config(); save_config(config)
        from .. import register_dynamic_menus; register_dynamic_menus()
        return {'FINISHED'}

class PIECREATOR_OT_DuplicateItem(bpy.types.Operator):
    bl_idname = "wm.pie_creator_duplicate_item"
    bl_label = "Duplicate Item"
    menu_id: bpy.props.StringProperty()
    item_index: bpy.props.IntProperty()
    def execute(self, context):
        menus = load_menus()
        menu = next((m for m in menus if m["id"] == self.menu_id), None)
        if not menu or not (0 <= self.item_index < len(menu["items"])): return {'CANCELLED'}
        import copy
        menu["items"].insert(self.item_index + 1, copy.deepcopy(menu["items"][self.item_index]))
        save_menus(menus); bpy.ops.wm.pie_creator_reload()
        return {'FINISHED'}

class PIECREATOR_OT_CopyItem(bpy.types.Operator):
    bl_idname = "wm.pie_creator_copy_item"
    bl_label = "Copy Item"
    menu_id: bpy.props.StringProperty(); item_index: bpy.props.IntProperty()
    def execute(self, context):
        menus = load_menus()
        menu = next((m for m in menus if m["id"] == self.menu_id), None)
        if not menu or not (0 <= self.item_index < len(menu["items"])): return {'CANCELLED'}
        wm = context.window_manager
        wm.pie_creator_item_clipboard = json.dumps(menu["items"][self.item_index])
        wm.pie_creator_clipboard_source_menu = self.menu_id
        wm.pie_creator_clipboard_is_cut = False
        return {'FINISHED'}

class PIECREATOR_OT_PasteItem(bpy.types.Operator):
    bl_idname = "wm.pie_creator_paste_item"
    bl_label = "Paste Item"
    menu_id: bpy.props.StringProperty(); item_index: bpy.props.IntProperty(default=-1)
    def execute(self, context):
        wm = context.window_manager
        if not wm.pie_creator_item_clipboard: return {'CANCELLED'}
        item = json.loads(wm.pie_creator_item_clipboard)
        menus = load_menus()
        target_menu = next((m for m in menus if m["id"] == self.menu_id), None)
        if not target_menu: return {'CANCELLED'}
        if wm.pie_creator_clipboard_is_cut:
            src = next((m for m in menus if m["id"] == wm.pie_creator_clipboard_source_menu), None)
            if src:
                for i, it in enumerate(src["items"]):
                    if json.dumps(it) == wm.pie_creator_item_clipboard: src["items"].pop(i); break
            wm.pie_creator_item_clipboard = ""; wm.pie_creator_clipboard_is_cut = False
        if self.item_index == -1: target_menu["items"].append(item)
        else: target_menu["items"].insert(self.item_index, item)
        save_menus(menus); bpy.ops.wm.pie_creator_reload()
        return {'FINISHED'}

class PIECREATOR_OT_AddToMenu(bpy.types.Operator):
    bl_idname = "wm.pie_creator_add_to_menu"
    bl_label = "Add to Menu"
    menu_id: bpy.props.StringProperty()
    def execute(self, context):
        wm = context.window_manager
        target_op = context.button_operator if hasattr(context, "button_operator") and context.button_operator else (wm.operators[-1] if wm.operators else None)
        if target_op and "pie_creator" in getattr(target_op, "bl_idname", "").lower() and len(wm.operators)>1: target_op = wm.operators[-2]
        if not target_op: return {'CANCELLED'}
        cmd = get_op_command(target_op); label = get_op_label(target_op)
        menus = load_menus()
        menu = next((m for m in menus if m["id"] == self.menu_id), None)
        if menu:
            menu["items"].append({"type": "COMMAND", "label": label, "command": cmd, "icon": 'NONE'})
            save_menus(menus); bpy.ops.wm.pie_creator_reload()
        return {'FINISHED'}

class PIECREATOR_OT_AddBufferedToMenu(bpy.types.Operator):
    bl_idname = "wm.pie_creator_add_buffered_to_menu"
    bl_label = "Add Captured to Menu"
    menu_id: bpy.props.StringProperty()
    def execute(self, context):
        wm = context.window_manager
        menus = load_menus()
        menu = next((m for m in menus if m["id"] == self.menu_id), None)
        if not menu: return {'CANCELLED'}
        
        is_prop = wm.pie_creator_ctx_is_prop
        if is_prop:
            path = wm.pie_creator_ctx_data_path
            prop = wm.pie_creator_ctx_prop_name
            label = wm.pie_creator_ctx_label
            if path and prop:
                menu["items"].append({
                    "type": "PROPERTY", "label": label, "data_path": path, 
                    "prop_name": prop, "icon": 'NONE', "use_slider": True
                })
        else:
            cmd = wm.pie_creator_ctx_command
            label = wm.pie_creator_ctx_label
            if cmd:
                menu["items"].append({"type": "COMMAND", "label": label, "command": cmd, "icon": 'NONE'})
        
        save_menus(menus); bpy.ops.wm.pie_creator_reload()
        return {'FINISHED'}

class PIECREATOR_OT_Paste(bpy.types.Operator):
    bl_idname = "wm.pie_creator_paste"
    bl_label = "Paste Captured to Menu"
    menu_id: bpy.props.StringProperty()
    def execute(self, context):
        wm = context.window_manager
        if not wm.pie_creator_has_buffer: return {'CANCELLED'}
        menus = load_menus()
        menu = next((m for m in menus if m["id"] == self.menu_id), None)
        if menu:
            cmd = wm.pie_creator_buffer_command
            item = {"label": wm.pie_creator_buffer_label, "icon": wm.pie_creator_buffer_icon or 'NONE'}
            if cmd.startswith("PROP|"):
                parts = cmd.split("|")
                item.update({"type": "PROPERTY", "data_path": parts[1], "prop_name": parts[2], "use_slider": True})
            else:
                item.update({"type": "COMMAND", "command": cmd})
            menu["items"].append(item); save_menus(menus); bpy.ops.wm.pie_creator_reload()
        return {'FINISHED'}

class PIECREATOR_OT_CallMaster(bpy.types.Operator):
    bl_idname = "wm.pie_creator_call_master"
    bl_label = "Call Master Menu"
    def execute(self, context):
        config = load_config()
        m_id = config.get("master_menu_id")
        if m_id: bpy.ops.wm.pie_creator_call(menu_id=m_id)
        else: self.report({'WARNING'}, "No Master Menu set.")
        return {'FINISHED'}

class PIECREATOR_OT_SwitchDeck(bpy.types.Operator):
    bl_idname = "wm.pie_creator_switch_deck"
    bl_label = "Switch Deck"
    deck_id: bpy.props.StringProperty()
    def execute(self, context):
        config = load_config(); config["active_deck"] = self.deck_id
        save_config(config); bpy.ops.wm.pie_creator_reload()
        return {'FINISHED'}

class PIECREATOR_OT_MoveToDeck(bpy.types.Operator):
    bl_idname = "wm.pie_creator_move_to_deck"
    bl_label = "Move Menu to Deck"
    menu_id: bpy.props.StringProperty()
    deck_id: bpy.props.StringProperty()
    def execute(self, context):
        config = load_config()
        menu = next((m for m in config.get("menus", []) if m["id"] == self.menu_id), None)
        if menu: menu["deck_id"] = self.deck_id; save_config(config); bpy.ops.wm.pie_creator_reload()
        return {'FINISHED'}

class PIECREATOR_OT_AddDeck(bpy.types.Operator):
    bl_idname = "wm.pie_creator_add_deck"
    bl_label = "Add New Deck"
    new_name: bpy.props.StringProperty(name="Deck Name", default="New Deck")
    def execute(self, context):
        config = load_config(); decks = config.get("decks", [])
        import uuid; d_id = str(uuid.uuid4())[:8]
        decks.append({"id": d_id, "name": self.new_name})
        save_config(config); return {'FINISHED'}
    def invoke(self, context, event): return context.window_manager.invoke_props_dialog(self)

class PIECREATOR_OT_RemoveDeck(bpy.types.Operator):
    bl_idname = "wm.pie_creator_remove_deck"
    bl_label = "Remove Deck"
    deck_id: bpy.props.StringProperty()
    def execute(self, context):
        config = load_config(); decks = config.get("decks", [])
        if self.deck_id == "default": return {'CANCELLED'}
        config["decks"] = [d for d in decks if d["id"] != self.deck_id]
        if config["active_deck"] == self.deck_id: config["active_deck"] = "default"
        for m in config.get("menus", []):
            if m.get("deck_id") == self.deck_id: m["deck_id"] = "default"
        save_config(config); bpy.ops.wm.pie_creator_reload()
        return {'FINISHED'}

class PIECREATOR_OT_SelectMenu(bpy.types.Operator):
    bl_idname = "wm.pie_creator_select_menu"
    bl_label = "Select Menu"
    menu_id: bpy.props.StringProperty()
    def execute(self, context):
        from ..ui_editor import set_active_menu_id
        set_active_menu_id(context.window_manager, self.menu_id); return {'FINISHED'}

class PIECREATOR_OT_ManageModes(bpy.types.Operator):
    bl_idname = "wm.pie_creator_manage_modes"
    bl_label = "Menu Modes"
    menu_id: bpy.props.StringProperty()
    def execute(self, context): return {'FINISHED'}
    def draw(self, context):
        menus = load_menus(); menu = next((m for m in menus if m["id"] == self.menu_id), None)
        if not menu: return
        layout = self.layout; modes = menu.setdefault("modes", [])
        all_modes = [
            ('OBJECT', "Object"), ('EDIT_MESH', "Edit Mesh"), ('SCULPT', "Sculpt"), 
            ('PAINT_VERTEX', "Vertex Paint"), ('WEIGHT_PAINT', "Weight Paint"), ('TEXTURE_PAINT', "Texture Paint")
        ]
        for m_id, m_name in all_modes:
            row = layout.row(); is_on = m_id in modes
            op = row.operator("wm.pie_creator_toggle_mode", text=m_name, icon='CHECKBOX_HLT' if is_on else 'CHECKBOX_DEHLT')
            op.menu_id = self.menu_id; op.mode = m_id
    def invoke(self, context, event): return context.window_manager.invoke_props_dialog(self)

class PIECREATOR_OT_ToggleMode(bpy.types.Operator):
    bl_idname = "wm.pie_creator_toggle_mode"
    bl_label = "Toggle Mode"
    menu_id: bpy.props.StringProperty(); mode: bpy.props.StringProperty()
    def execute(self, context):
        menus = load_menus(); menu = next((m for m in menus if m["id"] == self.menu_id), None)
        if menu:
            modes = menu.setdefault("modes", [])
            if self.mode in modes: modes.remove(self.mode)
            else: modes.append(self.mode)
            save_menus(menus); bpy.ops.wm.pie_creator_reload()
        return {'FINISHED'}

class PIECREATOR_OT_ManageAreas(bpy.types.Operator):
    bl_idname = "wm.pie_creator_manage_areas"
    bl_label = "Menu Areas"
    menu_id: bpy.props.StringProperty()
    def execute(self, context): return {'FINISHED'}
    def draw(self, context):
        menus = load_menus(); menu = next((m for m in menus if m["id"] == self.menu_id), None)
        if not menu: return
        layout = self.layout; areas = menu.setdefault("areas", [])
        all_areas = [('VIEW_3D', "3D View"), ('NODE_EDITOR', "Node Editor"), ('IMAGE_EDITOR', "Image Editor")]
        for a_id, a_name in all_areas:
            row = layout.row(); is_on = a_id in areas
            op = row.operator("wm.pie_creator_toggle_area", text=a_name, icon='CHECKBOX_HLT' if is_on else 'CHECKBOX_DEHLT')
            op.menu_id = self.menu_id; op.area = a_id
    def invoke(self, context, event): return context.window_manager.invoke_props_dialog(self)

class PIECREATOR_OT_ToggleArea(bpy.types.Operator):
    bl_idname = "wm.pie_creator_toggle_area"
    bl_label = "Toggle Area"
    menu_id: bpy.props.StringProperty(); area: bpy.props.StringProperty()
    def execute(self, context):
        menus = load_menus(); menu = next((m for m in menus if m["id"] == self.menu_id), None)
        if menu:
            areas = menu.setdefault("areas", [])
            if self.area in areas: areas.remove(self.area)
            else: areas.append(self.area)
            save_menus(menus); bpy.ops.wm.pie_creator_reload()
        return {'FINISHED'}

class PIECREATOR_OT_MoveMenu(bpy.types.Operator):
    bl_idname = "wm.pie_creator_move_menu"
    bl_label = "Move Menu"
    menu_id: bpy.props.StringProperty(); direction: bpy.props.EnumProperty(items=[('UP', "Up", ""), ('DOWN', "Down", "")])
    def execute(self, context):
        config = load_config(); menus = config.get("menus", [])
        idx = next((i for i, m in enumerate(menus) if m["id"] == self.menu_id), -1)
        if idx == -1: return {'CANCELLED'}
        new_idx = idx - 1 if self.direction == 'UP' else idx + 1
        if 0 <= new_idx < len(menus):
            menus[idx], menus[new_idx] = menus[new_idx], menus[idx]; save_config(config); bpy.ops.wm.pie_creator_reload()
        return {'FINISHED'}

class PIECREATOR_OT_RemoveMenu(bpy.types.Operator):
    bl_idname = "wm.pie_creator_remove_menu"
    bl_label = "Remove Menu"
    menu_id: bpy.props.StringProperty()
    def execute(self, context):
        config = load_config(); config["menus"] = [m for m in config.get("menus", []) if m["id"] != self.menu_id]
        save_config(config); bpy.ops.wm.pie_creator_reload(); return {'FINISHED'}
    def invoke(self, context, event): return context.window_manager.invoke_confirm(self, event)

class PIECREATOR_OT_AddItem(bpy.types.Operator):
    bl_idname = "wm.pie_creator_add_item"
    bl_label = "Edit Item"
    menu_id: bpy.props.StringProperty(); item_index: bpy.props.IntProperty(default=-1)
    label: bpy.props.StringProperty(name="Label"); command: bpy.props.StringProperty(name="Command")
    icon: bpy.props.StringProperty(name="Icon", default="NONE"); poll: bpy.props.StringProperty(name="Poll (Python Expr)")
    data_path: bpy.props.StringProperty(name="Data Path"); prop_name: bpy.props.StringProperty(name="Prop Name")
    use_slider: bpy.props.BoolProperty(name="Slider", default=True); item_type: bpy.props.EnumProperty(items=[('COMMAND', "Command", ""), ('PROPERTY', "Property", ""), ('MENU', "Submenu", ""), ('SEPARATOR', "Separator", ""), ('SNAP_PANEL', "Snap Panel", "")])
    sub_menu_id: bpy.props.StringProperty(name="Submenu ID")
    def draw(self, context):
        layout = self.layout; layout.prop(self, "item_type")
        if self.item_type == 'SEPARATOR': return
        layout.prop(self, "label"); layout.prop_search(self, "icon", context.window_manager, "pie_creator_icons_search")
        if self.item_type == 'COMMAND': layout.prop(self, "command"); layout.prop(self, "poll")
        elif self.item_type == 'PROPERTY': layout.prop(self, "data_path"); layout.prop(self, "prop_name"); layout.prop(self, "use_slider")
        elif self.item_type == 'MENU': layout.prop_search(self, "sub_menu_id", context.window_manager, "pie_creator_menus_search")
    def execute(self, context):
        menus = load_menus(); menu = next((m for m in menus if m["id"] == self.menu_id), None)
        if not menu: return {'CANCELLED'}
        item = {"type": self.item_type, "label": self.label, "icon": self.icon}
        if self.item_type == 'COMMAND': item.update({"command": self.command, "poll": self.poll})
        elif self.item_type == 'PROPERTY': item.update({"data_path": self.data_path, "prop_name": self.prop_name, "use_slider": self.use_slider})
        elif self.item_type == 'MENU': item["menu_id"] = self.sub_menu_id.split("  |")[0].strip()
        if self.item_index == -1: menu["items"].append(item)
        else: menu["items"][self.item_index] = item
        save_menus(menus); bpy.ops.wm.pie_creator_reload(); return {'FINISHED'}
    def invoke(self, context, event):
        if self.item_index != -1:
            menus = load_menus(); menu = next((m for m in menus if m["id"] == self.menu_id), None)
            if menu and 0 <= self.item_index < len(menu["items"]):
                it = menu["items"][self.item_index]; self.item_type = it.get("type", "COMMAND")
                self.label = it.get("label", ""); self.icon = it.get("icon", "NONE")
                self.command = it.get("command", ""); self.poll = it.get("poll", "")
                self.data_path = it.get("data_path", ""); self.prop_name = it.get("prop_name", "")
                self.use_slider = it.get("use_slider", True); self.sub_menu_id = it.get("menu_id", "")
        return context.window_manager.invoke_props_dialog(self, width=400)

class PIECREATOR_OT_MoveItem(bpy.types.Operator):
    bl_idname = "wm.pie_creator_move_item"
    bl_label = "Move Item"
    menu_id: bpy.props.StringProperty(); item_index: bpy.props.IntProperty(); direction: bpy.props.EnumProperty(items=[('UP', "Up", ""), ('DOWN', "Down", "")])
    def execute(self, context):
        menus = load_menus(); menu = next((m for m in menus if m["id"] == self.menu_id), None)
        idx = self.item_index; new_idx = idx - 1 if self.direction == 'UP' else idx + 1
        if menu and 0 <= new_idx < len(menu["items"]):
            items = menu["items"]; items[idx], items[new_idx] = items[new_idx], items[idx]
            save_menus(menus); bpy.ops.wm.pie_creator_reload()
        return {'FINISHED'}

class PIECREATOR_OT_RemoveItem(bpy.types.Operator):
    bl_idname = "wm.pie_creator_remove_item"
    bl_label = "Remove Item"
    menu_id: bpy.props.StringProperty(); item_index: bpy.props.IntProperty()
    def execute(self, context):
        menus = load_menus(); menu = next((m for m in menus if m["id"] == self.menu_id), None)
        if menu and 0 <= self.item_index < len(menu["items"]):
            menu["items"].pop(self.item_index); save_menus(menus); bpy.ops.wm.pie_creator_reload()
        return {'FINISHED'}

class PIECREATOR_OT_PrepareLink(bpy.types.Operator):
    bl_idname = "wm.pie_creator_prepare_link"
    bl_label = "Prepare Link"
    menu_id: bpy.props.StringProperty()
    def execute(self, context):
        context.window_manager.pie_creator_linking_child_id = self.menu_id
        show_hud(f"Linking ready: {self.menu_id}. Select 'Paste Link' in target menu.")
        return {'FINISHED'}

class PIECREATOR_OT_CreateLinkSubmenu(bpy.types.Operator):
    bl_idname = "wm.pie_creator_create_link_submenu"
    bl_label = "Create & Link Submenu"
    menu_id: bpy.props.StringProperty(); item_index: bpy.props.IntProperty()
    def execute(self, context):
        config = load_config(); menus = config.get("menus", []); d_id = config.get("active_deck", "default")
        from ..storage import generate_unique_id; new_id = generate_unique_id("submenu", menus)
        menus.append({"id": new_id, "name": "New Submenu", "type": "MENU", "deck_id": d_id, "items": []})
        parent = next((m for m in menus if m["id"] == self.menu_id), None)
        if parent: parent["items"][self.item_index].update({"type": "MENU", "menu_id": new_id})
        save_config(config); bpy.ops.wm.pie_creator_reload(); return {'FINISHED'}

class PIECREATOR_OT_UnlinkFromParent(bpy.types.Operator):
    bl_idname = "wm.pie_creator_unlink_from_parent"
    bl_label = "Unlink from Parents"
    menu_id: bpy.props.StringProperty()
    def execute(self, context):
        menus = load_menus()
        for m in menus:
            for item in m.get("items", []):
                if item.get("type") == "MENU" and item.get("menu_id") == self.menu_id: item["menu_id"] = ""
        save_menus(menus); bpy.ops.wm.pie_creator_reload(); return {'FINISHED'}

class PIECREATOR_OT_ToggleType(bpy.types.Operator):
    bl_idname = "wm.pie_creator_toggle_type"
    bl_label = "Toggle Menu Type"
    menu_id: bpy.props.StringProperty()
    def execute(self, context):
        menus = load_menus(); menu = next((m for m in menus if m["id"] == self.menu_id), None)
        if not menu: return {'CANCELLED'}
        types = ['PIE', 'POPUP', 'DIALOG', 'MENU', 'STACK', 'STICKY']
        curr = menu.get("type", "PIE"); next_t = types[(types.index(curr) + 1) % len(types)]
        menu["type"] = next_t; save_menus(menus); bpy.ops.wm.pie_creator_reload(); return {'FINISHED'}

class PIECREATOR_OT_CutItem(bpy.types.Operator):
    bl_idname = "wm.pie_creator_cut_item"
    bl_label = "Cut Item"
    menu_id: bpy.props.StringProperty(); item_index: bpy.props.IntProperty()
    def execute(self, context):
        menus = load_menus(); menu = next((m for m in menus if m["id"] == self.menu_id), None)
        if not menu or not (0 <= self.item_index < len(menu["items"])): return {'CANCELLED'}
        wm = context.window_manager
        wm.pie_creator_item_clipboard = json.dumps(menu["items"][self.item_index])
        wm.pie_creator_clipboard_source_menu = self.menu_id
        wm.pie_creator_clipboard_is_cut = True; return {'FINISHED'}

classes = (
    PIECREATOR_OT_Exec,
    PIECREATOR_OT_CallMenu,
    PIECREATOR_OT_CallStack,
    PIECREATOR_OT_StickyKey,
    PIECREATOR_OT_PopupDialog,
    PIECREATOR_OT_ReloadMenus,
    PIECREATOR_OT_DuplicateItem,
    PIECREATOR_OT_CopyItem,
    PIECREATOR_OT_PasteItem,
    PIECREATOR_OT_AddToMenu,
    PIECREATOR_OT_AddBufferedToMenu,
    PIECREATOR_OT_Paste,
    PIECREATOR_OT_CallMaster,
    PIECREATOR_OT_SwitchDeck,
    PIECREATOR_OT_MoveToDeck,
    PIECREATOR_OT_AddDeck,
    PIECREATOR_OT_RemoveDeck,
    PIECREATOR_OT_SelectMenu,
    PIECREATOR_OT_ManageModes,
    PIECREATOR_OT_ToggleMode,
    PIECREATOR_OT_ManageAreas,
    PIECREATOR_OT_ToggleArea,
    PIECREATOR_OT_MoveMenu,
    PIECREATOR_OT_RemoveMenu,
    PIECREATOR_OT_AddItem,
    PIECREATOR_OT_MoveItem,
    PIECREATOR_OT_RemoveItem,
    PIECREATOR_OT_PrepareLink,
    PIECREATOR_OT_CreateLinkSubmenu,
    PIECREATOR_OT_UnlinkFromParent,
    PIECREATOR_OT_ToggleType,
    PIECREATOR_OT_CutItem,
)

