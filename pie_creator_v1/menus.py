import bpy

def draw_menu_items(layout, items):
    for item in items:
        label = item.get("label", "No Label")
        icon = item.get("icon", "NONE")
        
        # セパレーターの場合
        if item.get("type") == "SEPARATOR":
            layout.separator()
            continue
        
        # サブメニューの場合
        if item.get("type") == "MENU":
            sub_id = item.get("menu_id", "")
            if sub_id:
                menu_idname = f"PIECREATOR_MT_{sub_id}"
                if hasattr(bpy.types, menu_idname):
                    layout.menu(menu_idname, text=label, icon=icon)
                else:
                    layout.label(text=f"{label} (Broken Link: {sub_id})", icon='ERROR')
            else:
                layout.label(text=f"{label} (No ID)", icon='ERROR')
        else:
            command = item.get("command", "")
            op_row = layout.operator("wm.pie_creator_exec", text=label, icon=icon)
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
        
        if menu_data["type"] == "PIE":
            pie = layout.menu_pie()
            draw_menu_items(pie, menu_data["items"])
        else:
            # 最上部にタイトルを表示
            column = layout.column()
            column.label(text=menu_name, icon='MENU_PANEL')
            column.separator()
            draw_menu_items(column, menu_data["items"])

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
