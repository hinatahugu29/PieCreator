bl_info = {
    "name": "PieCreator V1",
    "author": "Antigravity",
    "version": (0, 1, 0),
    "blender": (4, 0, 0),
    "location": "Preferences > Addons > PieCreator V1",
    "description": "Custom Pie Menu Builder (V1)",
    "category": "Interface",
}

import bpy
from . import storage, operators, menus, ui_editor

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
    for attr in dir(bpy.types):
        if attr.startswith("PIECREATOR_MT_"):
            # 基底クラス PIECREATOR_MT_GenericPie などは除外
            if attr == "PIECREATOR_MT_GenericPie":
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
    
    # Sync search collection for UI
    wm = bpy.context.window_manager
    wm.pie_creator_menus_search.clear()
    for m in menu_data:
        # 検索リストには全メニューを表示（別デッキへの移動などのため）
        item = wm.pie_creator_menus_search.add()
        item.name = m["id"]

    # 1. 登録対象の決定
    # サブメニュー機能の整合性を保つため、デッキに関わらず全ての PIE タイプのメニュークラスを登録する
    # (アクティブなデッキ外のメニューがサブメニューとして呼ばれる可能性があるため)
    for m in menu_data:
        if m.get("type", "PIE") == "PIE":
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
        setup_keymap_item(m["id"], m.get("type", "PIE"))
    
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

def setup_keymap_item(menu_id, menu_type):
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if not kc:
        return
    
    km = kc.keymaps.get("Window")
    if not km:
        km = kc.keymaps.new(name="Window", space_type='EMPTY')
    
    # Operator id depends on type
    if menu_type == "PIE":
        idname = "wm.pie_creator_call"
    elif menu_type == "STACK":
        idname = "wm.pie_creator_stack"
    elif menu_type == "STICKY":
        idname = "wm.pie_creator_sticky"
    else:
        idname = "wm.pie_creator_call"

    # Check if already exists (and check if it's the wrong type)
    exists = False
    wrong_type_item = None
    target_idnames = {"wm.pie_creator_call", "wm.pie_creator_stack", "wm.pie_creator_sticky"}
    
    for kmi in km.keymap_items:
        # wm.pie_creator_call_master など、menu_idを持たないオペレーターはスキップ
        if kmi.idname not in target_idnames:
            continue
            
        # Same menu ID but maybe different operator
        if kmi.properties.menu_id == menu_id:
            if kmi.idname == idname:
                exists = True
                break
            else:
                wrong_type_item = kmi
    
    # If type changed, remove old one
    if wrong_type_item:
        km.keymap_items.remove(wrong_type_item)
    
    if not exists:
        kmi = km.keymap_items.new(idname, 'NONE', 'PRESS')
        kmi.properties.menu_id = menu_id

def cleanup_keymap_items(active_menu_ids):
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if not kc:
        return
    
    km = kc.keymaps.get("Window")
    if not km:
        return
    
    to_remove = []
    target_idnames = {"wm.pie_creator_call", "wm.pie_creator_stack", "wm.pie_creator_sticky"}
    for kmi in km.keymap_items:
        if kmi.idname in target_idnames:
            if kmi.properties.menu_id not in active_menu_ids:
                to_remove.append(kmi)
    
    for kmi in to_remove:
        km.keymap_items.remove(kmi)

def draw_context_menu(self, context):
    try:
        layout = self.layout
        layout.separator()
        layout.label(text="PieCreator", icon='MENU_PANEL')
        
        # 1. Capture to Buffer
        layout.operator("wm.pie_creator_capture", text="Capture for PieCreator", icon='COPYDOWN')
        
        layout.separator()
        
        # 2. Add to specific menu list
        menus_data = storage.load_menus()
        for m in menus_data:
            op = layout.operator("wm.pie_creator_add_to_menu", text=f"Add to: {m['name']}")
            op.menu_id = m['id']
    except:
        pass

def register():
    operators.register()
    ui_editor.register()
    
    # Register search property
    bpy.types.WindowManager.pie_creator_menus_search = bpy.props.CollectionProperty(type=bpy.types.PropertyGroup)
    bpy.types.WindowManager.pie_creator_icons_search = bpy.props.CollectionProperty(type=bpy.types.PropertyGroup)
    bpy.types.WindowManager.pie_creator_moving_menu_id = bpy.props.StringProperty()
    
    # Capture Buffer Properties
    bpy.types.WindowManager.pie_creator_buffer_label = bpy.props.StringProperty(name="Buffer Label")
    bpy.types.WindowManager.pie_creator_buffer_command = bpy.props.StringProperty(name="Buffer Command")
    bpy.types.WindowManager.pie_creator_buffer_icon = bpy.props.StringProperty(name="Buffer Icon")
    bpy.types.WindowManager.pie_creator_is_recording = bpy.props.BoolProperty(default=False)
    bpy.types.WindowManager.pie_creator_has_buffer = bpy.props.BoolProperty(name="Has Buffer", default=False)

    # Initialize Icon Search List
    wm = bpy.context.window_manager
    import _bpy
    try:
        # Get all built-in icons from RNA
        icon_items = _bpy.types.UILayout.bl_rna.functions['prop'].parameters['icon'].enum_items.keys()
        wm.pie_creator_icons_search.clear()
        for icon in sorted(icon_items):
            item = wm.pie_creator_icons_search.add()
            item.name = icon
    except:
        pass

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
    from .operators import macro_recorder_timer
    if bpy.app.timers.is_registered(macro_recorder_timer):
        bpy.app.timers.unregister(macro_recorder_timer)

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
    operators.unregister()

if __name__ == "__main__":
    register()
