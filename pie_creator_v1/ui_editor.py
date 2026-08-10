import bpy
from .storage import load_menus, save_menus

class PIECREATOR_MT_DeckSwitchMenu(bpy.types.Menu):
    bl_label = "Switch Deck"
    bl_idname = "PIECREATOR_MT_DeckSwitchMenu"

    def draw(self, context):
        layout = self.layout
        from .storage import load_config
        config = load_config()
        for d in config["decks"]:
            op = layout.operator("wm.pie_creator_switch_deck", text=d["name"])
            op.deck_id = d["id"]

class PIECREATOR_MT_MoveToDeckMenu(bpy.types.Menu):
    bl_label = "Move to Deck"
    bl_idname = "PIECREATOR_MT_MoveToDeckMenu"

    def draw(self, context):
        layout = self.layout
        from .storage import load_config
        config = load_config()
        menu_id = context.window_manager.pie_creator_moving_menu_id
        
        for d in config["decks"]:
            op = layout.operator("wm.pie_creator_move_to_deck", text=d["name"])
            op.menu_id = menu_id
            op.deck_id = d["id"]

def get_menu_hierarchy(menus, active_deck_id):
    """メニューの親子関係を解析し、ツリー順のリストを生成する（デッキ内限定）"""
    deck_menus = {m["id"] for m in menus if m.get("deck_id", "default") == active_deck_id}
    
    parent_map = {m["id"]: [] for m in menus if m["id"] in deck_menus}
    for m in menus:
        if m["id"] not in deck_menus: continue
        for item in m.get("items", []):
            if item.get("type") == "MENU":
                target = item.get("menu_id")
                if target in parent_map:
                    parent_map[target].append(m["id"])
    
    roots = []
    for i, m in enumerate(menus):
        if m["id"] in deck_menus and not parent_map[m["id"]]:
            roots.append(i)
    
    ordered = []
    visited = set()
    
    def add_recursive(idx, level, path_str):
        if idx in visited: return
        visited.add(idx)
        ordered.append({
            "index": idx,
            "level": level,
            "path": path_str
        })
        
        menu = menus[idx]
        current_path = f"{path_str} > {menu['name']}" if path_str else menu['name']
        
        for item in menu.get("items", []):
            if item.get("type") == "MENU":
                target_id = item.get("menu_id")
                for c_idx, m in enumerate(menus):
                    if m["id"] == target_id:
                        add_recursive(c_idx, level + 1, current_path)
                        break

    for r_idx in roots:
        add_recursive(r_idx, 0, "")
    for i, m in enumerate(menus):
        if m["id"] in deck_menus and i not in visited:
            add_recursive(i, 0, "")
            
    return ordered

class PIECREATOR_Preferences(bpy.types.AddonPreferences):
    bl_idname = __package__
    
    search_query: bpy.props.StringProperty(
        name="Search",
        description="Search menus by name or ID",
        default=""
    )

    def draw(self, context):
        layout = self.layout
        from .storage import load_config
        config = load_config()
        active_deck_id = config.get("active_deck", "default")
        menus = config.get("menus", [])
        decks = config.get("decks", [])

        # Top Bar
        row = layout.row(align=True)
        row.operator("wm.pie_creator_reload", text="Reload & Sync", icon='FILE_REFRESH')
        row.operator("wm.pie_creator_export", text="Export Settings", icon='EXPORT')
        row.operator("wm.pie_creator_import", text="Import Settings", icon='IMPORT')
        
        # Macro Recorder Status
        wm = context.window_manager
        row.separator()
        if not wm.pie_creator_is_recording:
            rec = row.operator("wm.pie_creator_macro_recorder", text="Macro Recorder", icon='REC')
            rec.menu_id = "" # Default
        else:
            stop = row.operator("wm.pie_creator_macro_recorder", text="STOP RECORDING", icon='CANCEL')
        
        layout.separator()

        # Deck Manager
        box = layout.box()
        row = box.row()
        row.label(text="Active Deck:", icon='OUTLINER_COLLECTION')
        current_deck_name = next((d["name"] for d in decks if d["id"] == active_deck_id), "Unknown")
        row.menu("PIECREATOR_MT_DeckSwitchMenu", text=current_deck_name)
        row.operator("wm.pie_creator_add_deck", text="", icon='ADD')
        if active_deck_id != "default":
            del_deck = row.operator("wm.pie_creator_remove_deck", text="", icon='X')
            del_deck.deck_id = active_deck_id

        layout.separator()

        # Menu List Header
        row = layout.row()
        row.label(text="Registered Menus", icon='MENU_PANEL')
        
        # Master Key
        row.separator(factor=2.0)
        row.label(text="Master Key:", icon='KEYINGSET')
        kc = context.window_manager.keyconfigs.addon
        if kc:
            km = kc.keymaps.get("Window")
            if km:
                for kmi in km.keymap_items:
                    if kmi.idname == "wm.pie_creator_call_master":
                        row.prop(kmi, "type", text="", full_event=True)
                        break
        
        row.separator(factor=1.0)
        row.prop(self, "search_query", text="", icon='VIEWZOOM')
        row.operator("wm.pie_creator_add_menu", text="Add Menu", icon='ADD')

        q = self.search_query.lower()
        ordered_data = get_menu_hierarchy(menus, active_deck_id)
        
        for item_data in ordered_data:
            idx = item_data["index"]
            level = item_data["level"]
            path = item_data["path"]
            menu = menus[idx]
            
            if q and q not in menu['name'].lower() and q not in menu['id'].lower():
                continue
            
            main_row = layout.row()
            if level > 0:
                split = main_row.split(factor=min(0.05 * level, 0.4))
                spacer = split.column()
                for _ in range(level):
                    spacer.label(text="", icon='TRIA_RIGHT' if _ == level-1 else 'BLANK1')
                content_col = split.column()
            else:
                content_col = main_row.column()

            box = content_col.box()
            if path:
                p_row = box.row()
                p_row.label(text=path, icon='CON_CHILDOF')
                p_row.scale_y = 0.6

            header = box.row()
            
            # Management Buttons
            op_row = header.row(align=True)
            dup = op_row.operator("wm.pie_creator_duplicate_menu", text="", icon='DUPLICATE')
            dup.menu_id = menu["id"]
            
            move_up = op_row.operator("wm.pie_creator_move_menu", text="", icon='TRIA_UP')
            move_up.menu_id = menu["id"]
            move_up.direction = 'UP'
            
            move_down = op_row.operator("wm.pie_creator_move_menu", text="", icon='TRIA_DOWN')
            move_down.menu_id = menu["id"]
            move_down.direction = 'DOWN'
            
            rem = op_row.operator("wm.pie_creator_remove_menu", text="", icon='X')
            rem.menu_id = menu["id"]
            
            # Config Buttons
            config_row = header.row(align=True)
            is_master = config.get("master_menu_id") == menu["id"]
            master_icon = 'SOLO_ON' if is_master else 'SOLO_OFF'
            master_op = config_row.operator("wm.pie_creator_set_master_menu", text="", icon=master_icon)
            master_op.menu_id = menu["id"]
            
            toggle = config_row.operator("wm.pie_creator_toggle_type", text="", icon='FILE_REFRESH')
            toggle.menu_id = menu["id"]
            
            mode_op = config_row.operator("wm.pie_creator_manage_modes", text="Modes", icon='RESTRICT_SELECT_OFF')
            mode_op.menu_id = menu["id"]
            
            area_op = config_row.operator("wm.pie_creator_manage_areas", text="Areas", icon='VIEW3D')
            area_op.menu_id = menu["id"]
            
            header.label(text=f"[{menu.get('type', 'PIE')}] {menu['name']}")
            
            rename = header.operator("wm.pie_creator_rename_menu", text="", icon='GREASEPENCIL', emboss=False)
            rename.menu_id = menu["id"]
            rename.new_name = menu['name']

            # ID Display
            box.label(text=f"ID: {menu['id']}")

            # Items Section
            is_sticky = menu.get('type') == 'STICKY'
            item_box = box.column(align=True)
            
            if is_sticky:
                items = menu.get('items', [])
                while len(items) < 2:
                    items.append({"label": "Action", "command": ""})
                
                for label_prefix, i_idx in [("On Press", 0), ("On Release", 1)]:
                    row = item_box.row()
                    row.label(text=label_prefix, icon='DOT')
                    cmd = items[i_idx].get('command', '')
                    edit = row.operator("wm.pie_creator_add_item", text=cmd[:30] if cmd else "(Empty)", icon='GREASEPENCIL')
                    edit.menu_id = menu["id"]
                    edit.item_index = i_idx
            else:
                for j, item in enumerate(menu.get('items', [])):
                    row = item_box.row(align=True)
                    icon = item.get('icon', 'BLANK1')
                    row.label(text=item.get('label', 'No Label'), icon=icon if icon != "NONE" else 'BLANK1')
                    
                    mv_up = row.operator("wm.pie_creator_move_item", text="", icon='TRIA_UP')
                    mv_up.menu_id = menu["id"]
                    mv_up.item_index = j
                    mv_up.direction = 'UP'
                    
                    mv_down = row.operator("wm.pie_creator_move_item", text="", icon='TRIA_DOWN')
                    mv_down.menu_id = menu["id"]
                    mv_down.item_index = j
                    mv_down.direction = 'DOWN'
                    
                    edit = row.operator("wm.pie_creator_add_item", text="", icon='PREFERENCES')
                    edit.menu_id = menu["id"]
                    edit.item_index = j
                    
                    rem = row.operator("wm.pie_creator_remove_item", text="", icon='X')
                    rem.menu_id = menu["id"]
                    rem.item_index = j
                
                add = box.operator("wm.pie_creator_add_item", text="Add Item", icon='ADD')
                add.menu_id = menu["id"]
            
            # Local Macro Recorder
            macro_row = box.row(align=True)
            macro_row.label(text="Recording:", icon='REC')
            m_rec = macro_row.operator("wm.pie_creator_macro_recorder", text="Start Here", icon='PLAY')
            m_rec.menu_id = menu["id"]

# --- Operators ---

class PIECREATOR_OT_AddMenu(bpy.types.Operator):
    bl_idname = "wm.pie_creator_add_menu"
    bl_label = "Add New Menu"
    type: bpy.props.EnumProperty(
        items=[('PIE', "Pie Menu", ""), ('STACK', "Stack Key", ""), ('STICKY', "Sticky Key", "")]
    )
    def execute(self, context):
        from .storage import generate_unique_id, load_config, save_config
        config = load_config()
        active_deck_id = config.get("active_deck", "default")
        menus = config.get("menus", [])
        new_id = generate_unique_id("custom_menu", menus)
        menus.append({
            "id": new_id, "name": "New Menu", "type": self.type, 
            "deck_id": active_deck_id, "modes": [], "areas": [], "items": []
        })
        save_config(config)
        bpy.ops.wm.pie_creator_reload()
        return {'FINISHED'}

class PIECREATOR_OT_RenameMenu(bpy.types.Operator):
    bl_idname = "wm.pie_creator_rename_menu"
    bl_label = "Rename Menu"
    menu_id: bpy.props.StringProperty()
    new_name: bpy.props.StringProperty(name="New Name")
    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)
    def execute(self, context):
        menus = load_menus()
        menu = next((m for m in menus if m["id"] == self.menu_id), None)
        if menu:
            menu["name"] = self.new_name
            save_menus(menus)
            bpy.ops.wm.pie_creator_reload()
        return {'FINISHED'}

class PIECREATOR_OT_RemoveMenu(bpy.types.Operator):
    bl_idname = "wm.pie_creator_remove_menu"
    bl_label = "Remove Menu"
    menu_id: bpy.props.StringProperty()
    def execute(self, context):
        menus = load_menus()
        menus = [m for m in menus if m["id"] != self.menu_id]
        save_menus(menus)
        bpy.ops.wm.pie_creator_reload()
        return {'FINISHED'}

class PIECREATOR_OT_AddItem(bpy.types.Operator):
    bl_idname = "wm.pie_creator_add_item"
    bl_label = "Edit Item"
    menu_id: bpy.props.StringProperty()
    item_index: bpy.props.IntProperty(default=-1)
    
    type: bpy.props.EnumProperty(
        items=[('COMMAND', "Command", ""), ('MENU', "Submenu", ""), ('SEPARATOR', "Separator", "")]
    )
    label: bpy.props.StringProperty(name="Label")
    icon: bpy.props.StringProperty(name="Icon", default="NONE")
    command: bpy.props.StringProperty(name="Command")
    target_menu_id: bpy.props.StringProperty(name="Target Menu ID")

    def invoke(self, context, event):
        menus = load_menus()
        menu = next((m for m in menus if m["id"] == self.menu_id), None)
        if self.item_index != -1 and menu:
            items = menu.get("items", [])
            if 0 <= self.item_index < len(items):
                item = items[self.item_index]
                self.type = item.get("type", "COMMAND")
                self.label = item.get("label", "")
                self.icon = item.get("icon", "NONE")
                self.command = item.get("command", "")
                self.target_menu_id = item.get("menu_id", "")
        return context.window_manager.invoke_props_dialog(self, width=400)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "type")
        if self.type != 'SEPARATOR':
            layout.prop(self, "label")
            row = layout.row(align=True)
            row.prop(self, "icon")
            row.prop_search(self, "icon", context.window_manager, "pie_creator_icons_search", text="", icon='VIEWZOOM')
            if self.type == 'COMMAND':
                layout.prop(self, "command")
            else:
                layout.prop_search(self, "target_menu_id", context.window_manager, "pie_creator_menus_search", text="Target Menu")

    def execute(self, context):
        menus = load_menus()
        menu = next((m for m in menus if m["id"] == self.menu_id), None)
        if not menu: return {'CANCELLED'}
        
        new_item = {"type": self.type, "label": self.label, "icon": self.icon, "command": self.command, "menu_id": self.target_menu_id}
        items = menu.setdefault("items", [])
        if self.item_index == -1: items.append(new_item)
        elif 0 <= self.item_index < len(items): items[self.item_index] = new_item
        
        save_menus(menus)
        bpy.ops.wm.pie_creator_reload()
        return {'FINISHED'}

class PIECREATOR_OT_RemoveItem(bpy.types.Operator):
    bl_idname = "wm.pie_creator_remove_item"
    bl_label = "Remove Item"
    menu_id: bpy.props.StringProperty()
    item_index: bpy.props.IntProperty()
    def execute(self, context):
        menus = load_menus()
        menu = next((m for m in menus if m["id"] == self.menu_id), None)
        if menu:
            items = menu.get("items", [])
            if 0 <= self.item_index < len(items):
                items.pop(self.item_index)
                save_menus(menus)
                bpy.ops.wm.pie_creator_reload()
        return {'FINISHED'}

class PIECREATOR_OT_ManageModes(bpy.types.Operator):
    bl_idname = "wm.pie_creator_manage_modes"
    bl_label = "Manage Modes"
    menu_id: bpy.props.StringProperty()
    mode: bpy.props.StringProperty()
    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)
    def draw(self, context):
        layout = self.layout
        menus = load_menus()
        menu = next((m for m in menus if m["id"] == self.menu_id), None)
        if not menu: return
        active = menu.get("modes", [])
        for m_id, name in [('OBJECT', "Object"), ('EDIT_MESH', "Mesh Edit"), ('SCULPT', "Sculpt"), ('POSE', "Pose")]:
            row = layout.row()
            icon = 'CHECKBOX_HLT' if m_id in active else 'CHECKBOX_DEHLT'
            op = row.operator("wm.pie_creator_manage_modes", text=name, icon=icon)
            op.menu_id = self.menu_id; op.mode = m_id
    def execute(self, context):
        if not self.mode: return {'FINISHED'}
        menus = load_menus()
        menu = next((m for m in menus if m["id"] == self.menu_id), None)
        if menu:
            modes = menu.setdefault("modes", [])
            if self.mode in modes: modes.remove(self.mode)
            else: modes.append(self.mode)
            save_menus(menus); bpy.ops.wm.pie_creator_reload()
        return {'FINISHED'}

class PIECREATOR_OT_ManageAreas(bpy.types.Operator):
    bl_idname = "wm.pie_creator_manage_areas"
    bl_label = "Manage Areas"
    menu_id: bpy.props.StringProperty()
    area_type: bpy.props.StringProperty()
    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)
    def draw(self, context):
        layout = self.layout
        menus = load_menus()
        menu = next((m for m in menus if m["id"] == self.menu_id), None)
        if not menu: return
        active = menu.get("areas", [])
        for a_id, name in [('VIEW3D', "3D Viewport"), ('IMAGE_EDITOR', "UV/Image"), ('NODE_EDITOR', "Nodes")]:
            row = layout.row()
            icon = 'CHECKBOX_HLT' if a_id in active else 'CHECKBOX_DEHLT'
            op = row.operator("wm.pie_creator_manage_areas", text=name, icon=icon)
            op.menu_id = self.menu_id; op.area_type = a_id
    def execute(self, context):
        if not self.area_type: return {'FINISHED'}
        menus = load_menus()
        menu = next((m for m in menus if m["id"] == self.menu_id), None)
        if menu:
            areas = menu.setdefault("areas", [])
            if self.area_type in areas: areas.remove(self.area_type)
            else: areas.append(self.area_type)
            save_menus(menus); bpy.ops.wm.pie_creator_reload()
        return {'FINISHED'}

class PIECREATOR_OT_ToggleType(bpy.types.Operator):
    bl_idname = "wm.pie_creator_toggle_type"
    bl_label = "Toggle Type"
    menu_id: bpy.props.StringProperty()
    def execute(self, context):
        menus = load_menus()
        menu = next((m for m in menus if m["id"] == self.menu_id), None)
        if menu:
            types = ['PIE', 'STACK', 'STICKY']
            curr = menu.get('type', 'PIE')
            menu['type'] = types[(types.index(curr) + 1) % len(types)]
            save_menus(menus); bpy.ops.wm.pie_creator_reload()
        return {'FINISHED'}

class PIECREATOR_OT_MoveMenu(bpy.types.Operator):
    bl_idname = "wm.pie_creator_move_menu"
    bl_label = "Move Menu"
    menu_id: bpy.props.StringProperty()
    direction: bpy.props.EnumProperty(items=[('UP', "Up", ""), ('DOWN', "Down", "")])
    def execute(self, context):
        menus = load_menus()
        idx = next((i for i, m in enumerate(menus) if m["id"] == self.menu_id), -1)
        if idx != -1:
            if self.direction == 'UP' and idx > 0: menus[idx], menus[idx-1] = menus[idx-1], menus[idx]
            elif self.direction == 'DOWN' and idx < len(menus)-1: menus[idx], menus[idx+1] = menus[idx+1], menus[idx]
            save_menus(menus); bpy.ops.wm.pie_creator_reload()
        return {'FINISHED'}

class PIECREATOR_OT_MoveItem(bpy.types.Operator):
    bl_idname = "wm.pie_creator_move_item"
    bl_label = "Move Item"
    menu_id: bpy.props.StringProperty()
    item_index: bpy.props.IntProperty()
    direction: bpy.props.EnumProperty(items=[('UP', "Up", ""), ('DOWN', "Down", "")])
    def execute(self, context):
        menus = load_menus()
        menu = next((m for m in menus if m["id"] == self.menu_id), None)
        if menu:
            items = menu.get("items", [])
            idx = self.item_index
            if self.direction == 'UP' and idx > 0: items[idx], items[idx-1] = items[idx-1], items[idx]
            elif self.direction == 'DOWN' and idx < len(items)-1: items[idx], items[idx+1] = items[idx+1], items[idx]
            save_menus(menus); bpy.ops.wm.pie_creator_reload()
        return {'FINISHED'}

class PIECREATOR_OT_DuplicateMenu(bpy.types.Operator):
    bl_idname = "wm.pie_creator_duplicate_menu"
    bl_label = "Duplicate Menu"
    menu_id: bpy.props.StringProperty()
    def execute(self, context):
        from .storage import generate_unique_id
        menus = load_menus()
        menu = next((m for m in menus if m["id"] == self.menu_id), None)
        if menu:
            import copy
            new_menu = copy.deepcopy(menu)
            new_menu['id'] = generate_unique_id(new_menu['id'], menus)
            new_menu['name'] += " (Copy)"
            menus.append(new_menu)
            save_menus(menus); bpy.ops.wm.pie_creator_reload()
        return {'FINISHED'}

class PIECREATOR_OT_GuessLabel(bpy.types.Operator):
    bl_idname = "wm.pie_creator_guess_label"
    bl_label = "Guess Label"
    menu_id: bpy.props.StringProperty()
    command: bpy.props.StringProperty()
    def execute(self, context):
        from .operators import get_label_from_command
        label = get_label_from_command(self.command)
        if label:
            context.window_manager.pie_creator_buffer_label = label
            context.window_manager.pie_creator_has_buffer = True
        return {'FINISHED'}

class PIECREATOR_OT_SetMasterMenu(bpy.types.Operator):
    bl_idname = "wm.pie_creator_set_master_menu"
    bl_label = "Set as Master"
    menu_id: bpy.props.StringProperty()
    def execute(self, context):
        from .storage import load_config, save_config
        config = load_config(); config["master_menu_id"] = self.menu_id
        save_config(config); bpy.ops.wm.pie_creator_reload()
        return {'FINISHED'}

class PIECREATOR_OT_AddDeck(bpy.types.Operator):
    bl_idname = "wm.pie_creator_add_deck"
    bl_label = "Add Deck"
    name: bpy.props.StringProperty(name="Deck Name", default="New Deck")
    def invoke(self, context, event): return context.window_manager.invoke_props_dialog(self)
    def execute(self, context):
        from .storage import load_config, save_config
        config = load_config()
        # Ensure unique ID
        import time
        new_id = f"deck_{int(time.time())}"
        config["decks"].append({"id": new_id, "name": self.name})
        save_config(config)
        bpy.ops.wm.pie_creator_reload()
        return {'FINISHED'}

class PIECREATOR_OT_RemoveDeck(bpy.types.Operator):
    bl_idname = "wm.pie_creator_remove_deck"
    bl_label = "Remove Deck"
    deck_id: bpy.props.StringProperty()
    def execute(self, context):
        from .storage import load_config, save_config
        config = load_config()
        config["decks"] = [d for d in config["decks"] if d["id"] != self.deck_id]
        if config["active_deck"] == self.deck_id: config["active_deck"] = "default"
        save_config(config); bpy.ops.wm.pie_creator_reload(); return {'FINISHED'}

class PIECREATOR_OT_SwitchDeck(bpy.types.Operator):
    bl_idname = "wm.pie_creator_switch_deck"
    bl_label = "Switch Deck"
    deck_id: bpy.props.StringProperty()
    def execute(self, context):
        from .storage import load_config, save_config
        config = load_config(); config["active_deck"] = self.deck_id
        save_config(config); bpy.ops.wm.pie_creator_reload(); return {'FINISHED'}

class PIECREATOR_OT_MoveToDeck(bpy.types.Operator):
    bl_idname = "wm.pie_creator_move_to_deck"
    bl_label = "Move to Deck"
    menu_id: bpy.props.StringProperty()
    deck_id: bpy.props.StringProperty()
    def execute(self, context):
        from .storage import load_config, save_config
        config = load_config()
        for m in config["menus"]:
            if m["id"] == self.menu_id: m["deck_id"] = self.deck_id; break
        save_config(config); bpy.ops.wm.pie_creator_reload(); return {'FINISHED'}

classes = (
    PIECREATOR_MT_DeckSwitchMenu,
    PIECREATOR_MT_MoveToDeckMenu,
    PIECREATOR_Preferences, 
    PIECREATOR_OT_AddMenu, 
    PIECREATOR_OT_RenameMenu,
    PIECREATOR_OT_RemoveMenu, 
    PIECREATOR_OT_AddItem, 
    PIECREATOR_OT_RemoveItem,
    PIECREATOR_OT_ManageModes,
    PIECREATOR_OT_ManageAreas,
    PIECREATOR_OT_ToggleType,
    PIECREATOR_OT_MoveMenu,
    PIECREATOR_OT_MoveItem,
    PIECREATOR_OT_DuplicateMenu,
    PIECREATOR_OT_GuessLabel,
    PIECREATOR_OT_SetMasterMenu,
    PIECREATOR_OT_AddDeck,
    PIECREATOR_OT_RemoveDeck,
    PIECREATOR_OT_SwitchDeck,
    PIECREATOR_OT_MoveToDeck
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
