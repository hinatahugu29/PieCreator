# SPDX-License-Identifier: GPL-3.0-or-later
import bpy
from ..log import ADDON_ID
from ..storage import load_config
from .components import (
    draw_sidebar, draw_menu_entry, get_clean_active_menu_id, 
    get_menu_hierarchy, draw_scrape_wizard
)

class PIECREATOR_Preferences(bpy.types.AddonPreferences):
    # Extensions 形式では __package__ が "bl_ext.<repo>.pie_creator" になる。
    # 分解せずルートパッケージ名をそのまま使う（詳細は log.ADDON_ID を参照）。
    bl_idname = ADDON_ID
    
    search_query: bpy.props.StringProperty(name="Search", description="Search menus by name or ID", default="")

    auto_invoke_context: bpy.props.BoolProperty(
        name="Run commands the way buttons do",
        description=(
            "Add 'INVOKE_DEFAULT' to captured bpy.ops calls, so they behave "
            "the same as clicking the button they came from. Without it, "
            "Python runs them with EXEC_DEFAULT, which skips invoke() -- file "
            "browsers, dialogs and interactive tools then do nothing. "
            "Turn this off only if it changes an existing menu for the worse; "
            "a single item can always override it by writing an explicit "
            "context in its command"
        ),
        default=True,
    )

    debug_logging: bpy.props.BoolProperty(
        name="Verbose console log",
        description=(
            "Print detailed registration and menu-resolution logs to the system "
            "console. Errors are always reported regardless of this setting; "
            "turn this on only when tracking down why a menu or command "
            "misbehaves"
        ),
        default=False,
    )

    def draw(self, context):
        layout = self.layout; config = load_config()

        opts = layout.row(align=True)
        opts.prop(self, "auto_invoke_context")
        opts.prop(self, "debug_logging")
        active_deck_id = config.get("active_deck", "default")
        menus = config.get("menus", []); decks = config.get("decks", [])
        wm = context.window_manager

        # --- Top Bar ---
        row = layout.row(align=True)
        row.operator("wm.pie_creator_reload", text="Reload", icon='FILE_REFRESH')
        row.operator("wm.pie_creator_export", text="Export", icon='EXPORT')
        row.operator("wm.pie_creator_import", text="Import", icon='IMPORT')
        row.operator("wm.pie_creator_open_designer", text="Designer", icon='WINDOW')
        row.operator("wm.pie_creator_copy_designer_data", text="Copy", icon='COPYDOWN')
        row.operator("wm.pie_creator_paste_designer_data", text="Paste", icon='PASTEDOWN')
        
        row.separator(factor=2.0); row.label(text="Scraper:", icon='VIEWZOOM')
        row.prop_search(wm, "pie_creator_scrape_menu_id", wm, "pie_creator_blender_menus", text="")
        scrape_op = row.operator("wm.pie_creator_scrape_menu", text="Analyze Menu", icon='VIEWZOOM')
        scrape_op.target_id = wm.pie_creator_scrape_menu_id
        row.operator("wm.pie_creator_generate_handbook", text="Handbook", icon='HELP')

        row.separator(factor=2.0)
        if not wm.pie_creator_is_recording:
            rec = row.operator("wm.pie_creator_macro_recorder", text="Record", icon='REC'); rec.menu_id = ""
        else: row.operator("wm.pie_creator_macro_recorder", text="STOP RECORDING", icon='CANCEL')
        
        layout.separator()
        if wm.pie_creator_is_scraping:
            draw_scrape_wizard(layout, context, wm, config); layout.separator(factor=2.0)

        split = layout.split(factor=0.25)
        sidebar_col = split.column(); draw_sidebar(sidebar_col, config, context)
        
        editor_col = split.column()
        active_id = get_clean_active_menu_id(wm)
        if active_id:
            ordered_hierarchy = get_menu_hierarchy(menus, active_deck_id)
            path_str = next((entry["path"] for entry in ordered_hierarchy if menus[entry["index"]]["id"] == active_id), "")
            if path_str:
                path_box = editor_col.box(); arrow = "\u2794"
                display_path = path_str.replace(" > ", f" {arrow} ")
                path_box.label(text=f" Location: {display_path}", icon='FILE_PARENT')
        
        deck_box = editor_col.box(); row = deck_box.row()
        row.label(text="Deck:", icon='OUTLINER_COLLECTION')
        current_deck_name = next((d["name"] for d in decks if d["id"] == active_deck_id), "Unknown")
        row.menu("PIECREATOR_MT_DeckSwitchMenu", text=current_deck_name)
        row.operator("wm.pie_creator_add_deck", text="", icon='ADD')
        if active_deck_id != "default":
            del_deck = row.operator("wm.pie_creator_remove_deck", text="", icon='X'); del_deck.deck_id = active_deck_id

        editor_col.separator()
        head_row = editor_col.row(); head_row.label(text="Master Key:", icon='KEYINGSET')
        kc = context.window_manager.keyconfigs.addon
        if kc:
            km = kc.keymaps.get("Window")
            if km:
                for kmi in km.keymap_items:
                    if kmi.idname == "wm.pie_creator_call_master":
                        row = head_row.row(align=True)
                        row.prop(kmi, "type", text="", full_event=True)
                        clear_op = row.operator("wm.pie_creator_clear_shortcut", text="", icon='X', emboss=False)
                        clear_op.is_master = True
                        break
        head_row.prop(self, "search_query", text="", icon='VIEWZOOM')
        head_row.operator("wm.pie_creator_add_menu", text="Add Menu", icon='ADD')
        
        editor_col.separator(); q = self.search_query.lower()
        deck_menus = [m for m in menus if m.get("deck_id", "default") == active_deck_id]
        all_sub_ids = set()
        for m in deck_menus:
            for item in m.get("items", []):
                if item.get("type") == "MENU" and item.get("menu_id"): all_sub_ids.add(item["menu_id"])
        
        root_menus = [m for m in deck_menus if m["id"] not in all_sub_ids]
        drawn_ids = set()
        for menu in root_menus:
            if q and q not in menu['name'].lower() and q not in menu['id'].lower(): continue
            draw_menu_entry(editor_col, menu, menus, config, context, depth=0, drawn_ids=drawn_ids)
        for m in deck_menus:
            if m["id"] not in drawn_ids:
                if q and q not in m['name'].lower() and q not in m['id'].lower(): continue
                draw_menu_entry(editor_col, m, menus, config, context, depth=0, drawn_ids=drawn_ids)
