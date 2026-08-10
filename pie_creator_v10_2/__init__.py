bl_info = {
    "name": "PieCreator",
    "author": "hinata_hugu",
    "version": (0, 10, 2),
    "blender": (5, 0, 0),
    "location": "Preferences > Addons > PieCreator V10.2",
    "description": "Hybrid Nesting Menu Editor (V10.2) - Refactored Edition",
    "category": "Interface",
}

import bpy
import importlib

from . import storage, ops, ui

# リロード対応
if "storage" in locals():
    importlib.reload(storage)
    importlib.reload(ops)
    importlib.reload(ui)

dynamic_classes = []
addon_keymaps = []

def unregister_dynamic_menus():
    global dynamic_classes
    for cls in dynamic_classes:
        try: bpy.utils.unregister_class(cls)
        except: pass
    dynamic_classes.clear()
    
    # 静的メニュー以外を掃除
    static_menus = {
        "PIECREATOR_MT_GenericPie",
        "PIECREATOR_MT_DeckSwitchMenu",
        "PIECREATOR_MT_MoveToDeckMenu",
        "PIECREATOR_MT_HierarchyLinkMenu",
        "PIECREATOR_MT_MenuManageMenu",
        "PIECREATOR_MT_ContextMenuAddList"
    }
    for attr in dir(bpy.types):
        if attr.startswith("PIECREATOR_MT_"):
            if attr in static_menus: continue
            cls = getattr(bpy.types, attr)
            try: bpy.utils.unregister_class(cls)
            except: pass

def register_dynamic_menus():
    global dynamic_classes
    unregister_dynamic_menus()
    
    config = storage.load_config()
    active_deck_id = config.get("active_deck", "default")
    menu_data = config.get("menus", [])
    
    wm = bpy.context.window_manager
    wm.pie_creator_menus_search.clear()
    for m in menu_data:
        if m.get("deck_id", "default") == active_deck_id:
            item = wm.pie_creator_menus_search.add()
            item.name = f"{m['id']}  |  {m['name']}"

    for m in menu_data:
        cls = ui.menus.create_menu_class(m["id"], m["name"], m.get("modes", []), m.get("areas", []))
        try: bpy.utils.register_class(cls)
        except: pass
        if cls not in dynamic_classes: dynamic_classes.append(cls)
    
    active_menu_ids = []
    for m in menu_data:
        if m.get("deck_id", "default") != active_deck_id: continue
        active_menu_ids.append(m["id"])
        setup_keymap_item(m["id"], m.get("type", "PIE"), m.get("shortcut"))
    cleanup_keymap_items(active_menu_ids)

def setup_master_keymap():
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if not kc: return
    km = kc.keymaps.get("Window")
    if not km: km = kc.keymaps.new(name="Window", space_type='EMPTY')
    
    exists = any(kmi.idname == "wm.pie_creator_call_master" for kmi in km.keymap_items)
    if not exists:
        km.keymap_items.new("wm.pie_creator_call_master", 'X', 'PRESS', shift=True, ctrl=True)

def setup_keymap_item(menu_id, menu_type, shortcut_data=None):
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if not kc: return
    km = kc.keymaps.get("Window")
    if not km: km = kc.keymaps.new(name="Window", space_type='EMPTY')
    
    idname = {
        "PIE": "wm.pie_creator_call",
        "DIALOG": "wm.pie_creator_call",
        "STACK": "wm.pie_creator_stack",
        "STICKY": "wm.pie_creator_sticky",
        "POPUP": "wm.pie_creator_popup"
    }.get(menu_type, "wm.pie_creator_call")

    exists = False
    wrong_type_item = None
    target_idnames = {"wm.pie_creator_call", "wm.pie_creator_stack", "wm.pie_creator_sticky", "wm.pie_creator_popup"}
    old_key_props = None
    
    for kmi in km.keymap_items:
        if kmi.idname not in target_idnames: continue
        if getattr(kmi.properties, "menu_id", None) == menu_id:
            if kmi.idname == idname:
                exists = True
                if shortcut_data and shortcut_data.get("type") != 'NONE':
                    kmi.type = shortcut_data["type"]
                    kmi.value = shortcut_data.get("value", 'PRESS')
                    kmi.shift = shortcut_data.get("shift", False)
                    kmi.ctrl = shortcut_data.get("ctrl", False)
                    kmi.alt = shortcut_data.get("alt", False)
                    kmi.oskey = shortcut_data.get("oskey", False)
                    kmi.key_modifier = shortcut_data.get("key_modifier", 'NONE')
                break
            else:
                old_key_props = {
                    "type": kmi.type, "value": kmi.value, "any": kmi.any,
                    "shift": kmi.shift, "ctrl": kmi.ctrl, "alt": kmi.alt,
                    "oskey": kmi.oskey, "key_modifier": kmi.key_modifier,
                }
                wrong_type_item = kmi
    
    if wrong_type_item: km.keymap_items.remove(wrong_type_item)
    if not exists:
        if shortcut_data and shortcut_data.get("type") != 'NONE':
            kmi = km.keymap_items.new(idname, shortcut_data["type"], shortcut_data.get("value", 'PRESS'), 
                                    shift=shortcut_data.get("shift", False), ctrl=shortcut_data.get("ctrl", False), 
                                    alt=shortcut_data.get("alt", False), oskey=shortcut_data.get("oskey", False))
            kmi.key_modifier = shortcut_data.get("key_modifier", 'NONE')
        elif old_key_props:
            kmi = km.keymap_items.new(idname, old_key_props["type"], old_key_props["value"], 
                                    shift=old_key_props["shift"], ctrl=old_key_props["ctrl"], 
                                    alt=old_key_props["alt"], oskey=old_key_props["oskey"])
            kmi.any = old_key_props["any"]; kmi.key_modifier = old_key_props["key_modifier"]
        else:
            kmi = km.keymap_items.new(idname, 'NONE', 'PRESS')
        kmi.properties.menu_id = menu_id
        if menu_type == "POPUP": kmi.properties.use_dialog = False

def cleanup_keymap_items(active_menu_ids):
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if not kc: return
    km = kc.keymaps.get("Window")
    if not km: return
    to_remove = []
    target_idnames = {"wm.pie_creator_call", "wm.pie_creator_stack", "wm.pie_creator_sticky", "wm.pie_creator_popup"}
    for kmi in km.keymap_items:
        if kmi.idname in target_idnames:
            m_id = getattr(kmi.properties, "menu_id", "")
            if m_id not in active_menu_ids: to_remove.append(kmi)
    for kmi in to_remove: km.keymap_items.remove(kmi)

def draw_context_menu(self, context):
    try:
        layout = self.layout; wm = context.window_manager
        layout.separator(); layout.label(text="PieCreator", icon='MENU_PANEL')
        is_prop = bool(getattr(context, "button_prop", None))
        wm.pie_creator_ctx_is_prop = is_prop
        if is_prop:
            from .ops.core import get_prop_info
            path, prop, label = get_prop_info(context)
            wm.pie_creator_ctx_data_path = path or ""; wm.pie_creator_ctx_prop_name = prop or ""
            wm.pie_creator_ctx_label = label or ""; wm.pie_creator_ctx_command = ""
            layout.operator("wm.pie_creator_capture_prop", text="Capture Property", icon='PROPERTIES')
            layout.operator("wm.pie_creator_capture_value_as_cmd", text="Capture Value as Part", icon='ADD')
        else:
            from .ops.core import get_op_command, get_op_label
            target_op = None
            if hasattr(context, "button_operator") and context.button_operator: target_op = context.button_operator
            elif wm.operators:
                for op in reversed(wm.operators):
                    if "pie_creator" not in getattr(op, 'bl_idname', '').lower(): target_op = op; break
            if target_op:
                op_id = getattr(target_op, "bl_idname", "").lower()
                if "pie_creator" not in op_id:
                    wm.pie_creator_ctx_command = get_op_command(target_op) or ""
                    wm.pie_creator_ctx_label = get_op_label(target_op) or ""
                else: wm.pie_creator_ctx_command = ""; wm.pie_creator_ctx_label = ""
            wm.pie_creator_ctx_data_path = ""; wm.pie_creator_ctx_prop_name = ""
            layout.operator("wm.pie_creator_capture", text="Capture Operator", icon='COPYDOWN')
            layout.operator("wm.pie_creator_add_to_pool", text="Add to Pool", icon='ASSET_MANAGER')
            layout.separator(); op = layout.operator("wm.pie_creator_scrape_menu", text="Analyze Menu", icon='VIEWZOOM')
            op.target_id = wm.pie_creator_scrape_menu_id
        layout.separator()
        if storage.load_menus():
            layout.menu("PIECREATOR_MT_ContextMenuAddList", text="Add to:", icon='ADD')
    except Exception as e: print(f"PieCreator: Context menu error: {e}")

def register():
    ops.register()
    ui.register()

    wm_type = bpy.types.WindowManager
    prop_names = [
        "pie_creator_menus_search", "pie_creator_icons_search", "pie_creator_moving_menu_id",
        "pie_creator_linking_child_id", "pie_creator_active_menu_id", "pie_creator_buffer_label",
        "pie_creator_buffer_command", "pie_creator_buffer_icon", "pie_creator_is_recording",
        "pie_creator_has_buffer", "pie_creator_ctx_is_prop", "pie_creator_ctx_command",
        "pie_creator_ctx_label", "pie_creator_ctx_data_path", "pie_creator_ctx_prop_name",
        "pie_creator_active_pie_id", "pie_creator_item_clipboard", "pie_creator_clipboard_source_menu",
        "pie_creator_clipboard_is_cut", "pie_creator_sidebar_tab", "pie_creator_pool_selections",
        "pie_creator_scraped_items", "pie_creator_is_scraping", "pie_creator_scrape_menu_id",
        "pie_creator_blender_menus"
    ]
    for p in prop_names:
        if hasattr(wm_type, p):
            try: delattr(wm_type, p)
            except: pass

    from .ops.io import PIECREATOR_ScrapedItem
    wm_type.pie_creator_menus_search = bpy.props.CollectionProperty(type=bpy.types.PropertyGroup)
    wm_type.pie_creator_icons_search = bpy.props.CollectionProperty(type=bpy.types.PropertyGroup)
    wm_type.pie_creator_moving_menu_id = bpy.props.StringProperty()
    wm_type.pie_creator_linking_child_id = bpy.props.StringProperty()
    wm_type.pie_creator_active_menu_id = bpy.props.StringProperty()
    wm_type.pie_creator_buffer_label = bpy.props.StringProperty(name="Buffer Label")
    wm_type.pie_creator_buffer_command = bpy.props.StringProperty(name="Buffer Command")
    wm_type.pie_creator_buffer_icon = bpy.props.StringProperty(name="Buffer Icon")
    wm_type.pie_creator_is_recording = bpy.props.BoolProperty(default=False)
    wm_type.pie_creator_has_buffer = bpy.props.BoolProperty(name="Has Buffer", default=False)
    wm_type.pie_creator_ctx_is_prop = bpy.props.BoolProperty(default=False)
    wm_type.pie_creator_ctx_command = bpy.props.StringProperty()
    wm_type.pie_creator_ctx_label = bpy.props.StringProperty()
    wm_type.pie_creator_ctx_data_path = bpy.props.StringProperty()
    wm_type.pie_creator_ctx_prop_name = bpy.props.StringProperty()
    wm_type.pie_creator_active_pie_id = bpy.props.StringProperty()
    wm_type.pie_creator_item_clipboard = bpy.props.StringProperty(name="Item Clipboard")
    wm_type.pie_creator_clipboard_source_menu = bpy.props.StringProperty()
    wm_type.pie_creator_clipboard_is_cut = bpy.props.BoolProperty(default=False)
    wm_type.pie_creator_sidebar_tab = bpy.props.EnumProperty(
        name="Tab", items=[('MENUS', "Menus", ""), ('LIBRARY', "Library", "")], default='MENUS'
    )
    wm_type.pie_creator_pool_selections = bpy.props.StringProperty(default="")
    wm_type.pie_creator_scraped_items = bpy.props.CollectionProperty(type=PIECREATOR_ScrapedItem)
    wm_type.pie_creator_is_scraping = bpy.props.BoolProperty(default=False)
    wm_type.pie_creator_scrape_menu_id = bpy.props.StringProperty(name="Menu ID", default="VIEW3D_MT_mesh_add")
    wm_type.pie_creator_blender_menus = bpy.props.CollectionProperty(type=bpy.types.PropertyGroup)

    wm = bpy.context.window_manager
    
    # 1. アイコン検索用のリスト初期化（低レベル RNA アクセス）
    try:
        wm.pie_creator_icons_search.clear()
        # 標準的な UILayout.prop の 'icon' パラメータから列挙型を取得
        icon_items = []
        try:
            # 可能な限り標準的な API で試行
            icon_items = bpy.types.UILayout.bl_rna.functions['prop'].parameters['icon'].enum_items.keys()
        except:
            # フォールバック: 低レベル _bpy (Blender バージョンにより構造が異なる可能性がある)
            try:
                import _bpy
                icon_items = _bpy.types.UILayout.bl_rna.functions['prop'].parameters['icon'].enum_items.keys()
            except: pass
        
        if icon_items:
            for icon in sorted(icon_items):
                wm.pie_creator_icons_search.add().name = icon
    except Exception as e:
        print(f"PieCreator: Icon init error (skipped): {e}")

    # 2. Blender 標準メニューの検索用リスト初期化
    try:
        from .ops.io import init_blender_menus
        init_blender_menus(wm)
    except Exception as e:
        print(f"PieCreator: Blender menu search init error: {e}")

    bpy.types.UI_MT_button_context_menu.append(draw_context_menu)
    setup_master_keymap()
    register_dynamic_menus()

def unregister():
    bpy.types.UI_MT_button_context_menu.remove(draw_context_menu)
    from .ops.macro import macro_recorder_timer, _macro_on_undo_redo
    if bpy.app.timers.is_registered(macro_recorder_timer): bpy.app.timers.unregister(macro_recorder_timer)
    if _macro_on_undo_redo in bpy.app.handlers.undo_post: bpy.app.handlers.undo_post.remove(_macro_on_undo_redo)
    if _macro_on_undo_redo in bpy.app.handlers.redo_post: bpy.app.handlers.redo_post.remove(_macro_on_undo_redo)

    ui.unregister()
    ops.unregister()
    unregister_dynamic_menus()

if __name__ == "__main__":
    register()
