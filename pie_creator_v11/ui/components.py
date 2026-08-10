import bpy

# 折りたたみ状態の管理（モジュールレベル）
collapsed_menus = set()

# タイプ別カラー＆アイコンマップ
TYPE_THEME = {
    'PIE':    {'icon': 'ANTIALIASED',      'color': (0.1, 0.5, 0.9, 1.0)}, # 青
    'DIALOG': {'icon': 'WINDOW',           'color': (1.0, 0.6, 0.1, 1.0)}, # オレンジ (確定型)
    'POPUP':  {'icon': 'MENU_PANEL',       'color': (0.1, 0.8, 0.4, 1.0)}, # 緑 (ライブ)
    'MENU':   {'icon': 'COLLAPSEMENU',     'color': (0.5, 0.5, 0.5, 1.0)}, # グレー (リスト)
    'STACK':  {'icon': 'LINENUMBERS_ON',   'color': (1.0, 0.3, 0.3, 1.0)}, # 赤
    'STICKY': {'icon': 'PINNED',           'color': (0.8, 0.2, 0.8, 1.0)}, # 紫
}

def get_clean_active_menu_id(wm):
    """prop_search のハック用: 'ID  |  NAME' 形式から ID 部分を抽出する"""
    if wm.pie_creator_active_menu_id:
        return wm.pie_creator_active_menu_id.split("  |")[0].strip()
    return ""

def set_active_menu_id(wm, menu_id, config_menus=None):
    """IDをもとに、prop_search 用の 'ID  |  NAME' 形式を作ってプロパティにセットする"""
    if not config_menus:
        from ..storage import load_menus
        config_menus = load_menus()
    for m in config_menus:
        if m["id"] == menu_id:
            wm.pie_creator_active_menu_id = f"{menu_id}  |  {m['name']}"
            return
    wm.pie_creator_active_menu_id = menu_id

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

def draw_sidebar(layout, config, context):
    """左側のナビゲーター。Menus と Library を切り替え可能"""
    wm = context.window_manager
    col = layout.column(align=True)
    row = col.row(align=True)
    row.prop(wm, "pie_creator_sidebar_tab", expand=True)
    
    if wm.pie_creator_sidebar_tab == 'MENUS':
        draw_sidebar_menus(col, config, context)
    elif wm.pie_creator_sidebar_tab == 'LIBRARY':
        draw_sidebar_library(col, config, context)
    else:
        draw_sidebar_catalog(col, config, context)

def draw_sidebar_catalog(layout, config, context):
    wm = context.window_manager
    active_menu_id = get_clean_active_menu_id(wm)
    
    layout.label(text="Operator Catalog", icon='VIEWZOOM')
    layout.prop(wm, "pie_creator_catalog_search", text="", icon='VIEWZOOM')
    
    col = layout.column(align=True)
    results = wm.pie_creator_catalog_results
    
    if not results:
        if len(wm.pie_creator_catalog_search) < 2:
            col.label(text="Enter at least 2 chars...", icon='INFO')
        else:
            col.label(text="No results found.", icon='ERROR')
        return

    for item in results:
        box = col.box()
        row = box.row(align=True)
        # 左側に名前
        row.label(text=item.name)
        # 右側に追加ボタン
        if active_menu_id:
            add_op = row.operator("wm.pie_creator_catalog_add", text="", icon='ADD')
            add_op.menu_id = active_menu_id
            add_op.label = item.name
            add_op.idname = item.idname
        else:
            row.label(text="", icon='RESTRICT_SELECT_ON')
        
        # 下段に内部IDを表示
        box.label(text=f"  {item.idname}", icon='DOCUMENTS')

def draw_sidebar_menus(layout, config, context):
    """従来のメニューリスト表示"""
    menus = config.get("menus", [])
    active_deck_id = config.get("active_deck", "default")
    wm = context.window_manager
    ordered_hierarchy = get_menu_hierarchy(menus, active_deck_id)
    
    box = layout.box()
    for i, entry in enumerate(ordered_hierarchy):
        m = menus[entry["index"]]
        level = entry["level"]
        row = box.row(align=True)
        row.scale_y = 1.1
        is_active = get_clean_active_menu_id(wm) == m["id"]
        if is_active: row.active = True
        
        prefix = ""
        if level > 0:
            is_last = True
            if i + 1 < len(ordered_hierarchy):
                if ordered_hierarchy[i+1]["level"] >= level: is_last = False
            indent = "    " * (level - 1)
            symbol = "└ " if is_last else "┝ "
            prefix = indent + symbol
        
        theme = TYPE_THEME.get(m.get('type', 'PIE'), TYPE_THEME['PIE'])
        row.alignment = 'LEFT'
        display_text = f"{prefix}{m['name']}"
        op = row.operator("wm.pie_creator_select_menu", text=display_text, icon=theme['icon'], emboss=is_active)
        op.menu_id = m['id']
        if is_active: row.label(text="", icon='TRIA_RIGHT')

def draw_sidebar_library(layout, config, context):
    """コマンドプール（倉庫）の表示とマクロ組み立て"""
    wm = context.window_manager
    pool = config.get("command_pool", [])
    menus = config.get("menus", [])
    col = layout.column(align=True)
    col.label(text="Action Library", icon='ASSET_MANAGER')
    if not menus:
        col.label(text="No menus created yet.", icon='ERROR'); return

    active_menu_id = get_clean_active_menu_id(wm)
    if not active_menu_id and menus:
        active_menu_id = menus[0]["id"]
        set_active_menu_id(wm, active_menu_id, config["menus"])

    target_box = col.box()
    t_row = target_box.row(align=True)
    t_row.label(text="Target:", icon='GREASEPENCIL')
    t_row.prop_search(wm, "pie_creator_active_menu_id", wm, "pie_creator_menus_search", text="")

    selected_indices = wm.pie_creator_pool_selections
    if selected_indices:
        col.separator()
        row = col.row()
        row.scale_y = 1.5
        op = row.operator("wm.pie_creator_pool_assemble", text="ASSEMBLE MACRO", icon='FORWARD')
        op.menu_id = active_menu_id; op.selected_indices = selected_indices
        col.separator()
    else:
        col.separator(); col.label(text="(Select parts below to assemble)", icon='INFO')

    if not pool:
        box = col.box(); box.label(text="No parts captured yet."); return

    box = col.box()
    selected_list = selected_indices.split(",") if selected_indices else []
    for i, part in enumerate(pool):
        row = box.row(align=True)
        is_selected = str(i) in selected_list
        icon = 'CHECKBOX_HLT' if is_selected else 'CHECKBOX_DEHLT'
        sel_op = row.operator("wm.pie_creator_toggle_pool_selection", text="", icon=icon, emboss=False)
        sel_op.index = i
        row.label(text=part["label"])
        if len(pool) > 1:
            mv_up = row.operator("wm.pie_creator_move_pool_item", text="", icon='TRIA_UP', emboss=False)
            mv_up.index = i; mv_up.direction = 'UP'
            mv_down = row.operator("wm.pie_creator_move_pool_item", text="", icon='TRIA_DOWN', emboss=False)
            mv_down.index = i; mv_down.direction = 'DOWN'
        rem = row.operator("wm.pie_creator_remove_from_pool", text="", icon='X', emboss=False)
        rem.index = i

def get_submenu_ids(menu):
    ids = []
    for item in menu.get("items", []):
        if item.get("type") == "MENU" and item.get("menu_id"): ids.append(item["menu_id"])
    return ids

def draw_menu_entry(layout, menu, all_menus, config, context, depth=0, drawn_ids=None):
    if drawn_ids is None: drawn_ids = set()
    menu_id = menu["id"]
    if menu_id in drawn_ids: return
    drawn_ids.add(menu_id)
    
    wm = context.window_manager
    is_active = get_clean_active_menu_id(wm) == menu_id
    is_collapsed = menu_id in collapsed_menus
    is_master = config.get("master_menu_id") == menu_id
    menu_type = menu.get('type', 'PIE')
    theme = TYPE_THEME.get(menu_type, TYPE_THEME['PIE'])
    item_count = len(menu.get('items', []))
    sub_ids = get_submenu_ids(menu)
    
    main_box = layout.box()
    header = main_box.row(align=True)
    if is_active: header.active = True
    
    if is_active: header.label(text="", icon='CHECKMARK')
    else: header.label(text="", icon='DOT')
    
    collapse_icon = 'TRIA_RIGHT' if is_collapsed else 'TRIA_DOWN'
    collapse_op = header.operator("wm.pie_creator_toggle_collapse", text="", icon=collapse_icon, emboss=False)
    collapse_op.menu_id = menu_id
    
    if is_master: header.label(text="", icon='SOLO_ON')
    
    name_op = header.operator("wm.pie_creator_select_menu", text=menu['name'], icon=theme['icon'], emboss=True, depress=is_active)
    name_op.menu_id = menu_id
    
    rename_op = header.operator("wm.pie_creator_rename_menu", text="", icon='GREASEPENCIL', emboss=False)
    rename_op.menu_id = menu_id; rename_op.new_name = menu['name']
    
    type_op = header.operator("wm.pie_creator_toggle_type", text=f"[{menu_type}]", emboss=True, depress=is_active)
    type_op.menu_id = menu_id
    header.label(text=f"({item_count})", icon='LINENUMBERS_ON')
    
    kc = context.window_manager.keyconfigs.addon
    if kc:
        km = kc.keymaps.get("Window")
        if km:
            target_idnames = {"wm.pie_creator_call", "wm.pie_creator_stack", "wm.pie_creator_sticky", "wm.pie_creator_popup"}
            for kmi in km.keymap_items:
                if kmi.idname in target_idnames and getattr(kmi.properties, "menu_id", "") == menu_id:
                    row = header.row(align=True)
                    row.prop(kmi, "type", text="", full_event=True)
                    clear_op = row.operator("wm.pie_creator_clear_shortcut", text="", icon='X', emboss=False)
                    clear_op.menu_id = menu_id
                    break
    
    header.separator(factor=0.5)
    btn_row = header.row(align=True)
    play = btn_row.operator("wm.pie_creator_call", text="", icon='PLAY')
    play.menu_id = menu_id
    link_op = btn_row.operator("wm.pie_creator_prepare_link", text="", icon='LINKED')
    link_op.menu_id = menu_id
    if depth > 0:
        unlink_op = btn_row.operator("wm.pie_creator_unlink_from_parent", text="", icon='UNLINKED')
        unlink_op.menu_id = menu_id
    btn_row.menu("PIECREATOR_MT_MenuManageMenu", text="", icon='SETTINGS')
    wm.pie_creator_moving_menu_id = menu_id 
    rem = btn_row.operator("wm.pie_creator_remove_menu", text="", icon='X')
    rem.menu_id = menu_id
    
    if is_collapsed: return
    
    box = main_box.column()
    box.separator(factor=0.2)
    
    info_row = box.row()
    info_row.scale_y = 0.7
    id_op = info_row.operator("wm.pie_creator_rename_menu", text=f"ID: {menu_id}", icon='LINKED', emboss=False)
    id_op.menu_id = menu_id; id_op.new_name = menu['name']
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
    item_col = box.column(align=True)
    
    if menu_type == 'STICKY':
        items = menu.get('items', [])
        while len(items) < 2: items.append({"label": "Action", "command": ""})
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
                    t_theme = TYPE_THEME.get(target_menu.get('type', 'PIE'), TYPE_THEME['PIE'])
                    row.label(text="", icon=t_theme['icon'])
                    label = f"\u2192 {label} ({target_menu['name']})"
                else:
                    row.label(text="", icon='ERROR')
                    label = f"\u2192 {label} (Broken: {target_name})" if target_name else f"\u2192 {label} (未リンク)"
                    link_op = row.operator("wm.pie_creator_create_link_submenu", text="Create & Link", icon='ADD')
                    link_op.menu_id = menu_id; link_op.item_index = j
            elif item_type == 'SNAP_PANEL':
                row.label(text="", icon='SNAP_ON'); label = "Snap Settings Panel"
            elif item_type == 'SEPARATOR':
                row.label(text="\u2500\u2500 separator \u2500\u2500")
                rem_item = row.operator("wm.pie_creator_remove_item", text="", icon='X')
                rem_item.menu_id = menu_id; rem_item.item_index = j; continue
            else: row.label(text="", icon='BLANK1')
            
            row.label(text=label, icon=icon if icon not in ("NONE", "") else 'BLANK1')
            if item.get('poll'): row.label(text="", icon='FILTER')
            mv_up = row.operator("wm.pie_creator_move_item", text="", icon='TRIA_UP')
            mv_up.menu_id = menu_id; mv_up.item_index = j; mv_up.direction = 'UP'
            mv_down = row.operator("wm.pie_creator_move_item", text="", icon='TRIA_DOWN')
            mv_down.menu_id = menu_id; mv_down.item_index = j; mv_down.direction = 'DOWN'
            dup = row.operator("wm.pie_creator_duplicate_item", text="", icon='DUPLICATE')
            dup.menu_id = menu_id; dup.item_index = j
            to_pool = row.operator("wm.pie_creator_add_to_pool", text="", icon='ASSET_MANAGER')
            to_pool.command = item.get('command', ''); to_pool.label = label
            copy = row.operator("wm.pie_creator_copy_item", text="", icon='COPYDOWN')
            copy.menu_id = menu_id; copy.item_index = j
            cut = row.operator("wm.pie_creator_cut_item", text="", icon='REMOVE')
            cut.menu_id = menu_id; cut.item_index = j
            if wm.pie_creator_item_clipboard:
                pst = row.operator("wm.pie_creator_paste_item", text="", icon='PASTEDOWN')
                pst.menu_id = menu_id; pst.item_index = j
            edit = row.operator("wm.pie_creator_add_item", text="", icon='PREFERENCES')
            edit.menu_id = menu_id; edit.item_index = j
            if wm.pie_creator_has_buffer:
                pst_buf = row.operator("wm.pie_creator_paste", text="", icon='PASTEDOWN')
                pst_buf.menu_id = menu_id
            rem_item = row.operator("wm.pie_creator_remove_item", text="", icon='X')
            rem_item.menu_id = menu_id; rem_item.item_index = j
        
        footer = box.row(align=True)
        add = footer.operator("wm.pie_creator_add_item", text="Add Item", icon='ADD')
        add.menu_id = menu_id
        if wm.pie_creator_has_buffer:
            pst_buf = footer.operator("wm.pie_creator_paste", text="Paste Captured", icon='PASTEDOWN')
            pst_buf.menu_id = menu_id
        if wm.pie_creator_item_clipboard:
            pst = footer.operator("wm.pie_creator_paste_item", text="Paste Item", icon='PASTEDOWN')
            pst.menu_id = menu_id; pst.item_index = -1
        m_rec = footer.operator("wm.pie_creator_macro_recorder", text="Record", icon='REC')
        m_rec.menu_id = menu_id
    
    if sub_ids:
        box.separator(factor=0.3)
        sub_header = box.row()
        sub_header.label(text="Submenus:", icon='OUTLINER_OB_GROUP_INSTANCE')
        sub_header.scale_y = 0.7
        for sub_id in sub_ids:
            sub_menu = next((m for m in all_menus if m["id"] == sub_id), None)
            if sub_menu and sub_id not in drawn_ids:
                draw_menu_entry(box, sub_menu, all_menus, config, context, depth=depth+1, drawn_ids=drawn_ids)

def draw_scrape_wizard(layout, context, wm, config):
    """一括インポート用のウィザード画面を描画"""
    box = layout.box()
    head = box.row()
    head.label(text="Bulk Import Wizard (Menu Scraping)", icon='ASSET_MANAGER')
    head.operator("wm.pie_creator_cancel_import", text="Exit Wizard", icon='X')
    split = box.split(factor=0.6)
    left = split.column()
    left.label(text="1. Select Items to Import:", icon='CHECKBOX_HLT')
    sel_row = left.row(align=True)
    sel_row.label(text=f"Total: {len(wm.pie_creator_scraped_items)} items")
    item_list_box = left.box()
    col = item_list_box.column(align=True)
    for i, item in enumerate(wm.pie_creator_scraped_items):
        r = col.row(align=True); r.prop(item, "selected", text="")
        icon = item.icon if item.icon != 'NONE' else 'BLANK1'
        r.label(text=item.label, icon=icon)
        r.label(text=f"({item.idname})", icon='DOT')
        r.label(text=item.item_type)
    right = split.column()
    right.label(text="2. Destination:", icon='FORWARD')
    dest_box = right.box()
    dest_box.label(text="Select Parent Menu:")
    dest_box.prop_search(wm, "pie_creator_active_menu_id", wm, "pie_creator_menus_search", text="")
    active_id = get_clean_active_menu_id(wm)
    active_menu = next((m for m in config.get("menus", []) if m["id"] == active_id), None)
    if active_menu: dest_box.label(text=f"Target: {active_menu['name']}", icon='CHECKMARK')
    else: dest_box.label(text="⚠ Select a menu first", icon='ERROR')
    dest_box.separator(); dest_box.separator()
    btn_row = dest_box.row()
    btn_row.enabled = bool(active_menu)
    commit = btn_row.operator("wm.pie_creator_commit_import", text="IMPORT SELECTED", icon='IMPORT')
    commit.target_menu_id = active_id
    dest_box.separator(); dest_box.label(text="Tip:", icon='INFO')
    dest_box.label(text="Imported items can be"); dest_box.label(text="reordered freely later.")
