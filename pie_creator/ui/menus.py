# SPDX-License-Identifier: GPL-3.0-or-later
import bpy
from ..storage import load_config, load_menus
from ..log import log_debug

# poll / data_path はメニューを描画するたびに評価される。パイメニューは
# 頻繁に再描画されるので、compile 済みのコードオブジェクトを使い回す。
# 式そのものをキーにするため、項目を編集すれば自動的に別エントリになる。
_expr_cache = {}


def _compile_expr(expr):
    code = _expr_cache.get(expr)
    if code is None:
        code = compile(expr, "<piecreator>", "eval")
        _expr_cache[expr] = code
    return code


def clear_expr_cache():
    """メニュー再登録時に呼ぶ。編集で使われなくなった式を溜め込まないため。"""
    _expr_cache.clear()


def draw_menu_items(layout, items, context, is_pie=False):
    """メニュー項目を描画する。
    is_pie: Trueの場合、PIEタイプのサブメニューをクリックで新パイ展開するボタンにする。
    """
    all_menus = None
    if is_pie:
        all_menus = load_menus()
    
    for item in items:
        label = item.get("label", "No Label")
        icon = item.get("icon", "NONE")
        item_type = item.get("type", "COMMAND")
        
        poll_str = item.get("poll", "")
        if poll_str:
            try:
                allowed = eval(_compile_expr(poll_str), {"bpy": bpy, "context": context, "C": context, "D": bpy.data})
                if not allowed: continue
            except Exception as e:
                log_debug(f"poll の評価に失敗した ({label}): {poll_str}: {type(e).__name__}: {e}")
                layout.label(text=f"(Poll Error: {label})", icon='ERROR')
                continue
        
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
                    data = eval(_compile_expr(path), {"bpy": bpy, "context": context})
                    layout.prop(data, prop, text=label if label else "", icon=icon if icon != 'NONE' else 'BLANK1', slider=use_slider, expand=expand)
                except Exception as e:
                    # 描画のたびに通るので詳細ログ扱い。失敗は画面のラベルで伝わる。
                    log_debug(f"プロパティを描画できなかった: path={path!r}, prop={prop!r}: {type(e).__name__}: {e}")
                    layout.label(text=f"(Prop Error: {prop} - {type(e).__name__})", icon='ERROR')
            continue
        elif item_type == "SNAP_PANEL":
            ts = context.scene.tool_settings
            col = layout.column(align=True)
            col.label(text="Snap Target")
            grid = col.grid_flow(columns=2, align=True); grid.prop(ts, "snap_elements", expand=True)
            col.separator()
            col.label(text="Snap Target for Individual Elements")
            col.prop(ts, "use_snap_individual_elements", text="Individual Elements")
            col.separator()
            col.prop(ts, "use_snap_absolute_grid")
            col.prop(ts, "use_snap_align_rotation")
            col.prop(ts, "use_snap_backface_culling")
            col.separator()
            col.label(text="Affect")
            row = col.row(align=True); row.prop(ts, "snap_target", expand=True)
            if hasattr(ts, "snap_rotation_step"):
                col.separator(); col.label(text="Rotation Increment")
                col.prop(ts, "snap_rotation_step", text="")
            continue
        elif item_type == "MENU":
            sub_id = item.get("menu_id", "")
            if sub_id:
                menu_idname = f"PIECREATOR_MT_{sub_id}"
                if not hasattr(bpy.types, menu_idname):
                    layout.label(text=f"{label} (Broken Link: {sub_id})", icon='ERROR'); continue
                op = layout.operator("wm.pie_creator_call", text=label, icon=icon if icon != 'NONE' else 'BLANK1')
                op.menu_id = sub_id; continue
            else: layout.label(text=f"{label} (No ID)", icon='ERROR')
            continue
        else: # COMMAND
            command = item.get("command", "")
            valid_icon = icon if (icon and icon != "") else 'NONE'
            op_row = layout.operator("wm.pie_creator_exec", text=label, icon=valid_icon if valid_icon != 'NONE' else 'BLANK1')
            op_row.command = command

class PIECREATOR_MT_GenericPie(bpy.types.Menu):
    bl_label = "Pie Creator Menu"
    menu_id = ""; modes = []; areas = []
    @classmethod
    def poll(cls, context):
        if cls.modes and context.mode not in cls.modes: return False
        if cls.areas and context.area.type not in cls.areas: return False
        return True
    def draw(self, context):
        menus = load_menus()
        menu_data = next((m for m in menus if m["id"] == self.menu_id), None)
        if not menu_data:
            self.layout.label(text=f"Menu not found: {self.menu_id}"); return
        layout = self.layout; menu_name = menu_data.get("name", "Unnamed Menu"); wm = context.window_manager
        is_top_level_pie = (menu_data["type"] == "PIE" and hasattr(wm, "pie_creator_active_pie_id") and wm.pie_creator_active_pie_id == self.menu_id)
        if is_top_level_pie:
            pie = layout.menu_pie(); draw_menu_items(pie, menu_data["items"], context, is_pie=True)
        elif menu_data["type"] in {"DIALOG", "POPUP"}:
            items = menu_data.get("items", []); item_count = len(items)
            if item_count > 12:
                cols = 2 if item_count <= 24 else 3
                grid = layout.grid_flow(columns=cols, even_columns=True, even_rows=False, align=True)
                draw_menu_items(grid, items, context)
            else: draw_menu_items(layout, items, context)
        elif menu_data["type"] == "MENU":
            box = layout.box(); col = box.column(align=True)
            col.label(text=menu_name, icon='MENU_PANEL'); col.separator()
            draw_menu_items(col, menu_data["items"], context)
        else:
            column = layout.column(); column.label(text=menu_name, icon='MENU_PANEL'); column.separator()
            draw_menu_items(column, menu_data["items"], context)

def create_menu_class(menu_id, label, modes=None, areas=None):
    cls_name = f"PIECREATOR_MT_{menu_id}"
    # 常に新しいクラスを作成する（登録・解除は __init__.py 側で管理）
    new_cls = type(cls_name, (PIECREATOR_MT_GenericPie,), {
        "bl_idname": cls_name, "bl_label": label, "menu_id": menu_id,
        "modes": modes if modes is not None else [], "areas": areas if areas is not None else []
    })
    return new_cls

class PIECREATOR_MT_DeckSwitchMenu(bpy.types.Menu):
    bl_label = "Switch Deck"
    bl_idname = "PIECREATOR_MT_DeckSwitchMenu"
    def draw(self, context):
        layout = self.layout; config = load_config()
        for d in config["decks"]:
            op = layout.operator("wm.pie_creator_switch_deck", text=d["name"])
            op.deck_id = d["id"]

class PIECREATOR_MT_MoveToDeckMenu(bpy.types.Menu):
    bl_label = "Move to Deck"
    bl_idname = "PIECREATOR_MT_MoveToDeckMenu"
    def draw(self, context):
        layout = self.layout; config = load_config()
        menu_id = context.window_manager.pie_creator_moving_menu_id
        for d in config["decks"]:
            op = layout.operator("wm.pie_creator_move_to_deck", text=d["name"])
            op.menu_id = menu_id; op.deck_id = d["id"]

class PIECREATOR_MT_HierarchyLinkMenu(bpy.types.Menu):
    bl_label = "Link to Menu"
    bl_idname = "PIECREATOR_MT_HierarchyLinkMenu"
    def draw(self, context):
        layout = self.layout; menus = load_menus()
        child_id = context.window_manager.pie_creator_linking_child_id
        for m in menus:
            if m["id"] == child_id: continue
            op = layout.operator("wm.pie_creator_link_to_parent", text=m["name"])
            op.child_id = child_id; op.parent_id = m["id"]

class PIECREATOR_MT_MenuManageMenu(bpy.types.Menu):
    bl_label = "Manage Menu"
    bl_idname = "PIECREATOR_MT_MenuManageMenu"
    def draw(self, context):
        layout = self.layout; menu_id = context.window_manager.pie_creator_moving_menu_id
        menus = load_menus()
        menu = next((m for m in menus if m["id"] == menu_id), None)
        if not menu: return
        layout.operator("wm.pie_creator_rename_menu", text="Rename", icon='GREASEPENCIL').menu_id = menu_id
        layout.operator("wm.pie_creator_duplicate_menu", text="Duplicate", icon='DUPLICATE').menu_id = menu_id
        layout.operator("wm.pie_creator_toggle_type", text="Change Type", icon='FILE_REFRESH').menu_id = menu_id
        layout.operator("wm.pie_creator_set_master_menu", text="Set as Master", icon='SOLO_OFF').menu_id = menu_id

class PIECREATOR_MT_ContextMenuAddList(bpy.types.Menu):
    bl_label = "Add to Menu"
    bl_idname = "PIECREATOR_MT_ContextMenuAddList"

    def draw(self, context):
        layout = self.layout
        from .. import storage
        config = storage.load_config()
        menus_data = config.get("menus", [])
        active_deck_id = config.get("active_deck", "default")
        wm = context.window_manager
        
        is_prop = wm.pie_creator_ctx_is_prop
        has_data = False
        if is_prop: has_data = bool(wm.pie_creator_ctx_data_path and wm.pie_creator_ctx_prop_name)
        else: has_data = bool(wm.pie_creator_ctx_command)
        
        if not has_data:
            layout.label(text="(No capturable item)", icon='INFO')
        else:
            layout.operator("wm.pie_creator_add_to_pool", text="Command Pool", icon='ASSET_MANAGER')
            layout.separator()
            target_name = wm.pie_creator_ctx_label if wm.pie_creator_ctx_label else "(Unnamed)"
            layout.label(text=f"Target: {target_name}", icon='MOUSE_MOVE')
            layout.separator()
        
        decks = config.get("decks", [{"id": "default", "name": "Default Deck"}])
        deck_names = {d["id"]: d["name"] for d in decks}
        if not menus_data:
            layout.label(text="No menus available"); return

        decks_with_menus = {}
        for m in menus_data:
            d_id = m.get("deck_id", "default")
            decks_with_menus.setdefault(d_id, []).append(m)
        
        deck_order = [active_deck_id] + [d for d in decks_with_menus if d != active_deck_id]
        for d_id in deck_order:
            deck_menus_list = decks_with_menus.get(d_id, [])
            if not deck_menus_list: continue
            d_name = deck_names.get(d_id, d_id)
            if len(decks_with_menus) > 1:
                layout.separator()
                marker = "● " if d_id == active_deck_id else ""
                layout.label(text=f"{marker}{d_name}", icon='COLLAPSEMENU')
            for m in deck_menus_list:
                op = layout.operator("wm.pie_creator_add_buffered_to_menu", text=m['name'])
                op.menu_id = m['id']

classes = (
    PIECREATOR_MT_DeckSwitchMenu,
    PIECREATOR_MT_MoveToDeckMenu,
    PIECREATOR_MT_HierarchyLinkMenu,
    PIECREATOR_MT_MenuManageMenu,
    PIECREATOR_MT_ContextMenuAddList,
    PIECREATOR_MT_GenericPie,
)
