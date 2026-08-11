# SPDX-License-Identifier: GPL-3.0-or-later
import bpy
from ..storage import load_menus, save_menus, load_config, save_config, generate_unique_id
from ..log import log_debug
from .core import get_label_from_command

# ※ 状態管理用のセット（ui/components.py と共有される想定）
# 本来は WindowManager 等に持たせるのが Blender 流だが、
# 既存のロジックを維持するため、ここではモジュールレベルで保持する。
# 後ほど ui/components.py 等で参照できるように調整が必要。
from ..ui import components

class PIECREATOR_OT_ToggleCollapse(bpy.types.Operator):
    """Collapse or expand this menu in the editor list"""
    bl_idname = "wm.pie_creator_toggle_collapse"
    bl_label = "Toggle Collapse"
    menu_id: bpy.props.StringProperty()
    def execute(self, context):
        if self.menu_id in components.collapsed_menus:
            components.collapsed_menus.discard(self.menu_id)
            # 展開されたときにアクティブに設定
            components.set_active_menu_id(context.window_manager, self.menu_id)
        else:
            components.collapsed_menus.add(self.menu_id)
        return {'FINISHED'}

class PIECREATOR_OT_CollapseAll(bpy.types.Operator):
    """Collapse every menu in the editor list"""
    bl_idname = "wm.pie_creator_collapse_all"
    bl_label = "Collapse All"
    def execute(self, context):
        config = load_config()
        for m in config.get("menus", []):
            components.collapsed_menus.add(m["id"])
        return {'FINISHED'}

class PIECREATOR_OT_ExpandAll(bpy.types.Operator):
    """Expand every menu in the editor list"""
    bl_idname = "wm.pie_creator_expand_all"
    bl_label = "Expand All"
    def execute(self, context):
        components.collapsed_menus.clear()
        return {'FINISHED'}

class PIECREATOR_OT_AddMenu(bpy.types.Operator):
    """Create a new menu in the active deck"""
    bl_idname = "wm.pie_creator_add_menu"
    bl_label = "Add New Menu"
    type: bpy.props.EnumProperty(
        name="Type",
        items=[
            ('PIE',    "Pie Menu", "Radial menu around the cursor"), 
            ('POPUP',  "Popup (Live)", "Live popup that closes when you release the mouse"),
            ('DIALOG', "Dialog (OK)", "Dialog that stays open until you confirm it"),
            ('MENU',   "Menu (List)", "Vertical list menu inside a box"),
            ('STACK',  "Stack Key", "Key that steps through its items on each press"), 
            ('STICKY', "Sticky Key", "Key that acts on press and again on release")
        ]
    )
    def execute(self, context):
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
    """Change the display name and identifier of this menu"""
    bl_idname = "wm.pie_creator_rename_menu"
    bl_label = "Rename Menu"
    
    menu_id: bpy.props.StringProperty()
    new_id: bpy.props.StringProperty(name="Menu ID")
    new_name: bpy.props.StringProperty(name="Menu Name")

    def invoke(self, context, event):
        self.new_id = self.menu_id
        menus = load_menus()
        menu = next((m for m in menus if m["id"] == self.menu_id), None)
        if menu:
            self.new_name = menu.get("name", "")
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "new_id")
        layout.prop(self, "new_name")
        if self.new_id != self.menu_id:
            layout.label(text="Changing the ID updates every reference to this menu", icon='ERROR')

    def execute(self, context):
        config = load_config()
        menus = config.get("menus", [])
        old_id = self.menu_id
        new_id = self.new_id
        
        if not new_id:
            self.report({'ERROR'}, "The ID cannot be empty")
            return {'CANCELLED'}
            
        if new_id != old_id and any(m["id"] == new_id for m in menus):
            self.report({'ERROR'}, f"The ID '{new_id}' is already in use")
            return {'CANCELLED'}

        target_menu = next((m for m in menus if m["id"] == old_id), None)
        if not target_menu: return {'CANCELLED'}

        target_menu["id"] = new_id
        target_menu["name"] = self.new_name

        for m in menus:
            for item in m.get("items", []):
                if item.get("type") == "MENU" and item.get("menu_id") == old_id:
                    item["menu_id"] = new_id
        
        if config.get("master_menu_id") == old_id:
            config["master_menu_id"] = new_id

        kc = context.window_manager.keyconfigs.addon
        if kc:
            target_idnames = {"wm.pie_creator_call", "wm.pie_creator_stack", "wm.pie_creator_sticky", "wm.pie_creator_popup"}
            for km in kc.keymaps:
                for kmi in km.keymap_items:
                    if kmi.idname in target_idnames:
                        if getattr(kmi.properties, "menu_id", "") == old_id:
                            kmi.properties.menu_id = new_id

        save_config(config)
        bpy.ops.wm.pie_creator_reload()
        return {'FINISHED'}

class PIECREATOR_OT_RemoveMenu(bpy.types.Operator):
    """Delete this menu and its shortcut. Items pointing at it become broken links"""
    bl_idname = "wm.pie_creator_remove_menu"
    bl_label = "Remove Menu"
    menu_id: bpy.props.StringProperty()
    def execute(self, context):
        config = load_config()
        menus = config.get("menus", [])
        
        # サブメニュー参照を解除
        for m in menus:
            for item in m.get("items", []):
                if item.get("type") == "MENU" and item.get("menu_id") == self.menu_id:
                    item["menu_id"] = ""
        
        # マスターメニュー設定を解除
        if config.get("master_menu_id") == self.menu_id:
            config["master_menu_id"] = ""
            
        menus = [m for m in menus if m["id"] != self.menu_id]
        config["menus"] = menus
        save_config(config)
        bpy.ops.wm.pie_creator_reload()
        return {'FINISHED'}

class PIECREATOR_OT_AddItem(bpy.types.Operator):
    """Edit this item: label, icon, command, poll condition and property binding"""
    bl_idname = "wm.pie_creator_add_item"
    bl_label = "Edit Item"
    menu_id: bpy.props.StringProperty()
    item_index: bpy.props.IntProperty(default=-1)
    
    type: bpy.props.EnumProperty(
        items=[
            ('COMMAND', "Command", ""),
            ('PROPERTY', "Property", ""),
            ('MENU', "Submenu", ""),
            ('SNAP_PANEL', "Snap Panel", ""),
            ('SEPARATOR', "Separator", "")
        ]
    )
    label: bpy.props.StringProperty(name="Label")
    icon: bpy.props.StringProperty(name="Icon", default="NONE")
    command: bpy.props.StringProperty(name="Command")
    target_menu_id: bpy.props.StringProperty(name="Target Menu ID")
    data_path: bpy.props.StringProperty(name="Data Path")
    prop_name: bpy.props.StringProperty(name="Prop Name")
    use_slider: bpy.props.BoolProperty(name="Use Slider", default=True)
    expand: bpy.props.BoolProperty(name="Expand (Enums)", default=False)
    poll: bpy.props.StringProperty(name="Poll Condition")

    def invoke(self, context, event):
        menus = load_menus()
        menu = next((m for m in menus if m["id"] == self.menu_id), None)
        if self.item_index != -1 and menu:
            items = menu.get("items", [])
            if 0 <= self.item_index < len(items):
                it = items[self.item_index]
                self.type = it.get("type", "COMMAND")
                self.label = it.get("label", "")
                self.icon = it.get("icon", "NONE")
                self.command = it.get("command", "")
                self.target_menu_id = it.get("menu_id", "")
                self.data_path = it.get("data_path", "")
                self.prop_name = it.get("prop_name", "")
                self.use_slider = it.get("use_slider", True)
                self.expand = it.get("expand", False)
                self.poll = it.get("poll", "")
        return context.window_manager.invoke_props_dialog(self, width=400)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "type")
        if self.type != 'SEPARATOR':
            layout.prop(self, "label")
            row = layout.row(align=True)
            row.prop(self, "icon")
            row.prop_search(self, "icon", context.window_manager, "pie_creator_icons_search", text="", icon='VIEWZOOM')
            if self.type == 'COMMAND': layout.prop(self, "command")
            elif self.type == 'PROPERTY':
                layout.prop(self, "data_path"); layout.prop(self, "prop_name")
                layout.prop(self, "use_slider"); layout.prop(self, "expand")
            elif self.type == 'MENU':
                layout.prop_search(self, "target_menu_id", context.window_manager, "pie_creator_menus_search", text="Target Menu")
                op = layout.operator("wm.pie_creator_create_link_submenu", text="Create & Link Submenu")
                op.menu_id = self.menu_id; op.item_index = self.item_index; op.label = self.label or "New Submenu"; op.icon = self.icon
            layout.prop(self, "poll", icon='FILTER')

    def execute(self, context):
        menus = load_menus()
        menu = next((m for m in menus if m["id"] == self.menu_id), None)
        if not menu: return {'CANCELLED'}
        if self.type == 'MENU' and self.target_menu_id == self.menu_id:
            self.report({'ERROR'}, "A menu cannot be its own submenu"); return {'CANCELLED'}
        
        new_item = {
            "type": self.type, "label": self.label, "icon": self.icon, "command": self.command, 
            "menu_id": self.target_menu_id, "data_path": self.data_path, "prop_name": self.prop_name,
            "use_slider": self.use_slider, "expand": self.expand, "poll": self.poll
        }
        items = menu.setdefault("items", [])
        if self.item_index == -1: items.append(new_item)
        else: items[self.item_index] = new_item
        save_menus(menus); bpy.ops.wm.pie_creator_reload()
        return {'FINISHED'}

class PIECREATOR_OT_RemoveItem(bpy.types.Operator):
    """Delete this item from the menu"""
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
                save_menus(menus); bpy.ops.wm.pie_creator_reload()
        return {'FINISHED'}

class PIECREATOR_OT_ManageModes(bpy.types.Operator):
    """Choose which Blender modes this menu appears in. Leave empty to allow every mode"""
    bl_idname = "wm.pie_creator_manage_modes"
    bl_label = "Manage Modes"
    menu_id: bpy.props.StringProperty()
    mode: bpy.props.StringProperty()
    def invoke(self, context, event):
        if self.mode:
            return self.execute(context)
        return context.window_manager.invoke_props_dialog(self)
    def draw(self, context):
        layout = self.layout
        menus = load_menus()
        menu = next((m for m in menus if m["id"] == self.menu_id), None)
        if not menu: return
        active = menu.get("modes", [])
        mode_list = [
            ('OBJECT', "Object"), ('EDIT_MESH', "Mesh Edit"), ('EDIT_CURVE', "Curve Edit"),
            ('SCULPT', "Sculpt"), ('VERTEX_PAINT', "Vertex Paint"), ('WEIGHT_PAINT', "Weight Paint"),
            ('TEXTURE_PAINT', "Texture Paint"), ('POSE', "Pose")
        ]
        for m_id, name in mode_list:
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
    """Choose which editor types this menu appears in. Leave empty to allow every editor"""
    bl_idname = "wm.pie_creator_manage_areas"
    bl_label = "Manage Areas"
    menu_id: bpy.props.StringProperty()
    area_type: bpy.props.StringProperty()
    def invoke(self, context, event):
        if self.area_type:
            return self.execute(context)
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
    """Change how this menu is presented: pie, popup, dialog, stack or sticky key"""
    bl_idname = "wm.pie_creator_toggle_type"
    bl_label = "Toggle Type"
    menu_id: bpy.props.StringProperty()
    def execute(self, context):
        menus = load_menus()
        menu = next((m for m in menus if m["id"] == self.menu_id), None)
        if menu:
            types = ['PIE', 'DIALOG', 'STACK', 'STICKY', 'POPUP']
            curr = menu.get('type', 'PIE')
            menu['type'] = types[(types.index(curr) + 1) % len(types)]
            save_menus(menus); bpy.ops.wm.pie_creator_reload()
        return {'FINISHED'}

class PIECREATOR_OT_MoveMenu(bpy.types.Operator):
    """Reorder this menu within the editor list"""
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
    """Reorder this item within the menu"""
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
    """Create a copy of this menu under a new identifier"""
    bl_idname = "wm.pie_creator_duplicate_menu"
    bl_label = "Duplicate Menu"
    menu_id: bpy.props.StringProperty()
    def execute(self, context):
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
    """Fill in the label from the operator named in the command"""
    bl_idname = "wm.pie_creator_guess_label"
    bl_label = "Guess Label"
    menu_id: bpy.props.StringProperty()
    command: bpy.props.StringProperty()
    def execute(self, context):
        label = get_label_from_command(self.command)
        if label:
            context.window_manager.pie_creator_buffer_label = label
            context.window_manager.pie_creator_has_buffer = True
        return {'FINISHED'}

class PIECREATOR_OT_SetMasterMenu(bpy.types.Operator):
    """Use this menu as the fallback when no menu matches the current mode"""
    bl_idname = "wm.pie_creator_set_master_menu"
    bl_label = "Set as Master"
    menu_id: bpy.props.StringProperty()
    def execute(self, context):
        config = load_config(); config["master_menu_id"] = self.menu_id
        save_config(config); bpy.ops.wm.pie_creator_reload()
        return {'FINISHED'}

class PIECREATOR_OT_AddDeck(bpy.types.Operator):
    """Create a new deck. Decks let you swap a whole set of menus at once"""
    bl_idname = "wm.pie_creator_add_deck"
    bl_label = "Add Deck"
    name: bpy.props.StringProperty(name="Deck Name", default="New Deck")
    def invoke(self, context, event): return context.window_manager.invoke_props_dialog(self)
    def execute(self, context):
        config = load_config(); import time
        new_id = f"deck_{int(time.time())}"
        config["decks"].append({"id": new_id, "name": self.name})
        save_config(config); bpy.ops.wm.pie_creator_reload()
        return {'FINISHED'}

class PIECREATOR_OT_RemoveDeck(bpy.types.Operator):
    """Delete this deck. Menus inside it move back to the default deck"""
    bl_idname = "wm.pie_creator_remove_deck"
    bl_label = "Remove Deck"
    deck_id: bpy.props.StringProperty()
    def execute(self, context):
        config = load_config()
        for m in config.get("menus", []):
            if m.get("deck_id") == self.deck_id: m["deck_id"] = "default"
        config["decks"] = [d for d in config["decks"] if d["id"] != self.deck_id]
        if config["active_deck"] == self.deck_id: config["active_deck"] = "default"
        save_config(config); bpy.ops.wm.pie_creator_reload()
        return {'FINISHED'}

class PIECREATOR_OT_SwitchDeck(bpy.types.Operator):
    """Make this deck active, replacing the registered menus and shortcuts"""
    bl_idname = "wm.pie_creator_switch_deck"
    bl_label = "Switch Deck"
    deck_id: bpy.props.StringProperty()
    def execute(self, context):
        config = load_config(); config["active_deck"] = self.deck_id
        save_config(config); bpy.ops.wm.pie_creator_reload(); return {'FINISHED'}

class PIECREATOR_OT_MoveToDeck(bpy.types.Operator):
    """Move this menu into another deck"""
    bl_idname = "wm.pie_creator_move_to_deck"
    bl_label = "Move to Deck"
    menu_id: bpy.props.StringProperty()
    deck_id: bpy.props.StringProperty()
    def execute(self, context):
        config = load_config()
        for m in config["menus"]:
            if m["id"] == self.menu_id: m["deck_id"] = self.deck_id; break
        save_config(config); bpy.ops.wm.pie_creator_reload(); return {'FINISHED'}

class PIECREATOR_OT_PrepareLink(bpy.types.Operator):
    """Pick this menu as the child for the next link operation"""
    bl_idname = "wm.pie_creator_prepare_link"
    bl_label = "Prepare Link"
    menu_id: bpy.props.StringProperty()
    def execute(self, context):
        context.window_manager.pie_creator_linking_child_id = self.menu_id
        bpy.ops.wm.call_menu(name="PIECREATOR_MT_HierarchyLinkMenu")
        return {'FINISHED'}

class PIECREATOR_OT_LinkToParent(bpy.types.Operator):
    """Add this menu as a submenu entry of the chosen parent menu"""
    bl_idname = "wm.pie_creator_link_to_parent"
    bl_label = "Link to Parent"
    child_id: bpy.props.StringProperty()
    parent_id: bpy.props.StringProperty()
    def execute(self, context):
        menus = load_menus()
        parent = next((m for m in menus if m["id"] == self.parent_id), None)
        child = next((m for m in menus if m["id"] == self.child_id), None)
        if parent and child:
            items = parent.setdefault("items", [])
            if any(it.get("type") == "MENU" and it.get("menu_id") == self.child_id for it in items):
                self.report({'WARNING'}, "Already linked"); return {'CANCELLED'}
            items.append({"type": "MENU", "label": child["name"], "icon": 'NONE', "menu_id": self.child_id})
            save_menus(menus); bpy.ops.wm.pie_creator_reload()
        return {'FINISHED'}

class PIECREATOR_OT_UnlinkFromParent(bpy.types.Operator):
    """Remove this menu from its parent so it becomes a root menu again"""
    bl_idname = "wm.pie_creator_unlink_from_parent"
    bl_label = "Unlink from Parent"
    menu_id: bpy.props.StringProperty()
    def execute(self, context):
        menus = load_menus(); target_id = self.menu_id; found = False
        for m in menus:
            items = m.get("items", [])
            new_items = [it for it in items if not (it.get("type") == "MENU" and it.get("menu_id") == target_id)]
            if len(new_items) != len(items): m["items"] = new_items; found = True
        if found: save_menus(menus); bpy.ops.wm.pie_creator_reload()
        return {'FINISHED'}

class PIECREATOR_OT_SelectMenu(bpy.types.Operator):
    """Open this menu in the editor"""
    bl_idname = "wm.pie_creator_select_menu"
    bl_label = "Select Menu"
    menu_id: bpy.props.StringProperty()
    def execute(self, context):
        components.set_active_menu_id(context.window_manager, self.menu_id)
        return {'FINISHED'}

class PIECREATOR_OT_DuplicateItem(bpy.types.Operator):
    """Create a copy of this item in the same menu"""
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
    """Copy this item to the PieCreator clipboard"""
    bl_idname = "wm.pie_creator_copy_item"
    bl_label = "Copy Item"
    menu_id: bpy.props.StringProperty(); item_index: bpy.props.IntProperty()
    def execute(self, context):
        menus = load_menus()
        menu = next((m for m in menus if m["id"] == self.menu_id), None)
        if not menu or not (0 <= self.item_index < len(menu["items"])): return {'CANCELLED'}
        wm = context.window_manager
        import json
        wm.pie_creator_item_clipboard = json.dumps(menu["items"][self.item_index])
        wm.pie_creator_clipboard_source_menu = self.menu_id
        wm.pie_creator_clipboard_is_cut = False
        return {'FINISHED'}

class PIECREATOR_OT_CutItem(bpy.types.Operator):
    """Cut this item to the PieCreator clipboard"""
    bl_idname = "wm.pie_creator_cut_item"
    bl_label = "Cut Item"
    menu_id: bpy.props.StringProperty(); item_index: bpy.props.IntProperty()
    def execute(self, context):
        menus = load_menus()
        menu = next((m for m in menus if m["id"] == self.menu_id), None)
        if not menu or not (0 <= self.item_index < len(menu["items"])): return {'CANCELLED'}
        wm = context.window_manager
        import json
        wm.pie_creator_item_clipboard = json.dumps(menu["items"][self.item_index])
        wm.pie_creator_clipboard_source_menu = self.menu_id
        wm.pie_creator_clipboard_is_cut = True
        return {'FINISHED'}

class PIECREATOR_OT_PasteItem(bpy.types.Operator):
    """Paste the clipboard item into this menu"""
    bl_idname = "wm.pie_creator_paste_item"
    bl_label = "Paste Item"
    menu_id: bpy.props.StringProperty(); item_index: bpy.props.IntProperty(default=-1)
    def execute(self, context):
        wm = context.window_manager
        if not wm.pie_creator_item_clipboard: return {'CANCELLED'}
        import json
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
    """Add the captured command to this menu"""
    bl_idname = "wm.pie_creator_add_to_menu"
    bl_label = "Add to Menu"
    menu_id: bpy.props.StringProperty()
    def execute(self, context):
        wm = context.window_manager
        target_op = context.button_operator if hasattr(context, "button_operator") and context.button_operator else (wm.operators[-1] if wm.operators else None)
        if target_op and "pie_creator" in getattr(target_op, "bl_idname", "").lower() and len(wm.operators)>1: target_op = wm.operators[-2]
        if not target_op: return {'CANCELLED'}
        from .core import get_op_command, get_op_label
        cmd = get_op_command(target_op); label = get_op_label(target_op)
        menus = load_menus()
        menu = next((m for m in menus if m["id"] == self.menu_id), None)
        if menu:
            menu["items"].append({"type": "COMMAND", "label": label, "command": cmd, "icon": 'NONE'})
            save_menus(menus); bpy.ops.wm.pie_creator_reload()
        return {'FINISHED'}

class PIECREATOR_OT_AddBufferedToMenu(bpy.types.Operator):
    """Add the most recently captured command or property to this menu"""
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
            path = wm.pie_creator_ctx_data_path; prop = wm.pie_creator_ctx_prop_name; label = wm.pie_creator_ctx_label
            if path and prop:
                menu["items"].append({"type": "PROPERTY", "label": label, "data_path": path, "prop_name": prop, "icon": 'NONE', "use_slider": True})
        else:
            cmd = wm.pie_creator_ctx_command; label = wm.pie_creator_ctx_label
            if cmd: menu["items"].append({"type": "COMMAND", "label": label, "command": cmd, "icon": 'NONE'})
        save_menus(menus); bpy.ops.wm.pie_creator_reload()
        return {'FINISHED'}

class PIECREATOR_OT_Paste(bpy.types.Operator):
    """Paste the captured command into the menu as a new item"""
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
            else: item.update({"type": "COMMAND", "command": cmd})
            menu["items"].append(item); save_menus(menus); bpy.ops.wm.pie_creator_reload()
        return {'FINISHED'}

class PIECREATOR_OT_CreateLinkSubmenu(bpy.types.Operator):
    """Create a new menu and link it as a submenu of this one"""
    bl_idname = "wm.pie_creator_create_link_submenu"
    bl_label = "Create & Link Submenu"
    menu_id: bpy.props.StringProperty(); item_index: bpy.props.IntProperty()
    label: bpy.props.StringProperty(name="Label", default="New Submenu")
    icon: bpy.props.StringProperty(name="Icon", default="NONE")
    def execute(self, context):
        config = load_config(); menus = config.get("menus", []); d_id = config.get("active_deck", "default")
        new_id = generate_unique_id("submenu", menus)
        menus.append({"id": new_id, "name": self.label, "type": "MENU", "deck_id": d_id, "items": []})
        parent = next((m for m in menus if m["id"] == self.menu_id), None)
        if parent:
            if self.item_index == -1: parent["items"].append({"type": "MENU", "label": self.label, "icon": self.icon, "menu_id": new_id})
            else: parent["items"][self.item_index].update({"type": "MENU", "label": self.label, "icon": self.icon, "menu_id": new_id})
        save_config(config); bpy.ops.wm.pie_creator_reload(); return {'FINISHED'}

class PIECREATOR_OT_ToggleMode(bpy.types.Operator):
    """Turn this Blender mode on or off for the menu"""
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

class PIECREATOR_OT_ToggleArea(bpy.types.Operator):
    """Turn this editor type on or off for the menu"""
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

class PIECREATOR_OT_CatalogAdd(bpy.types.Operator):
    """Add this operator from the catalog to the menu"""
    bl_idname = "wm.pie_creator_catalog_add"
    bl_label = "Add to Menu"
    menu_id: bpy.props.StringProperty()
    label: bpy.props.StringProperty()
    idname: bpy.props.StringProperty()
    def execute(self, context):
        menus = load_menus()
        menu = next((m for m in menus if m["id"] == self.menu_id), None)
        if menu:
            cmd = f"bpy.ops.{self.idname}()"
            menu["items"].append({"type": "COMMAND", "label": self.label, "command": cmd, "icon": 'NONE'})
            save_menus(menus); bpy.ops.wm.pie_creator_reload()
        return {'FINISHED'}

class PIECREATOR_OT_ClearShortcut(bpy.types.Operator):
    """Clear the keyboard shortcut assigned to this menu"""
    bl_idname = "wm.pie_creator_clear_shortcut"
    bl_label = "Clear Shortcut"
    menu_id: bpy.props.StringProperty()
    is_master: bpy.props.BoolProperty(default=False)
    def execute(self, context):
        from ..storage import load_config, save_config
        config = load_config()
        menus = config.get("menus", [])
        
        kc = context.window_manager.keyconfigs.addon
        if not kc: return {'CANCELLED'}
        km = kc.keymaps.get("Window")
        if not km: return {'CANCELLED'}
        
        found = False
        if self.is_master:
            # マスターキーの情報を保存データからクリア（もしあれば）
            if "master_shortcut" in config:
                config["master_shortcut"]["type"] = 'NONE'
                save_config(config)
            
            # 実際のキーマップをクリア
            for kmi in km.keymap_items:
                if kmi.idname == "wm.pie_creator_call_master":
                    kmi.type = 'NONE'
                    found = True; break
        else:
            # 個別メニューのショートカットを保存データからクリア
            target_menu = next((m for m in menus if m["id"] == self.menu_id), None)
            if target_menu:
                if "shortcut" in target_menu:
                    target_menu["shortcut"]["type"] = 'NONE'
                    save_config(config)
            
            # 実際のキーマップをクリア
            target_idnames = {"wm.pie_creator_call", "wm.pie_creator_stack", "wm.pie_creator_sticky", "wm.pie_creator_popup"}
            for kmi in km.keymap_items:
                if kmi.idname in target_idnames:
                    try:
                        m_id = getattr(kmi.properties, "menu_id", "")
                        if m_id == self.menu_id:
                            kmi.type = 'NONE'
                            found = True; break
                    except Exception as e:
                        # menu_id を持たないキーマップ項目が混ざり得る
                        log_debug(f"Could not read keymap item {kmi.idname}: {type(e).__name__}: {e}")
                        continue
        
        # UI更新を強制
        for area in context.screen.areas: area.tag_redraw()
        # アドオン全体をリロードして整合性を保つ
        bpy.ops.wm.pie_creator_reload()
        
        return {'FINISHED'}

classes = (
    PIECREATOR_OT_ToggleCollapse,
    PIECREATOR_OT_CollapseAll,
    PIECREATOR_OT_ExpandAll,
    PIECREATOR_OT_AddMenu,
    PIECREATOR_OT_RenameMenu,
    PIECREATOR_OT_RemoveMenu,
    PIECREATOR_OT_AddItem,
    PIECREATOR_OT_RemoveItem,
    PIECREATOR_OT_ManageModes,
    PIECREATOR_OT_ToggleMode,
    PIECREATOR_OT_ManageAreas,
    PIECREATOR_OT_ToggleArea,
    PIECREATOR_OT_ToggleType,
    PIECREATOR_OT_MoveMenu,
    PIECREATOR_OT_MoveItem,
    PIECREATOR_OT_DuplicateMenu,
    PIECREATOR_OT_GuessLabel,
    PIECREATOR_OT_SetMasterMenu,
    PIECREATOR_OT_AddDeck,
    PIECREATOR_OT_RemoveDeck,
    PIECREATOR_OT_SwitchDeck,
    PIECREATOR_OT_MoveToDeck,
    PIECREATOR_OT_PrepareLink,
    PIECREATOR_OT_LinkToParent,
    PIECREATOR_OT_UnlinkFromParent,
    PIECREATOR_OT_SelectMenu,
    PIECREATOR_OT_DuplicateItem,
    PIECREATOR_OT_CopyItem,
    PIECREATOR_OT_CutItem,
    PIECREATOR_OT_PasteItem,
    PIECREATOR_OT_AddToMenu,
    PIECREATOR_OT_AddBufferedToMenu,
    PIECREATOR_OT_Paste,
    PIECREATOR_OT_CreateLinkSubmenu,
    PIECREATOR_OT_ClearShortcut,
    PIECREATOR_OT_CatalogAdd,
)
