bl_info = {
    "name": "PieCreator",
    "author": "hinata_hugu",
    "version": (0, 10, 1),
    "blender": (5, 0, 0),
    "location": "Preferences > Addons > PieCreator V9",
    "description": "Hybrid Nesting Menu Editor (V9) - Bulk Import & Menu Scraping Edition",
    "category": "Interface",
}

import bpy
import importlib

if "ui_editor" in locals():
    importlib.reload(storage)
    importlib.reload(ops)
    importlib.reload(menus)
    importlib.reload(ui_editor)
else:
    from . import storage, ops, menus, ui_editor

dynamic_classes = []
addon_keymaps = []

def unregister_dynamic_menus():
    global dynamic_classes
    # 保持しているリストから解除
    for cls in dynamic_classes:
        try:
            bpy.utils.unregister_class(cls)
        except:
            pass
    dynamic_classes.clear()
    
    # 保持リストから漏れている可能性のある動的クラスを bpy.types から直接掃除
    # (スクリプトのリロードなどで dynamic_classes がリセットされた場合への対策)
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
            if attr in static_menus:
                continue
            cls = getattr(bpy.types, attr)
            try:
                bpy.utils.unregister_class(cls)
            except:
                pass

def register_dynamic_menus():
    global dynamic_classes
    unregister_dynamic_menus()
    
    config = storage.load_config()
    active_deck_id = config.get("active_deck", "default")
    menu_data = config.get("menus", [])
    
    # Sync search collection for UI（アクティブデッキのメニューのみ）
    wm = bpy.context.window_manager
    wm.pie_creator_menus_search.clear()
    for m in menu_data:
        if m.get("deck_id", "default") == active_deck_id:
            item = wm.pie_creator_menus_search.add()
            item.name = f"{m['id']}  |  {m['name']}"

    # 1. 登録対象の決定
    # サブメニュー機能やダイアログ形式に対応するため、全メニューのクラスを登録する
    for m in menu_data:
        # すべてのタイプで MT クラスを作成（DIALOG, STACK等もサブメニューとして呼ばれる可能性があるため）
        cls = menus.create_menu_class(m["id"], m["name"], m.get("modes", []), m.get("areas", []))
        try:
            bpy.utils.register_class(cls)
        except:
            pass
        if cls not in dynamic_classes:
            dynamic_classes.append(cls)
    
    # 2. キーマップの構成 (こちらはアクティブなデッキのみ)
    active_menu_ids = []
    for m in menu_data:
        if m.get("deck_id", "default") != active_deck_id:
            continue
        active_menu_ids.append(m["id"])
        # shortcutデータを渡す
        setup_keymap_item(m["id"], m.get("type", "PIE"), m.get("shortcut"))
    
    # Cleanup orphaned keymap items
    cleanup_keymap_items(active_menu_ids)

def setup_master_keymap():
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if not kc:
        return
    
    km = kc.keymaps.get("Window")
    if not km:
        km = kc.keymaps.new(name="Window", space_type='EMPTY')
    
    # 既に存在するかチェック
    exists = False
    for kmi in km.keymap_items:
        if kmi.idname == "wm.pie_creator_call_master":
            exists = True
            break
    
    if not exists:
        # デフォルト: Ctrl + Shift + X
        kmi = km.keymap_items.new("wm.pie_creator_call_master", 'X', 'PRESS', shift=True, ctrl=True)

def setup_keymap_item(menu_id, menu_type, shortcut_data=None):
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if not kc:
        return
    
    km = kc.keymaps.get("Window")
    if not km:
        km = kc.keymaps.new(name="Window", space_type='EMPTY')
    
    # Operator id depends on type
    if menu_type in {"PIE", "DIALOG"}:
        idname = "wm.pie_creator_call"
    elif menu_type == "STACK":
        idname = "wm.pie_creator_stack"
    elif menu_type == "STICKY":
        idname = "wm.pie_creator_sticky"
    elif menu_type == "POPUP":
        idname = "wm.pie_creator_popup"
    else:
        idname = "wm.pie_creator_call"

    # Check if already exists (and check if it's the wrong type)
    exists = False
    wrong_type_item = None
    target_idnames = {"wm.pie_creator_call", "wm.pie_creator_stack", "wm.pie_creator_sticky", "wm.pie_creator_popup"}
    
    # キー設定の引継ぎ用変数
    old_key_props = None
    
    for kmi in km.keymap_items:
        # wm.pie_creator_call_master など、menu_idを持たないオペレーターはスキップ
        if kmi.idname not in target_idnames:
            continue
            
        # 同じメニューIDの既存設定を探す
        if kmi.properties.menu_id == menu_id:
            if kmi.idname == idname:
                exists = True
                # すでに存在する場合でも、JSONからの設定で上書き復元する（起動時のみなど）
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
                # タイプが異なる場合、現在の設定をバックアップ
                old_key_props = {
                    "type": kmi.type,
                    "value": kmi.value,
                    "any": kmi.any,
                    "shift": kmi.shift,
                    "ctrl": kmi.ctrl,
                    "alt": kmi.alt,
                    "oskey": kmi.oskey,
                    "key_modifier": kmi.key_modifier,
                }
                wrong_type_item = kmi
    
    # If type changed, remove old one
    if wrong_type_item:
        km.keymap_items.remove(wrong_type_item)
    
    if not exists:
        # 1. 引数として渡された設定があればそれを使う
        if shortcut_data and shortcut_data.get("type") != 'NONE':
            kmi = km.keymap_items.new(idname, shortcut_data["type"], shortcut_data.get("value", 'PRESS'), 
                                    shift=shortcut_data.get("shift", False), ctrl=shortcut_data.get("ctrl", False), 
                                    alt=shortcut_data.get("alt", False), oskey=shortcut_data.get("oskey", False))
            kmi.key_modifier = shortcut_data.get("key_modifier", 'NONE')
        # 2. バックアップがあればそれを使う
        elif old_key_props:
            kmi = km.keymap_items.new(idname, old_key_props["type"], old_key_props["value"], 
                                    shift=old_key_props["shift"], ctrl=old_key_props["ctrl"], 
                                    alt=old_key_props["alt"], oskey=old_key_props["oskey"])
            kmi.any = old_key_props["any"]
            kmi.key_modifier = old_key_props["key_modifier"]
        # 3. 無ければ 'NONE'
        else:
            kmi = km.keymap_items.new(idname, 'NONE', 'PRESS')
            
        kmi.properties.menu_id = menu_id
        if menu_type == "POPUP":
            kmi.properties.use_dialog = False

def cleanup_keymap_items(active_menu_ids):
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if not kc:
        return
    
    km = kc.keymaps.get("Window")
    if not km:
        return
    
    to_remove = []
    target_idnames = {"wm.pie_creator_call", "wm.pie_creator_stack", "wm.pie_creator_sticky", "wm.pie_creator_popup"}
    for kmi in km.keymap_items:
        if kmi.idname in target_idnames:
            if kmi.properties.menu_id not in active_menu_ids:
                to_remove.append(kmi)
    
    for kmi in to_remove:
        km.keymap_items.remove(kmi)

def draw_context_menu(self, context):
    try:
        layout = self.layout
        wm = context.window_manager
        layout.separator()
        layout.label(text="PieCreator", icon='MENU_PANEL')
        
        # コンテキスト情報を先にバッファに保存する
        # (サブメニューに入ると context.button_operator / button_prop が消失するため)
        is_prop = bool(getattr(context, "button_prop", None))
        wm.pie_creator_ctx_is_prop = is_prop
        
        if is_prop:
            from .ops.core import get_prop_info
            path, prop, label = get_prop_info(context)
            wm.pie_creator_ctx_data_path = path or ""
            wm.pie_creator_ctx_prop_name = prop or ""
            wm.pie_creator_ctx_label = label or ""
            wm.pie_creator_ctx_command = ""
            layout.operator("wm.pie_creator_capture_prop", text="Capture Property for PieCreator", icon='PROPERTIES')
            # V6: 値をパーツとして取得
            layout.operator("wm.pie_creator_capture_value_as_cmd", text="Capture Current Value as Part", icon='ADD')
        else:
            from .ops.core import get_op_command, get_op_label
            target_op = None
            if hasattr(context, "button_operator") and context.button_operator:
                target_op = context.button_operator
            elif wm.operators:
                # 履歴を遡って PieCreator 以外の最新のオペレーターを探す
                for op in reversed(wm.operators):
                    if "pie_creator" not in getattr(op, 'bl_idname', '').lower():
                        target_op = op
                        break
            
            if target_op:
                op_id = getattr(target_op, "bl_idname", "").lower()
                if "pie_creator" not in op_id:
                    cmd = get_op_command(target_op)
                    label = get_op_label(target_op)
                    wm.pie_creator_ctx_command = cmd or ""
                    wm.pie_creator_ctx_label = label or ""
                else:
                    wm.pie_creator_ctx_command = ""
                    wm.pie_creator_ctx_label = ""
            wm.pie_creator_ctx_data_path = ""
            wm.pie_creator_ctx_prop_name = ""
            layout.operator("wm.pie_creator_capture", text="Capture for PieCreator", icon='COPYDOWN')
            # V6: 倉庫へ追加
            layout.operator("wm.pie_creator_add_to_pool", text="Add to Command Pool", icon='ASSET_MANAGER')
            
            # --- V8: 分析 (Analyze) ボタンをコンテキストメニューへ ---
            layout.separator()
            op = layout.operator("wm.pie_creator_scrape_menu", text="Analyze with Scraper", icon='VIEWZOOM')
            # 現在 Scraper 欄にセットされている ID を対象にする
            op.target_id = wm.pie_creator_scrape_menu_id
        
        layout.separator()
        
        # 2. Add to specific menu list (Submenu化)
        menus_data = storage.load_menus()
        if menus_data:
            # 「Add to:」という名前のメニュー項目（実際にはサブメニューの入り口）
            sub = layout.menu("PIECREATOR_MT_ContextMenuAddList", text="Add to:", icon='ADD')
    except Exception as e:
        print(f"PieCreator: Context menu error: {e}")

class PIECREATOR_MT_ContextMenuAddList(bpy.types.Menu):
    bl_label = "Add to Menu"
    bl_idname = "PIECREATOR_MT_ContextMenuAddList"

    def draw(self, context):
        layout = self.layout
        from . import storage
        config = storage.load_config()
        menus_data = config.get("menus", [])
        active_deck_id = config.get("active_deck", "default")
        wm = context.window_manager
        
        # コンテキストの種類は draw_context_menu で先に保存済み
        is_prop = wm.pie_creator_ctx_is_prop
        
        # バッファに有効なデータがあるかチェック
        has_data = False
        if is_prop:
            has_data = bool(wm.pie_creator_ctx_data_path and wm.pie_creator_ctx_prop_name)
        else:
            has_data = bool(wm.pie_creator_ctx_command)
        
        if not has_data:
            layout.label(text="(No capturable item)", icon='INFO')
        else:
            # 倉庫（Command Pool）への追加をリストの最上部に追加
            layout.operator("wm.pie_creator_add_to_pool", text="Command Pool", icon='ASSET_MANAGER')
            layout.separator()
            
            # 現在のキャプチャ対象を表示
            target_name = wm.pie_creator_ctx_label if wm.pie_creator_ctx_label else "(Unnamed)"
            layout.label(text=f"Target: {target_name}", icon='MOUSE_MOVE')
            layout.separator()
        
        # デッキ情報の取得
        decks = config.get("decks", [{"id": "default", "name": "Default Deck"}])
        deck_names = {d["id"]: d["name"] for d in decks}
        
        if not menus_data:
            layout.label(text="No menus available")
            return

        # 全デッキのメニューをデッキごとにグルーピングして表示
        decks_with_menus = {}
        for m in menus_data:
            d_id = m.get("deck_id", "default")
            decks_with_menus.setdefault(d_id, []).append(m)
        
        # アクティブデッキを先に表示
        deck_order = [active_deck_id] + [d for d in decks_with_menus if d != active_deck_id]
        
        for d_id in deck_order:
            deck_menus_list = decks_with_menus.get(d_id, [])
            if not deck_menus_list:
                continue
            
            d_name = deck_names.get(d_id, d_id)
            if len(decks_with_menus) > 1:
                # 複数デッキがある場合のみデッキ名ヘッダーを表示
                layout.separator()
                marker = "● " if d_id == active_deck_id else ""
                layout.label(text=f"{marker}{d_name}", icon='COLLAPSEMENU')
            
            for m in deck_menus_list:
                op = layout.operator("wm.pie_creator_add_buffered_to_menu", text=m['name'])
                op.menu_id = m['id']

def register():
    # 1. クラス登録を最優先で行う (PropertyGroupが先に登録されている必要があるため)
    ops.register()
    ui_editor.register()

    # 2. WindowManager プロパティの登録
    # すでに登録されている場合に del を試みることで衝突を避ける
    from .ops.io import PIECREATOR_ScrapedItem
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
        name="Tab",
        items=[('MENUS', "Menus", "メニュー管理"), ('LIBRARY', "Library", "パーツ倉庫")],
        default='MENUS'
    )
    wm_type.pie_creator_pool_selections = bpy.props.StringProperty(default="")

    wm_type.pie_creator_scraped_items = bpy.props.CollectionProperty(type=PIECREATOR_ScrapedItem)
    wm_type.pie_creator_is_scraping = bpy.props.BoolProperty(default=False)
    wm_type.pie_creator_scrape_menu_id = bpy.props.StringProperty(name="Menu ID to Scrape", default="VIEW3D_MT_mesh_add")
    wm_type.pie_creator_blender_menus = bpy.props.CollectionProperty(type=bpy.types.PropertyGroup)

    # 3. Context Menu Add List Class 登録
    if hasattr(bpy.types, "PIECREATOR_MT_ContextMenuAddList"):
        try: bpy.utils.unregister_class(getattr(bpy.types, "PIECREATOR_MT_ContextMenuAddList"))
        except: pass
    try:
        bpy.utils.register_class(PIECREATOR_MT_ContextMenuAddList)
    except Exception as e:
        print(f"PieCreator: Failed to register PIECREATOR_MT_ContextMenuAddList: {e}")
    
    # Initialize Icon/Menu Search List
    wm = bpy.context.window_manager
    import _bpy
    try:
        # 1. アイコンリストの初期化
        icon_items = _bpy.types.UILayout.bl_rna.functions['prop'].parameters['icon'].enum_items.keys()
        wm.pie_creator_icons_search.clear()
        for icon in sorted(icon_items):
            item = wm.pie_creator_icons_search.add()
            item.name = icon
            
        # 2. Blender メニューリストの初期化 (Scraper 用)
        from .ops.io import init_blender_menus
        init_blender_menus(wm)
    except Exception as e:
        print(f"PieCreator: Failed to initialize search lists: {e}")

    # Register Keymaps
    kc = wm.keyconfigs.addon
    if kc:
        km = kc.keymaps.get("Window")
        if not km:
            km = kc.keymaps.new(name="Window", space_type='EMPTY')
        if (km, None) not in addon_keymaps:
            addon_keymaps.append((km, None))

    # Register Context Menu Hook (Remove first to avoid duplicates)
    try:
        bpy.types.UI_MT_button_context_menu.remove(draw_context_menu)
    except:
        pass
    bpy.types.UI_MT_button_context_menu.append(draw_context_menu)

    setup_master_keymap()
    register_dynamic_menus()

def unregister():
    # Unregister Context Menu Hook
    bpy.types.UI_MT_button_context_menu.remove(draw_context_menu)

    # Stop Macro Timer if running
    from .ops.macro import macro_recorder_timer, _macro_on_undo_redo
    if bpy.app.timers.is_registered(macro_recorder_timer):
        bpy.app.timers.unregister(macro_recorder_timer)
    
    # Undoハンドラーのクリーンアップ
    if _macro_on_undo_redo in bpy.app.handlers.undo_post:
        bpy.app.handlers.undo_post.remove(_macro_on_undo_redo)
    if _macro_on_undo_redo in bpy.app.handlers.redo_post:
        bpy.app.handlers.redo_post.remove(_macro_on_undo_redo)

    # Unregister search property
    try:
        del bpy.types.WindowManager.pie_creator_menus_search
        del bpy.types.WindowManager.pie_creator_icons_search
        del bpy.types.WindowManager.pie_creator_moving_menu_id
        
        del bpy.types.WindowManager.pie_creator_buffer_label
        del bpy.types.WindowManager.pie_creator_buffer_command
        del bpy.types.WindowManager.pie_creator_buffer_icon
        del bpy.types.WindowManager.pie_creator_is_recording
        del bpy.types.WindowManager.pie_creator_has_buffer
        
        del bpy.types.WindowManager.pie_creator_ctx_is_prop
        del bpy.types.WindowManager.pie_creator_ctx_command
        del bpy.types.WindowManager.pie_creator_ctx_label
        del bpy.types.WindowManager.pie_creator_ctx_data_path
        del bpy.types.WindowManager.pie_creator_ctx_prop_name
        
        del bpy.types.WindowManager.pie_creator_active_pie_id
        
        del bpy.types.WindowManager.pie_creator_item_clipboard
        del bpy.types.WindowManager.pie_creator_clipboard_source_menu
        del bpy.types.WindowManager.pie_creator_clipboard_is_cut

        del bpy.types.WindowManager.pie_creator_sidebar_tab
        del bpy.types.WindowManager.pie_creator_pool_selections

        del bpy.types.WindowManager.pie_creator_scraped_items
        del bpy.types.WindowManager.pie_creator_is_scraping
        del bpy.types.WindowManager.pie_creator_scrape_menu_id
        del bpy.types.WindowManager.pie_creator_blender_menus
    except Exception as e:
        print(f"PieCreator: Error deleting properties: {e}")

    # Unregister Keymaps
    for km, kmi in addon_keymaps:
        try:
            bpy.context.window_manager.keyconfigs.addon.keymaps.remove(km)
        except:
            pass
    addon_keymaps.clear()

    unregister_dynamic_menus()
    ui_editor.unregister()
    ops.unregister()
    try:
        bpy.utils.unregister_class(PIECREATOR_MT_ContextMenuAddList)
    except:
        pass

if __name__ == "__main__":
    register()
