bl_info = {
    "name": "PieCreator HUD TEST V 0.5.8",
    "author": "Antigravity",
    "version": (0, 5, 8),
    "blender": (4, 0, 0),
    "location": "View3D > Ctrl + Shift + H",
    "description": "Clean Architecture HUD Engine",
    "category": "Interface",
}

import bpy
import importlib
from . import hud_draw, storage

importlib.reload(hud_draw)
importlib.reload(storage)

# --- Data Models ---

def update_hud_keymaps(self, context):
    try:
        unregister_keymaps()
        register_keymaps()
        # Save to JSON on update
        save_to_storage()
    except Exception as e:
        print(f"PieCreator HUD: Keymap update failed: {e}")

def save_to_storage():
    prefs = bpy.context.preferences.addons[__package__].preferences
    data = {"modules": []}
    for mod in prefs.modules:
        m_data = {
            "name": mod.name, "type": mod.type, "show_mode": mod.show_mode,
            "is_visible": mod.is_visible, "color": list(mod.color),
            "offset_x": mod.offset_x, "offset_y": mod.offset_y,
            "inner_r": mod.inner_r, "outer_r": mod.outer_r,
            "columns": mod.columns, "cell_w": mod.cell_w, "cell_h": mod.cell_h,
            "shortcut_key": mod.shortcut_key, "shortcut_ctrl": mod.shortcut_ctrl,
            "shortcut_shift": mod.shortcut_shift, "shortcut_alt": mod.shortcut_alt,
            "items": []
        }
        for item in mod.items:
            m_data["items"].append({
                "label": item.label, "command": item.command,
                "link_module": item.link_module, "icon": item.icon
            })
        data["modules"].append(m_data)
    storage.save_config(data)

class PIECREATOR_HUD_Item(bpy.types.PropertyGroup):
    label: bpy.props.StringProperty(name="Label", default="New Item")
    command: bpy.props.StringProperty(name="Command", default="print('Action')")
    link_module: bpy.props.StringProperty(name="Link to Module", default="")
    icon: bpy.props.StringProperty(name="Icon Name", default="DOT")

class PIECREATOR_HUD_LibraryItem(bpy.types.PropertyGroup):
    label: bpy.props.StringProperty(name="Label", default="Saved Action", update=update_hud_keymaps)
    command: bpy.props.StringProperty(name="Command", default="", update=update_hud_keymaps)
    icon: bpy.props.StringProperty(name="Icon", default="DOT", update=update_hud_keymaps)

class PIECREATOR_HUD_Module(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(name="Module Name", default="New Module")
    # ... (properties remain the same)
    type: bpy.props.EnumProperty(
        name="Type",
        items=[('RADIAL', "Radial", "Circular"), ('GRID', "Grid", "Box-based")],
        default='RADIAL'
    )
    show_mode: bpy.props.EnumProperty(
        name="Show In",
        items=[('ALL', "All", ""), ('OBJECT', "Object", ""), ('SCULPT', "Sculpt", ""), ('EDIT', "Edit", "")],
        default='ALL'
    )
    is_visible: bpy.props.BoolProperty(name="Visible", default=True)
    color: bpy.props.FloatVectorProperty(name="Color", subtype='COLOR', default=(0.1, 0.4, 0.8, 0.7), size=4, min=0, max=1)
    
    offset_x: bpy.props.FloatProperty(name="Offset X", default=0)
    offset_y: bpy.props.FloatProperty(name="Offset Y", default=0)
    
    # Shape Config
    inner_r: bpy.props.FloatProperty(name="Inner R", default=40)
    outer_r: bpy.props.FloatProperty(name="Outer R", default=90)
    columns: bpy.props.IntProperty(name="Columns", default=3, min=1)
    cell_w: bpy.props.FloatProperty(name="Cell Width", default=100)
    cell_h: bpy.props.FloatProperty(name="Cell Height", default=30)

    # Shortcut Config
    shortcut_key: bpy.props.StringProperty(name="Key", default="NONE", update=update_hud_keymaps)
    shortcut_ctrl: bpy.props.BoolProperty(name="Ctrl", default=False, update=update_hud_keymaps)
    shortcut_shift: bpy.props.BoolProperty(name="Shift", default=False, update=update_hud_keymaps)
    shortcut_alt: bpy.props.BoolProperty(name="Alt", default=False, update=update_hud_keymaps)

    items: bpy.props.CollectionProperty(type=PIECREATOR_HUD_Item)

# --- Preferences UI ---

class PIECREATOR_HUD_Preferences(bpy.types.AddonPreferences):
    bl_idname = __package__
    modules: bpy.props.CollectionProperty(type=PIECREATOR_HUD_Module)
    library: bpy.props.CollectionProperty(type=PIECREATOR_HUD_LibraryItem)
    active_profile: bpy.props.StringProperty(name="Profile", default="Default", update=update_hud_keymaps)

    def draw(self, context):
        layout = self.layout
        
        # Profile Section
        row = layout.row()
        row.prop(self, "active_profile", text="Active Profile", icon='OUTLINER_OB_GROUP_INSTANCE')
        row.operator("piecreator.hud_save", text="Force Save", icon='FILE_TICK')
        
        layout.separator()
        
        split = layout.split(factor=0.7)
        
        # Left: Modules
        col_main = split.column()
        col_main.label(text="HUD Modules:", icon='MENU_PANEL')
        col_main.operator("piecreator.hud_add_module", text="Add New Module", icon='ADD')
        
        for m_idx, mod in enumerate(self.modules):
            box = col_main.box()
            header = box.row()
            header.prop(mod, "is_visible", text="")
            header.prop(mod, "name", text="")
            header.prop(mod, "show_mode", text="")
            header.prop(mod, "type", text="")
            header.prop(mod, "color", text="")
            header.operator("piecreator.hud_remove_module", text="", icon='X').index = m_idx
            
            # Shortcut Row
            s_row = box.row(align=True)
            s_row.label(text="Shortcut:", icon='EVENT_H')
            s_row.prop(mod, "shortcut_key", text="")
            s_row.operator("piecreator.hud_key_binder", text="Bind", icon='MOUSE_MOVE').module_index = m_idx
            s_row.prop(mod, "shortcut_ctrl", text="Ctrl", toggle=True)
            s_row.prop(mod, "shortcut_shift", text="Shift", toggle=True)
            s_row.prop(mod, "shortcut_alt", text="Alt", toggle=True)

            # Parameters
            p_box = box.box()
            row = p_box.row(align=True)
            row.prop(mod, "offset_x"); row.prop(mod, "offset_y")
            if mod.type == 'RADIAL':
                row.prop(mod, "inner_r"); row.prop(mod, "outer_r")
            else:
                row.prop(mod, "columns"); row.prop(mod, "cell_w"); row.prop(mod, "cell_h")
            
            # Items
            col = box.column(align=True)
            for i_idx, item in enumerate(mod.items):
                i_row = col.row(align=True)
                i_row.prop(item, "label", text="")
                icon_op = i_row.operator("piecreator.hud_icon_picker", text="", icon=item.icon)
                icon_op.module_index = m_idx
                icon_op.item_index = i_idx
                i_row.prop(item, "link_module", text="", icon='LINKED')
                i_row.prop(item, "command", text="")
                op = i_row.operator("piecreator.hud_remove_item", text="", icon='REMOVE')
                op.module_index = m_idx
                op.item_index = i_idx
            box.operator("piecreator.hud_add_item", text="Add Item", icon='ADD').module_index = m_idx

        # Right: Library
        col_lib = split.column()
        col_lib.label(text="Library (Pool):", icon='ASSET_MANAGER')
        col_lib.operator("piecreator.hud_add_to_library", text="Add to Lib", icon='ADD')
        for l_idx, l_item in enumerate(self.library):
            box = col_lib.box()
            row = box.row()
            icon_op = row.operator("piecreator.hud_icon_picker", text="", icon=l_item.icon)
            icon_op.module_index = -1 # library mode
            icon_op.item_index = l_idx
            row.prop(l_item, "label", text="")
            row.operator("piecreator.hud_remove_from_library", text="", icon='X').index = l_idx
            box.prop(l_item, "command", text="")

# --- Operators ---

class PIECREATOR_OT_HUD_AddModule(bpy.types.Operator):
    bl_idname = "piecreator.hud_add_module"
    bl_label = "Add Module"
    def execute(self, context):
        context.preferences.addons[__package__].preferences.modules.add()
        return {'FINISHED'}

class PIECREATOR_OT_HUD_RemoveModule(bpy.types.Operator):
    bl_idname = "piecreator.hud_remove_module"
    bl_label = "Remove Module"
    index: bpy.props.IntProperty()
    def execute(self, context):
        context.preferences.addons[__package__].preferences.modules.remove(self.index)
        return {'FINISHED'}

class PIECREATOR_OT_HUD_AddItem(bpy.types.Operator):
    bl_idname = "piecreator.hud_add_item"
    bl_label = "Add Item"
    module_index: bpy.props.IntProperty()
    def execute(self, context):
        context.preferences.addons[__package__].preferences.modules[self.module_index].items.add()
        return {'FINISHED'}

class PIECREATOR_OT_HUD_RemoveItem(bpy.types.Operator):
    bl_idname = "piecreator.hud_remove_item"
    bl_label = "Remove Item"
    module_index: bpy.props.IntProperty()
    item_index: bpy.props.IntProperty()
    def execute(self, context):
        context.preferences.addons[__package__].preferences.modules[self.module_index].items.remove(self.item_index)
        return {'FINISHED'}

# --- Capture Logic (Ported from v10.2) ---

def get_op_command(op):
    import mathutils
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
                else: p_list.append(f"{p_id}={repr(val)}")
        return f"{cmd_base}({', '.join(p_list)})"
    except: return ""

def get_op_label(op):
    if not op: return "Action"
    idname = getattr(op, "bl_idname", None)
    try:
        if hasattr(op, "name") and op.name: return op.name
        if idname and "_OT_" in idname:
            parts = idname.split("_OT_")
            return getattr(getattr(bpy.ops, parts[0].lower()), parts[1]).get_rna_type().name
    except: pass
    return idname if idname else "Action"

def get_prop_info(context):
    if not hasattr(context, "button_prop") or not context.button_prop: return None, None, None
    prop = context.button_prop
    ptr = context.button_pointer
    try:
        if ptr.id_data:
            base = "bpy.context.active_object" if ptr.id_data == context.active_object else f"bpy.data.{ptr.id_data.rna_type.name.lower()}s['{ptr.id_data.name}']"
            path = ptr.path_from_id()
            full_path = f"{base}.{path}" if path else base
            return full_path, prop.identifier, prop.name
    except: pass
    return None, None, None

class PIECREATOR_OT_HUD_Capture(bpy.types.Operator):
    bl_idname = "piecreator.hud_capture"
    bl_label = "Capture to HUD"
    module_index: bpy.props.IntProperty()
    
    def execute(self, context):
        prefs = context.preferences.addons[__package__].preferences
        mod = prefs.modules[self.module_index]
        
        # Try Property
        path, prop, label = get_prop_info(context)
        if path:
            item = mod.items.add()
            item.label = label
            item.command = f"{path} = not {path}" if "bool" in prop.lower() else f"print({path})"
            self.report({'INFO'}, f"Captured Property: {label}")
            save_to_storage()
            return {'FINISHED'}
            
        # Try Operator
        wm = context.window_manager
        target_op = None
        if hasattr(context, "button_operator") and context.button_operator: target_op = context.button_operator
        elif wm.operators:
            for op in reversed(wm.operators):
                if "piecreator" not in getattr(op, 'bl_idname', '').lower(): target_op = op; break
        
        if target_op:
            item = mod.items.add()
            item.label = get_op_label(target_op)
            item.command = get_op_command(target_op)
            self.report({'INFO'}, f"Captured Operator: {item.label}")
            save_to_storage()
            return {'FINISHED'}
            
        return {'CANCELLED'}

def draw_context_menu(self, context):
    layout = self.layout
    prefs = context.preferences.addons[__package__].preferences
    if not prefs.modules: return
    
    layout.separator()
    layout.label(text="Add to HUD:", icon='MENU_PANEL')
    for i, mod in enumerate(prefs.modules):
        op = layout.operator("piecreator.hud_capture", text=mod.name, icon='ADD')
        op.module_index = i

class PIECREATOR_OT_HUD_Main(bpy.types.Operator):
    bl_idname = "piecreator.hud_main"
    bl_label = "PieCreator HUD"
    bl_options = {'REGISTER', 'UNDO'}
    
    module_index: bpy.props.IntProperty(default=-1)
    trigger_key: bpy.props.StringProperty(default="")

    def execute_action(self, context, mod_idx, item_idx):
        prefs = context.preferences.addons[__package__].preferences
        mod = prefs.modules[mod_idx]
        item = mod.items[item_idx]
        if item.link_module:
            target = next((m for m in prefs.modules if m.name == item.link_module), None)
            if target: target.is_visible = not target.is_visible
        if item.command:
            try:
                exec(item.command)
                self.report({'INFO'}, f"Executed: {item.label}")
            except Exception as e:
                self.report({'ERROR'}, str(e))

    def modal(self, context, event):
        context.area.tag_redraw()
        if event.type == 'MOUSEMOVE':
            self.mouse_pos = (event.mouse_region_x, event.mouse_region_y)
        
        # Click
        if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            hit = hud_draw._drawer.get_last_hit()
            if hit[0] is not None: self.execute_action(context, *hit)

        # Swipe (Hold-Release)
        if self.trigger_key and event.type == self.trigger_key and event.value == 'RELEASE':
            hit = hud_draw._drawer.get_last_hit()
            if hit[0] is not None: self.execute_action(context, *hit)
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
            return {'FINISHED'}

        if event.value == 'PRESS' and event.type in {'ESC', 'RIGHTMOUSE'}:
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
            return {'FINISHED'}
        return {'RUNNING_MODAL'}

    def invoke(self, context, event):
        if context.area.type != 'VIEW_3D': return {'CANCELLED'}
        self.trigger_key = event.type
        self.mouse_pos = (event.mouse_region_x, event.mouse_region_y)
        hud_draw._drawer.init_session(self.module_index)
        args = (self, context)
        self._handle = bpy.types.SpaceView3D.draw_handler_add(hud_draw.draw_callback, args, 'WINDOW', 'POST_PIXEL')
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

class PIECREATOR_OT_HUD_Save(bpy.types.Operator):
    bl_idname = "piecreator.hud_save"
    bl_label = "Save HUD Config"
    def execute(self, context):
        save_to_storage()
        self.report({'INFO'}, "HUD Config Saved to JSON")
        return {'FINISHED'}

class PIECREATOR_OT_HUD_AddLibrary(bpy.types.Operator):
    bl_idname = "piecreator.hud_add_to_library"
    bl_label = "Add to Library"
    def execute(self, context):
        context.preferences.addons[__package__].preferences.library.add()
        return {'FINISHED'}

class PIECREATOR_OT_HUD_RemoveLibrary(bpy.types.Operator):
    bl_idname = "piecreator.hud_remove_from_library"
    bl_label = "Remove from Library"
    index: bpy.props.IntProperty()
    def execute(self, context):
        context.preferences.addons[__package__].preferences.library.remove(self.index)
        return {'FINISHED'}

class PIECREATOR_OT_HUD_IconPicker(bpy.types.Operator):
    bl_idname = "piecreator.hud_icon_picker"
    bl_label = "Select Icon"
    bl_property = "icon_enum"
    
    def get_icons(self, context):
        import _bpy
        items = _bpy.types.UILayout.bl_rna.functions['prop'].parameters['icon'].enum_items.keys()
        return [(i, i, "", i, idx) for idx, i in enumerate(sorted(items))]
    
    icon_enum: bpy.props.EnumProperty(items=get_icons)
    module_index: bpy.props.IntProperty()
    item_index: bpy.props.IntProperty(default=-1) # -1 for library

    def execute(self, context):
        prefs = context.preferences.addons[__package__].preferences
        if self.module_index == -1:
            prefs.library[self.item_index].icon = self.icon_enum
        else:
            prefs.modules[self.module_index].items[self.item_index].icon = self.icon_enum
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.invoke_search_popup(self)
        return {'FINISHED'}

class PIECREATOR_OT_HUD_KeyBinder(bpy.types.Operator):
    bl_idname = "piecreator.hud_key_binder"
    bl_label = "Press any key..."
    
    module_index: bpy.props.IntProperty()
    
    def modal(self, context, event):
        if event.value == 'PRESS':
            if event.type in {'ESC', 'RIGHTMOUSE'}:
                return {'CANCELLED'}
            
            prefs = context.preferences.addons[__package__].preferences
            mod = prefs.modules[self.module_index]
            
            # Filter modifiers
            if event.type in {'LEFT_CTRL', 'RIGHT_CTRL', 'LEFT_ALT', 'RIGHT_ALT', 'LEFT_SHIFT', 'RIGHT_SHIFT', 'OSKEY'}:
                return {'RUNNING_MODAL'}
                
            mod.shortcut_key = event.type
            mod.shortcut_ctrl = event.ctrl
            mod.shortcut_shift = event.shift
            mod.shortcut_alt = event.alt
            
            update_hud_keymaps(None, context)
            self.report({'INFO'}, f"Bound to: {mod.shortcut_key}")
            return {'FINISHED'}
            
        return {'RUNNING_MODAL'}

    def invoke(self, context, event):
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

classes = (
    PIECREATOR_HUD_Item, PIECREATOR_HUD_LibraryItem, PIECREATOR_HUD_Module, PIECREATOR_HUD_Preferences, 
    PIECREATOR_OT_HUD_AddModule, PIECREATOR_OT_HUD_RemoveModule, 
    PIECREATOR_OT_HUD_AddItem, PIECREATOR_OT_HUD_RemoveItem, 
    PIECREATOR_OT_HUD_Main, PIECREATOR_OT_HUD_Capture,
    PIECREATOR_OT_HUD_Save, PIECREATOR_OT_HUD_AddLibrary, PIECREATOR_OT_HUD_RemoveLibrary,
    PIECREATOR_OT_HUD_IconPicker, PIECREATOR_OT_HUD_KeyBinder
)
addon_keymaps = []

def register_keymaps():
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if not kc: return
    
    km = kc.keymaps.new(name='3D View', space_type='VIEW_3D')
    prefs = bpy.context.preferences.addons[__package__].preferences
    
    for m_idx, mod in enumerate(prefs.modules):
        if mod.shortcut_key == 'NONE': continue
        
        kmi = km.keymap_items.new(
            PIECREATOR_OT_HUD_Main.bl_idname, 
            mod.shortcut_key, 
            'PRESS', 
            ctrl=mod.shortcut_ctrl, 
            shift=mod.shortcut_shift, 
            alt=mod.shortcut_alt
        )
        kmi.properties.module_index = m_idx
        addon_keymaps.append((km, kmi))

def unregister_keymaps():
    for km, kmi in addon_keymaps:
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()

def register():
    for cls in classes: bpy.utils.register_class(cls)
    
    # Load from Storage
    prefs = bpy.context.preferences.addons[__package__].preferences
    if not prefs.modules:
        config = storage.load_config()
        for m_data in config.get("modules", []):
            mod = prefs.modules.add()
            for key, val in m_data.items():
                if key == "items":
                    for i_data in val:
                        item = mod.items.add()
                        for i_key, i_val in i_data.items(): setattr(item, i_key, i_val)
                elif hasattr(mod, key): setattr(mod, key, val)
    
    # Default if still empty
    if not prefs.modules:
        m1 = prefs.modules.add(); m1.name = "Tools"; m1.type = 'RADIAL'
        m1.shortcut_key = 'H'; m1.shortcut_ctrl = True; m1.shortcut_shift = True
        it1 = m1.items.add(); it1.label = "Shapes >"; it1.link_module = "Shapes"
        m2 = prefs.modules.add(); m2.name = "Shapes"; m2.type = 'GRID'; m2.is_visible = False; m2.offset_x = 160
        for l in ["Cube", "Sphere", "Monkey"]: m2.items.add().label = l

    bpy.types.UI_MT_button_context_menu.append(draw_context_menu)
    register_keymaps()

def unregister():
    bpy.types.UI_MT_button_context_menu.remove(draw_context_menu)
    unregister_keymaps()
    for cls in reversed(classes): bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()
