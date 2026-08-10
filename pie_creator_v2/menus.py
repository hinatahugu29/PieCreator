import bpy

def draw_menu_items(layout, items, context, is_pie=False):
    """メニュー項目を描画する。
    is_pie: Trueの場合、PIEタイプのサブメニューをクリックで新パイ展開するボタンにする。
    """
    # PIEサブメニュー判定用にメニューデータを事前ロード
    all_menus = None
    if is_pie:
        from .storage import load_menus
        all_menus = load_menus()
    
    for item in items:
        # 先にラベル・アイコン・タイプを取得（Poll評価時のエラー表示に必要）
        label = item.get("label", "No Label")
        icon = item.get("icon", "NONE")
        item_type = item.get("type", "COMMAND")
        
        # 1. Poll (個別表示条件) の評価
        poll_str = item.get("poll", "")
        if poll_str:
            try:
                # 安全なコンテキストで評価
                allowed = eval(poll_str, {"bpy": bpy, "context": context, "C": context, "D": bpy.data})
                if not allowed: continue
            except Exception as e:
                # Poll式のエラー時は警告を表示
                layout.label(text=f"(Poll Error: {label})", icon='ERROR')
                print(f"PieCreator Poll Error: {e}")
                continue
        
        # 2. タイプ別の描画
        if item_type == "SEPARATOR":
            layout.separator()
            continue
            
        elif item_type == "PROPERTY":
            path = item.get("data_path", "")
            prop = item.get("prop_name", "")
            use_slider = item.get("use_slider", True)
            expand = item.get("expand", False)
            if path and prop:
                try:
                    # データパスからオブジェクトを取得
                    data = eval(path, {"bpy": bpy, "context": context})
                    # ラベルが空の場合はBlender標準のラベルを使用
                    layout.prop(data, prop, text=label if label else "", icon=icon if icon != 'NONE' else 'BLANK1', slider=use_slider, expand=expand)
                except Exception as e:
                    layout.label(text=f"(Prop Error: {prop})", icon='ERROR')
            continue

        elif item_type == "SNAP_PANEL":
            ts = context.scene.tool_settings
            col = layout.column(align=True)
            
            # Snap Target
            col.label(text="Snap Target")
            grid = col.grid_flow(columns=2, align=True)
            grid.prop(ts, "snap_elements", expand=True)
            
            col.separator()
            
            # Individual Elements
            col.label(text="Snap Target for Individual Elements")
            col.prop(ts, "use_snap_individual_elements", text="Individual Elements")
            # Blender 4.0+ では snap_elements_individual などがあるが、
            # 基本的な snap_elements の expand で事足りることが多い
            
            col.separator()
            
            # Options
            col.prop(ts, "use_snap_absolute_grid")
            col.prop(ts, "use_snap_align_rotation")
            col.prop(ts, "use_snap_backface_culling")
            
            col.separator()
            
            # Affect
            col.label(text="Affect")
            row = col.row(align=True)
            row.prop(ts, "snap_target", expand=True)
            
            col.separator()
            
            # Rotation Increment (もし存在すれば)
            if hasattr(ts, "snap_rotation_step"):
                col.label(text="Rotation Increment")
                col.prop(ts, "snap_rotation_step", text="")
            
            continue

        elif item_type == "MENU":
            sub_id = item.get("menu_id", "")
            if sub_id:
                menu_idname = f"PIECREATOR_MT_{sub_id}"
                if not hasattr(bpy.types, menu_idname):
                    layout.label(text=f"{label} (Broken Link: {sub_id})", icon='ERROR')
                    continue
                
                # パイメニュー内のPIEサブメニュー → クリックで新パイを展開
                if is_pie and all_menus:
                    sub_data = next((m for m in all_menus if m["id"] == sub_id), None)
                    if sub_data and sub_data.get("type") == "PIE":
                        op = layout.operator(
                            "wm.pie_creator_call",
                            text=label,
                            icon=icon if icon != 'NONE' else 'BLANK1'
                        )
                        op.menu_id = sub_id
                        continue
                
                # それ以外 → 通常のドロップダウンサブメニュー
                layout.menu(menu_idname, text=label, icon=icon if icon != 'NONE' else 'BLANK1')
            else:
                layout.label(text=f"{label} (No ID)", icon='ERROR')
            continue
            
        else: # COMMAND
            command = item.get("command", "")
            op_row = layout.operator("wm.pie_creator_exec", text=label, icon=icon if icon != 'NONE' else 'BLANK1')
            op_row.command = command

class PIECREATOR_MT_GenericPie(bpy.types.Menu):
    bl_label = "Pie Creator Menu"
    
    # クラス作成時に指定される
    menu_id = ""
    modes = []
    areas = []

    @classmethod
    def poll(cls, context):
        # 1. モードチェック
        if cls.modes:
            if context.mode not in cls.modes:
                return False
        
        # 2. エリアチェック
        if cls.areas:
            if context.area.type not in cls.areas:
                return False
                
        return True

    def draw(self, context):
        from .storage import load_menus
        menus = load_menus()
        
        # 自分のIDに一致するデータを探す
        menu_data = next((m for m in menus if m["id"] == self.menu_id), None)
        if not menu_data:
            self.layout.label(text=f"Menu not found: {self.menu_id}")
            return
        
        layout = self.layout
        menu_name = menu_data.get("name", "Unnamed Menu")
        
        # パイメニューとして描画するかの判定:
        # 直接 call_menu_pie で呼ばれたトップレベルのメニューのみ円形配置を使用する。
        # サブメニュー（layout.menu() 経由）として描画される場合はリスト形式にする。
        wm = context.window_manager
        is_top_level_pie = (
            menu_data["type"] == "PIE" and
            hasattr(wm, "pie_creator_active_pie_id") and
            wm.pie_creator_active_pie_id == self.menu_id
        )
        
        if is_top_level_pie:
            pie = layout.menu_pie()
            # is_pie=True: PIEサブメニューはクリックで新パイ展開
            draw_menu_items(pie, menu_data["items"], context, is_pie=True)
        elif menu_data["type"] == "DIALOG":
            # ポップアップダイアログ形式: ボックスで囲む
            box = layout.box()
            col = box.column(align=True)
            col.label(text=menu_name, icon='MENU_PANEL')
            col.separator()
            draw_menu_items(col, menu_data["items"], context)
        else:
            # サブメニュー / STACK / その他: リスト形式で描画
            column = layout.column()
            column.label(text=menu_name, icon='MENU_PANEL')
            column.separator()
            draw_menu_items(column, menu_data["items"], context)

# 動的にメニュークラスを作成する関数
def create_menu_class(menu_id, label, modes=None, areas=None):
    cls_name = f"PIECREATOR_MT_{menu_id}"
    
    # すでに登録されている場合はスキップ
    if hasattr(bpy.types, cls_name):
        # 既存クラスのプロパティを更新（再登録せずに済む場合）
        cls = getattr(bpy.types, cls_name)
        cls.modes = modes if modes is not None else []
        cls.areas = areas if areas is not None else []
        return cls

    # 継承して新しいクラスを作成
    new_cls = type(cls_name, (PIECREATOR_MT_GenericPie,), {
        "bl_idname": cls_name,
        "bl_label": label,
        "menu_id": menu_id,
        "modes": modes if modes is not None else [],
        "areas": areas if areas is not None else []
    })
    
    return new_cls
