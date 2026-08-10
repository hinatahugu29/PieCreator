import bpy
import mathutils
import blf
from ..storage import load_config, save_config, load_menus, sanitize_command

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
        print(f"PieCreator Error: {e}")
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
    bl_idname = "wm.pie_creator_reload"
    bl_label = "Reload & Sync"
    def execute(self, context):
        config = load_config(); save_config(config)
        from .. import register_dynamic_menus; register_dynamic_menus()
        return {'FINISHED'}

class PIECREATOR_OT_CallMaster(bpy.types.Operator):
    bl_idname = "wm.pie_creator_call_master"
    bl_label = "Call Master Menu"
    def execute(self, context):
        config = load_config()
        m_id = config.get("master_menu_id")
        if m_id: bpy.ops.wm.pie_creator_call(menu_id=m_id)
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
