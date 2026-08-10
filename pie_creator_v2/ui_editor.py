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
                if target_id not in deck_menus:
                    continue  # デッキ外のメニューは階層表示に含めない
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

# 折りたたみ状態の管理（モジュールレベル）
collapsed_menus = set()

# タイプ別アイコンマップ
TYPE_ICONS = {
    'PIE': 'ANTIALIASED',
    'DIALOG': 'WINDOW',
    'STACK': 'LINENUMBERS_ON',
    'STICKY': 'PINNED',
    'POPUP': 'MENU_PANEL',
}

def get_submenu_ids(menu):
    """メニューが参照しているサブメニューIDのリストを返す"""
    ids = []
    for item in menu.get("items", []):
        if item.get("type") == "MENU" and item.get("menu_id"):
            ids.append(item["menu_id"])
    return ids

def draw_menu_entry(layout, menu, all_menus, config, context, depth=0, drawn_ids=None):
    """1つのメニューを描画し、サブメニューを再帰的にネスト表示する"""
    if drawn_ids is None:
        drawn_ids = set()
    
    menu_id = menu["id"]
    if menu_id in drawn_ids:
        return
    drawn_ids.add(menu_id)
    
    is_collapsed = menu_id in collapsed_menus
    is_master = config.get("master_menu_id") == menu_id
    menu_type = menu.get('type', 'PIE')
    type_icon = TYPE_ICONS.get(menu_type, 'BLANK1')
    item_count = len(menu.get('items', []))
    sub_ids = get_submenu_ids(menu)
    
    box = layout.box()
    
    # ====== ヘッダー行 ======
    header = box.row()
    
    collapse_icon = 'TRIA_RIGHT' if is_collapsed else 'TRIA_DOWN'
    collapse_op = header.operator("wm.pie_creator_toggle_collapse", text="", icon=collapse_icon, emboss=False)
    collapse_op.menu_id = menu_id
    
    if is_master:
        header.label(text="", icon='SOLO_ON')
    
    header.label(text=menu['name'], icon=type_icon)
    header.label(text=f"[{menu_type}] ({item_count} items)")
    
    kc = context.window_manager.keyconfigs.addon
    if kc:
        km = kc.keymaps.get("Window")
        if km:
            target_idnames = {"wm.pie_creator_call", "wm.pie_creator_stack", "wm.pie_creator_sticky", "wm.pie_creator_popup"}
            for kmi in km.keymap_items:
                if kmi.idname in target_idnames and getattr(kmi.properties, "menu_id", "") == menu_id:
                    header.prop(kmi, "type", text="", full_event=True)
                    break
    
    btn_row = header.row(align=True)
    btn_row.scale_x = 0.9
    if not is_master:
        master_op = btn_row.operator("wm.pie_creator_set_master_menu", text="", icon='SOLO_OFF')
        master_op.menu_id = menu_id
    
    # 階層管理ボタン
    link_op = btn_row.operator("wm.pie_creator_prepare_link", text="", icon='LINKED')
    link_op.menu_id = menu_id
    if depth > 0:
        unlink_op = btn_row.operator("wm.pie_creator_unlink_from_parent", text="", icon='UNLINKED')
        unlink_op.menu_id = menu_id
    
    toggle = btn_row.operator("wm.pie_creator_toggle_type", text="", icon='FILE_REFRESH')
    toggle.menu_id = menu_id
    rename = btn_row.operator("wm.pie_creator_rename_menu", text="", icon='GREASEPENCIL')
    rename.menu_id = menu_id; rename.new_name = menu['name']
    dup = btn_row.operator("wm.pie_creator_duplicate_menu", text="", icon='DUPLICATE')
    dup.menu_id = menu_id
    rem = btn_row.operator("wm.pie_creator_remove_menu", text="", icon='X')
    rem.menu_id = menu_id
    
    if is_collapsed:
        return
    
    # ====== ID + フィルター ======
    info_row = box.row()
    info_row.scale_y = 0.7
    info_row.label(text=f"ID: {menu_id}")
    mode_op = info_row.operator("wm.pie_creator_manage_modes", text="Modes", icon='RESTRICT_SELECT_OFF')
    mode_op.menu_id = menu_id
    area_op = info_row.operator("wm.pie_creator_manage_areas", text="Areas", icon='VIEW3D')
    area_op.menu_id = menu_id
    move_row = info_row.row(align=True)
    move_up = move_row.operator("wm.pie_creator_move_menu", text="", icon='TRIA_UP')
    move_up.menu_id = menu_id; move_up.direction = 'UP'
    move_down = move_row.operator("wm.pie_creator_move_menu", text="", icon='TRIA_DOWN')
    move_down.menu_id = menu_id; move_down.direction = 'DOWN'
    
    box.separator(factor=0.3)
    
    # ====== アイテム一覧 ======
    is_sticky = menu_type == 'STICKY'
    item_col = box.column(align=True)
    
    if is_sticky:
        items = menu.get('items', [])
        while len(items) < 2:
            items.append({"label": "Action", "command": ""})
        for label_prefix, i_idx in [("On Press", 0), ("On Release", 1)]:
            row = item_col.row()
            row.label(text=label_prefix, icon='DOT')
            cmd = items[i_idx].get('command', '')
            edit = row.operator("wm.pie_creator_add_item", text=cmd[:30] if cmd else "(Empty)", icon='GREASEPENCIL')
            edit.menu_id = menu_id; edit.item_index = i_idx
    else:
        for j, item in enumerate(menu.get('items', [])):
            row = item_col.row(align=True)
            icon = item.get('icon', 'BLANK1')
            item_type = item.get('type', 'COMMAND')
            label = item.get('label', 'No Label')
            
            if item_type == 'PROPERTY':
                row.label(text="", icon='RNA')
                label = f"{label if label else item.get('prop_name')}"
            elif item_type == 'MENU':
                target_name = item.get('menu_id', '')
                target_menu = next((m for m in all_menus if m["id"] == target_name), None) if target_name else None
                if target_menu:
                    t_icon = TYPE_ICONS.get(target_menu.get('type', 'PIE'), 'BLANK1')
                    row.label(text="", icon=t_icon)
                    label = f"\u2192 {label} ({target_menu['name']})"
                else:
                    row.label(text="", icon='ERROR')
                    if target_name:
                        label = f"\u2192 {label} (Broken: {target_name})"
                    else:
                        label = f"\u2192 {label} (未リンク)"
                    # 壊れた/未リンク時に Create & Link ボタンを追加
                    link_op = row.operator("wm.pie_creator_create_link_submenu", text="Create & Link", icon='ADD')
                    link_op.menu_id = menu_id
                    link_op.item_index = j
            elif item_type == 'SNAP_PANEL':
                row.label(text="", icon='SNAP_ON')
                label = "Snap Settings Panel"
            elif item_type == 'SEPARATOR':
                row.label(text="\u2500\u2500 separator \u2500\u2500")
                rem_item = row.operator("wm.pie_creator_remove_item", text="", icon='X')
                rem_item.menu_id = menu_id; rem_item.item_index = j
                continue
            else:
                row.label(text="", icon='BLANK1')
            
            row.label(text=label, icon=icon if icon not in ("NONE", "") else 'BLANK1')
            if item.get('poll'):
                row.label(text="", icon='FILTER')
            mv_up = row.operator("wm.pie_creator_move_item", text="", icon='TRIA_UP')
            mv_up.menu_id = menu_id; mv_up.item_index = j; mv_up.direction = 'UP'
            mv_down = row.operator("wm.pie_creator_move_item", text="", icon='TRIA_DOWN')
            mv_down.menu_id = menu_id; mv_down.item_index = j; mv_down.direction = 'DOWN'
            edit = row.operator("wm.pie_creator_add_item", text="", icon='PREFERENCES')
            edit.menu_id = menu_id; edit.item_index = j
            rem_item = row.operator("wm.pie_creator_remove_item", text="", icon='X')
            rem_item.menu_id = menu_id; rem_item.item_index = j
        
        footer = box.row(align=True)
        add = footer.operator("wm.pie_creator_add_item", text="Add Item", icon='ADD')
        add.menu_id = menu_id
        m_rec = footer.operator("wm.pie_creator_macro_recorder", text="Record", icon='REC')
        m_rec.menu_id = menu_id
    
    # ====== サブメニューをネスト表示 ======
    if sub_ids:
        box.separator(factor=0.3)
        sub_header = box.row()
        sub_header.label(text="Submenus:", icon='OUTLINER_OB_GROUP_INSTANCE')
        sub_header.scale_y = 0.7
        for sub_id in sub_ids:
            sub_menu = next((m for m in all_menus if m["id"] == sub_id), None)
            if sub_menu and sub_id not in drawn_ids:
                draw_menu_entry(box, sub_menu, all_menus, config, context, depth=depth+1, drawn_ids=drawn_ids)


class PIECREATOR_Preferences(bpy.types.AddonPreferences):
    bl_idname = __package__
    
    search_query: bpy.props.StringProperty(name="Search", description="Search menus by name or ID", default="")

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
        row.operator("wm.pie_creator_export", text="Export", icon='EXPORT')
        row.operator("wm.pie_creator_import", text="Import", icon='IMPORT')
        wm = context.window_manager
        row.separator()
        if not wm.pie_creator_is_recording:
            rec = row.operator("wm.pie_creator_macro_recorder", text="Macro Recorder", icon='REC')
            rec.menu_id = ""
        else:
            row.operator("wm.pie_creator_macro_recorder", text="STOP RECORDING", icon='CANCEL')
        
        layout.separator()

        # Deck Manager
        deck_box = layout.box()
        row = deck_box.row()
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
        
        ctrl_row = layout.row(align=True)
        ctrl_row.operator("wm.pie_creator_collapse_all", text="Collapse All", icon='FULLSCREEN_EXIT')
        ctrl_row.operator("wm.pie_creator_expand_all", text="Expand All", icon='FULLSCREEN_ENTER')

        q = self.search_query.lower()
        deck_menus = [m for m in menus if m.get("deck_id", "default") == active_deck_id]
        
        all_sub_ids = set()
        for m in deck_menus:
            for item in m.get("items", []):
                if item.get("type") == "MENU" and item.get("menu_id"):
                    all_sub_ids.add(item["menu_id"])
        
        root_menus = [m for m in deck_menus if m["id"] not in all_sub_ids]
        drawn_ids = set()
        
        for menu in root_menus:
            if q and q not in menu['name'].lower() and q not in menu['id'].lower():
                continue
            draw_menu_entry(layout, menu, menus, config, context, depth=0, drawn_ids=drawn_ids)
        
        for m in deck_menus:
            if m["id"] not in drawn_ids:
                if q and q not in m['name'].lower() and q not in m['id'].lower():
                    continue
                draw_menu_entry(layout, m, menus, config, context, depth=0, drawn_ids=drawn_ids)

# --- Operators ---

class PIECREATOR_OT_ToggleCollapse(bpy.types.Operator):
    bl_idname = "wm.pie_creator_toggle_collapse"
    bl_label = "Toggle Collapse"
    menu_id: bpy.props.StringProperty()
    def execute(self, context):
        if self.menu_id in collapsed_menus:
            collapsed_menus.discard(self.menu_id)
        else:
            collapsed_menus.add(self.menu_id)
        return {'FINISHED'}

class PIECREATOR_OT_CollapseAll(bpy.types.Operator):
    bl_idname = "wm.pie_creator_collapse_all"
    bl_label = "Collapse All"
    def execute(self, context):
        from .storage import load_config
        config = load_config()
        for m in config.get("menus", []):
            collapsed_menus.add(m["id"])
        return {'FINISHED'}

class PIECREATOR_OT_ExpandAll(bpy.types.Operator):
    bl_idname = "wm.pie_creator_expand_all"
    bl_label = "Expand All"
    def execute(self, context):
        collapsed_menus.clear()
        return {'FINISHED'}

class PIECREATOR_OT_AddMenu(bpy.types.Operator):
    bl_idname = "wm.pie_creator_add_menu"
    bl_label = "Add New Menu"
    type: bpy.props.EnumProperty(
        items=[
            ('PIE', "Pie Menu", ""), 
            ('DIALOG', "Dialog Menu", ""),
            ('STACK', "Stack Key", ""), 
            ('STICKY', "Sticky Key", ""),
            ('POPUP', "Popup Dialog", "")
        ]
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
    
    menu_id: bpy.props.StringProperty() # ターゲットとなる現在のID
    new_id: bpy.props.StringProperty(name="Menu ID", description="内部的な識別子（英数字・アンダースコア推奨）")
    new_name: bpy.props.StringProperty(name="Menu Name", description="表示名")

    def invoke(self, context, event):
        # 呼び出し時に現在の値を初期値としてセット
        self.new_id = self.menu_id
        # new_nameはUIから operator.new_name = ... で渡される想定だが、念のため取得
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
            layout.label(text="⚠ IDを変更すると全ての参照が更新されます", icon='ERROR')

    def execute(self, context):
        from .storage import load_config, save_config
        config = load_config()
        menus = config.get("menus", [])
        
        old_id = self.menu_id
        new_id = self.new_id
        
        if not new_id:
            self.report({'ERROR'}, "IDを空にすることはできません")
            return {'CANCELLED'}
            
        # 重複チェック（自分自身以外で）
        if new_id != old_id and any(m["id"] == new_id for m in menus):
            self.report({'ERROR'}, f"ID '{new_id}' は既に使用されています")
            return {'CANCELLED'}

        target_menu = next((m for m in menus if m["id"] == old_id), None)
        if not target_menu:
            return {'CANCELLED'}

        # 1. メニュー自身の情報を更新
        target_menu["id"] = new_id
        target_menu["name"] = self.new_name

        # 2. 他のメニューからのサブメニュー参照を更新
        ref_count = 0
        for m in menus:
            for item in m.get("items", []):
                if item.get("type") == "MENU" and item.get("menu_id") == old_id:
                    item["menu_id"] = new_id
                    ref_count += 1
        
        # 3. マスターメニューの参照を更新
        if config.get("master_menu_id") == old_id:
            config["master_menu_id"] = new_id

        # 4. キーマップ（ショートカット設定）の参照を更新
        kmi_count = 0
        kc = context.window_manager.keyconfigs.addon
        if kc:
            target_idnames = {"wm.pie_creator_call", "wm.pie_creator_stack", "wm.pie_creator_sticky", "wm.pie_creator_popup"}
            for km in kc.keymaps:
                for kmi in km.keymap_items:
                    if kmi.idname in target_idnames:
                        if getattr(kmi.properties, "menu_id", "") == old_id:
                            kmi.properties.menu_id = new_id
                            kmi_count += 1

        save_config(config)
        bpy.ops.wm.pie_creator_reload()
        
        msg = f"Renamed: {self.new_name}"
        if new_id != old_id:
            msg += f" (ID: {old_id} -> {new_id})"
        self.report({'INFO'}, msg)
        
        return {'FINISHED'}

class PIECREATOR_OT_RemoveMenu(bpy.types.Operator):
    bl_idname = "wm.pie_creator_remove_menu"
    bl_label = "Remove Menu"
    menu_id: bpy.props.StringProperty()
    def execute(self, context):
        menus = load_menus()
        # 他メニューのサブメニューリンクをクリーンアップ（Broken Link防止）
        for m in menus:
            for item in m.get("items", []):
                if item.get("type") == "MENU" and item.get("menu_id") == self.menu_id:
                    item["menu_id"] = ""
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
        items=[
            ('COMMAND', "Command", "Execute a Python command"),
            ('PROPERTY', "Property", "Draw a property slider/toggle"),
            ('MENU', "Submenu", "Open another menu"),
            ('SNAP_PANEL', "Snap Panel", "Draw Blender's Snap settings UI"),
            ('SEPARATOR', "Separator", "Draw a separator line")
        ]
    )
    label: bpy.props.StringProperty(name="Label")
    icon: bpy.props.StringProperty(name="Icon", default="NONE")
    command: bpy.props.StringProperty(name="Command")
    target_menu_id: bpy.props.StringProperty(name="Target Menu ID")
    
    # V2 新規フィールド
    data_path: bpy.props.StringProperty(name="Data Path", description="bpy.data.objects['Cube'] etc.")
    prop_name: bpy.props.StringProperty(name="Prop Name", description="Property identifier like 'location'")
    use_slider: bpy.props.BoolProperty(name="Use Slider", default=True)
    expand: bpy.props.BoolProperty(name="Expand (Enums)", default=False)
    poll: bpy.props.StringProperty(name="Poll Condition", description="Python expression for visibility")

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
                self.data_path = item.get("data_path", "")
                self.prop_name = item.get("prop_name", "")
                self.use_slider = item.get("use_slider", True)
                self.expand = item.get("expand", False)
                self.poll = item.get("poll", "")
        return context.window_manager.invoke_props_dialog(self, width=400)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "type")
        if self.type != 'SEPARATOR':
            layout.prop(self, "label")
            row = layout.row(align=True)
            row.prop(self, "icon")
            row.prop_search(self, "icon", context.window_manager, "pie_creator_icons_search", text="", icon='VIEWZOOM')
            
            layout.separator()
            if self.type == 'COMMAND':
                layout.prop(self, "command")
            elif self.type == 'PROPERTY':
                layout.prop(self, "data_path")
                layout.prop(self, "prop_name")
                layout.prop(self, "use_slider")
                layout.prop(self, "expand")
            elif self.type == 'MENU':
                layout.label(text=f"現在のメニュー: {self.menu_id}", icon='INFO')
                layout.prop_search(self, "target_menu_id", context.window_manager, "pie_creator_menus_search", text="Target Menu")
                if self.target_menu_id == self.menu_id:
                    layout.label(text="⚠ 自分自身は選択できません", icon='ERROR')
                elif not self.target_menu_id:
                    layout.label(text="↓ リンク先が無い場合は新規作成できます", icon='INFO')
                # 新規サブメニュー作成ボタン（即座に保存されます）
                create_row = layout.row()
                create_op = create_row.operator("wm.pie_creator_create_link_submenu", text="この内容で新規サブメニューを作成してリンク", icon='ADD')
                create_op.menu_id = self.menu_id
                create_op.item_index = self.item_index
                create_op.label = self.label if self.label else "New Submenu"
                create_op.icon = self.icon
            elif self.type == 'SNAP_PANEL':
                layout.label(text="Blenderのスナップ設定（ターゲット、影響、オプション）を一括表示します", icon='INFO')

            layout.separator()
            layout.prop(self, "poll", icon='FILTER')

    def execute(self, context):
        menus = load_menus()
        menu = next((m for m in menus if m["id"] == self.menu_id), None)
        if not menu: return {'CANCELLED'}
        
        # 自己参照防止
        if self.type == 'MENU' and self.target_menu_id == self.menu_id:
            self.report({'ERROR'}, "自分自身をサブメニューにすることはできません")
            return {'CANCELLED'}
        
        new_item = {
            "type": self.type, 
            "label": self.label, 
            "icon": self.icon, 
            "command": self.command, 
            "menu_id": self.target_menu_id,
            "data_path": self.data_path,
            "prop_name": self.prop_name,
            "use_slider": self.use_slider,
            "expand": self.expand,
            "poll": self.poll
        }
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
            types = ['PIE', 'DIALOG', 'STACK', 'STICKY', 'POPUP']
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
        # デッキに属するメニューを default に移動（ゴーストデッキ防止）
        for m in config.get("menus", []):
            if m.get("deck_id") == self.deck_id:
                m["deck_id"] = "default"
        config["decks"] = [d for d in config["decks"] if d["id"] != self.deck_id]
        if config["active_deck"] == self.deck_id: config["active_deck"] = "default"
        save_config(config); bpy.ops.wm.pie_creator_reload()
        self.report({'INFO'}, "デッキを削除し、メニューをDefaultに移動しました")
        return {'FINISHED'}

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

class PIECREATOR_MT_HierarchyLinkMenu(bpy.types.Menu):
    bl_label = "Link to Menu"
    bl_idname = "PIECREATOR_MT_HierarchyLinkMenu"
    def draw(self, context):
        layout = self.layout
        menus = load_menus()
        child_id = context.window_manager.pie_creator_linking_child_id
        # 検索ボックスのような感覚で全メニューをリストアップ
        for m in menus:
            if m["id"] == child_id: continue
            op = layout.operator("wm.pie_creator_link_to_parent", text=m["name"])
            op.child_id = child_id
            op.parent_id = m["id"]

class PIECREATOR_OT_PrepareLink(bpy.types.Operator):
    bl_idname = "wm.pie_creator_prepare_link"
    bl_label = "Prepare Link"
    menu_id: bpy.props.StringProperty()
    def execute(self, context):
        context.window_manager.pie_creator_linking_child_id = self.menu_id
        bpy.ops.wm.call_menu(name="PIECREATOR_MT_HierarchyLinkMenu")
        return {'FINISHED'}

class PIECREATOR_OT_LinkToParent(bpy.types.Operator):
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
            # すでにリンクがあるかチェックして重複防止
            if any(it.get("type") == "MENU" and it.get("menu_id") == self.child_id for it in items):
                self.report({'WARNING'}, f"すでに '{parent['name']}' の中にリンクが存在します")
                return {'CANCELLED'}
            
            items.append({
                "type": "MENU",
                "label": child["name"],
                "icon": 'NONE',
                "menu_id": self.child_id
            })
            save_menus(menus)
            bpy.ops.wm.pie_creator_reload()
            self.report({'INFO'}, f"'{child['name']}' を '{parent['name']}' のサブメニューにしました")
        return {'FINISHED'}

class PIECREATOR_OT_UnlinkFromParent(bpy.types.Operator):
    bl_idname = "wm.pie_creator_unlink_from_parent"
    bl_label = "Unlink from Parent"
    menu_id: bpy.props.StringProperty()
    def execute(self, context):
        menus = load_menus()
        target_id = self.menu_id
        found = False
        for m in menus:
            items = m.get("items", [])
            new_items = [it for it in items if not (it.get("type") == "MENU" and it.get("menu_id") == target_id)]
            if len(new_items) != len(items):
                m["items"] = new_items
                found = True
        
        if found:
            save_menus(menus)
            bpy.ops.wm.pie_creator_reload()
            self.report({'INFO'}, "親メニューからのリンクを解除しました")
        else:
            self.report({'WARNING'}, "親メニューが見つかりませんでした")
        return {'FINISHED'}

classes = (
    PIECREATOR_MT_DeckSwitchMenu,
    PIECREATOR_MT_MoveToDeckMenu,
    PIECREATOR_MT_HierarchyLinkMenu,
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
    PIECREATOR_OT_MoveToDeck,
    PIECREATOR_OT_ToggleCollapse,
    PIECREATOR_OT_CollapseAll,
    PIECREATOR_OT_ExpandAll,
    PIECREATOR_OT_PrepareLink,
    PIECREATOR_OT_LinkToParent,
    PIECREATOR_OT_UnlinkFromParent,
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
