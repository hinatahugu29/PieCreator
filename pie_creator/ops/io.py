import bpy
import os
import json
import webbrowser
from bpy_extras.io_utils import ExportHelper, ImportHelper
from ..storage import load_config, save_config, load_menus, save_menus

# --- スクレイピング用基盤クラス ---

class PIECREATOR_ScrapedItem(bpy.types.PropertyGroup):
    label: bpy.props.StringProperty()
    idname: bpy.props.StringProperty()
    props_json: bpy.props.StringProperty()
    icon: bpy.props.StringProperty(default="NONE")
    selected: bpy.props.BoolProperty(default=True)
    item_type: bpy.props.EnumProperty(
        items=[('COMMAND', "Command", ""), ('MENU', "Menu", ""), ('LABEL', "Label", "")],
        default='COMMAND'
    )

class PropertySniffer:
    def __init__(self, target_dict): self.target_dict = target_dict
    def __setattr__(self, name, value):
        if name == "target_dict": super().__setattr__(name, value)
        else: self.target_dict[name] = value
    def __getattr__(self, name): return self

class MockLayout:
    def __init__(self, verbose=True):
        self.results = []
        self.verbose = verbose
    def operator(self, idname, text="", icon="NONE", **kwargs):
        item = {"type": "COMMAND", "idname": idname, "label": text, "icon": icon, "properties": {}}
        self.results.append(item)
        return PropertySniffer(item["properties"])
    def menu(self, menu_id, text="", icon="NONE"):
        self.results.append({"type": "MENU", "idname": menu_id, "label": text, "icon": icon})
    def label(self, text="", icon="NONE"):
        if text: self.results.append({"type": "LABEL", "label": text, "icon": icon})
    def __getattr__(self, name): return lambda *args, **kwargs: self

# --- オペレーター ---

class PIECREATOR_OT_ExportSettings(bpy.types.Operator, ExportHelper):
    bl_idname = "wm.pie_creator_export"
    bl_label = "Export Settings"
    filename_ext = ".json"
    def execute(self, context):
        config = load_config()
        with open(self.filepath, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return {'FINISHED'}

class PIECREATOR_OT_ImportSettings(bpy.types.Operator, ImportHelper):
    bl_idname = "wm.pie_creator_import"
    bl_label = "Import Settings"
    filename_ext = ".json"
    def execute(self, context):
        if os.path.exists(self.filepath):
            with open(self.filepath, 'r', encoding='utf-8') as f: data = json.load(f)
            if isinstance(data, dict) and "menus" in data:
                save_config(data); bpy.ops.wm.pie_creator_reload()
        return {'FINISHED'}

class PIECREATOR_OT_ScrapeMenu(bpy.types.Operator):
    bl_idname = "wm.pie_creator_scrape_menu"
    bl_label = "Scrape Blender Menu"
    target_id: bpy.props.StringProperty(name="Menu ID")
    def execute(self, context):
        clean_id = self.target_id.split("  |")[0].strip()
        if not hasattr(bpy.types, clean_id): return {'CANCELLED'}
        menu_cls = getattr(bpy.types, clean_id)
        mock = MockLayout()
        
        # モック環境の構築
        class MockSpaceData:
            def __init__(self, real): self.real = real
            def __getattr__(self, name): return getattr(self.real, name, 'ShaderNodeTree' if name=='tree_type' else None)
        class MockContext:
            def __init__(self, real): self.real = real
            def __getattr__(self, name):
                if name == 'space_data': return MockSpaceData(getattr(self.real, 'space_data', None))
                return getattr(self.real, name, None)
        class DummySelf:
            def __init__(self, layout): self.layout = layout
            def __getattr__(self, name):
                if name == 'node_operator':
                    return lambda l, t, tx="", ic='NONE', **kw: l.operator("node.add_node", text=tx or t, icon=ic)
                return lambda *args, **kwargs: None

        try: menu_cls.draw(DummySelf(mock), MockContext(context))
        except:
            try: menu_cls.draw(mock, MockContext(context))
            except: return {'CANCELLED'}

        wm = context.window_manager
        wm.pie_creator_scraped_items.clear()
        for item in mock.results:
            si = wm.pie_creator_scraped_items.add()
            si.item_type = item["type"]; si.idname = item["idname"]
            si.label = item["label"] if item["label"] else item["idname"]; si.icon = item["icon"]
            if "properties" in item: si.props_json = json.dumps(item["properties"])
        wm.pie_creator_is_scraping = True
        return {'FINISHED'}

class PIECREATOR_OT_CommitImport(bpy.types.Operator):
    bl_idname = "wm.pie_creator_commit_import"
    bl_label = "Import Selected Items"
    target_menu_id: bpy.props.StringProperty(name="Destination Menu")
    def execute(self, context):
        wm = context.window_manager
        selected = [i for i in wm.pie_creator_scraped_items if i.selected]
        if not selected: return {'CANCELLED'}
        menus = load_menus()
        target = next((m for m in menus if m["id"] == self.target_menu_id), None)
        if not target: return {'CANCELLED'}
        for si in selected:
            item = {"label": si.label, "icon": si.icon, "type": "COMMAND" if si.item_type=='COMMAND' else "MENU"}
            if si.item_type == 'COMMAND':
                props = json.loads(si.props_json) if si.props_json else {}
                p_str = ", ".join([f"{k}='{v}'" if isinstance(v,str) else f"{k}={repr(v)}" for k,v in props.items()])
                item["command"] = f"bpy.ops.{si.idname.replace('_OT_','.',1).lower()}({p_str})"
            else: item["menu_id"] = si.idname
            target["items"].append(item)
        save_menus(menus); bpy.ops.wm.pie_creator_reload()
        wm.pie_creator_is_scraping = False; wm.pie_creator_scraped_items.clear()
        return {'FINISHED'}

class PIECREATOR_OT_GenerateMenuHandbook(bpy.types.Operator):
    bl_idname = "wm.pie_creator_generate_handbook"
    bl_label = "Generate Menu Handbook"
    def execute(self, context):
        from .core import show_hud
        try:
            from ..tools.handbook_gen import generate_handbook
            count, path = generate_handbook(context)
            show_hud(f"Handbook Generated: {count} menus")
            self.report({'INFO'}, f"Handbook saved to: {path}")
        except Exception as e:
            self.report({'ERROR'}, f"Handbook failed: {e}")
        return {'FINISHED'}

def init_blender_menus(wm):
    """Blender の全メニュークラスをスキャンして検索用リストを初期化する"""
    wm.pie_creator_blender_menus.clear()
    menu_items = []
    
    # 全ての登録済みタイプをスキャンして Menu クラスを探す
    for attr in dir(bpy.types):
        # アドオン自身のメニューは除外（無限ループや混同を避ける）
        if attr.startswith("PIECREATOR_MT_"): continue
        
        try:
            cls = getattr(bpy.types, attr)
            # クラスであり、かつ bpy.types.Menu のサブクラスであることを確認
            if isinstance(cls, type) and issubclass(cls, bpy.types.Menu):
                # bl_label があれば使用、なければクラス名を表示
                label = getattr(cls, "bl_label", "")
                if not label:
                    label = attr
                menu_items.append(f"{attr}  |  {label}")
        except:
            # 属性アクセス等でエラーが出るクラスは無視
            continue
    
    # 読みやすいようにソートして登録
    for item_name in sorted(set(menu_items)):
        item = wm.pie_creator_blender_menus.add()
        item.name = item_name

class PIECREATOR_OT_CancelImport(bpy.types.Operator):
    bl_idname = "wm.pie_creator_cancel_import"
    bl_label = "Cancel Import"
    def execute(self, context):
        wm = context.window_manager
        wm.pie_creator_is_scraping = False
        wm.pie_creator_scraped_items.clear()
        return {'FINISHED'}

classes = (
    PIECREATOR_ScrapedItem,
    PIECREATOR_OT_ExportSettings,
    PIECREATOR_OT_ImportSettings,
    PIECREATOR_OT_ScrapeMenu,
    PIECREATOR_OT_CommitImport,
    PIECREATOR_OT_GenerateMenuHandbook,
    PIECREATOR_OT_CancelImport,
)
