import bpy

class MockLayout:
    """BlenderのUILayoutを模倣し、メソッド呼び出しを記録するクラス"""
    def __init__(self):
        self.items = []
        self.active_operator = None

    def operator(self, idname, text="", icon="NONE", emboss=True, depress=False, icon_value=0):
        item = {
            "type": "COMMAND",
            "idname": idname,
            "label": text,
            "icon": icon,
            "properties": {}
        }
        self.items.append(item)
        
        # プロパティ設定をキャッチするためのダミーオブジェクトを返す
        class PropertySniffer:
            def __init__(self, target_item):
                self.target_item = target_item
            def __setattr__(self, name, value):
                if name == "target_item":
                    super().__setattr__(name, value)
                else:
                    self.target_item["properties"][name] = value
            def __getattr__(self, name):
                return self # チェーン対応 (例: props.sub.val)
        
        return PropertySniffer(item)

    def menu(self, menu_id, text="", icon="NONE"):
        self.items.append({
            "type": "MENU",
            "menu_id": menu_id,
            "label": text,
            "icon": icon
        })

    def label(self, text="", icon="NONE"):
        if text: # ラベルも一応記録
            self.items.append({"type": "LABEL", "label": text, "icon": icon})

    def separator(self):
        pass

    # レイアウト構造維持のためのダミーメソッド
    def row(self, align=False): return self
    def column(self, align=False, heading=""): return self
    def box(self): return self
    def split(self, factor=0.0, align=False): return self
    def grid_flow(self, row_major=False, columns=0, even_columns=False, even_rows=False, align=False): return self

def scrape_menu(menu_idname):
    """指定されたIDのメニューをスクレイピングする"""
    print(f"\n--- Scaping Menu: {menu_idname} ---")
    
    if not hasattr(bpy.types, menu_idname):
        print(f"Error: Menu {menu_idname} not found.")
        return []
    
    menu_cls = getattr(bpy.types, menu_idname)
    mock = MockLayout()
    
    # contextのモック（必要に応じて）
    class MockContext:
        def __init__(self):
            self.area = None
            self.region = None
            self.space_data = None
            self.active_object = bpy.context.active_object
    
    try:
        # drawメソッドを呼び出す。
        # 多くのメニューは draw(self, context) のシグネチャを持つ
        menu_cls.draw(None, mock)
    except Exception as e:
        print(f"Scraping Error: {e}")
        # 一部のメニューは draw(context, layout) かもしれない（古い形式や特殊な形式）
        try:
            menu_cls.draw(MockContext(), mock)
        except:
            pass

    return mock.items

# --- テスト実行 ---
if __name__ == "__main__":
    # 例: 「追加 > メッシュ」メニュー
    target = "VIEW3D_MT_mesh_add"
    results = scrape_menu(target)
    
    for i, item in enumerate(results):
        if item["type"] == "COMMAND":
            props = f" with {item['properties']}" if item['properties'] else ""
            print(f"[{i}] {item['label']} -> {item['idname']}{props} (Icon: {item['icon']})")
        elif item["type"] == "MENU":
            print(f"[{i}] [SubMenu] {item['label']} -> {item['menu_id']}")
        else:
            print(f"[{i}] [{item['type']}] {item['label']}")
