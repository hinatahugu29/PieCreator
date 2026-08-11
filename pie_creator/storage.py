# SPDX-License-Identifier: GPL-3.0-or-later
import json
import os
import shutil
import bpy

from .log import log_error
# コマンド文字列の処理は bpy 非依存の command_text.py にある（単体テストのため）。
# 既存の呼び出し側がここから import しているので、そのまま再公開する。
from .command_text import (  # noqa: F401
    EXEC_CONTEXTS, ensure_exec_context, sanitize_command, format_arg,
)


def get_config_path():
    config_dir = bpy.utils.user_resource('CONFIG', path='pie_creator', create=True)
    new_path = os.path.join(config_dir, "menus.json")
    
    old_path = os.path.join(os.path.dirname(__file__), "menus.json")
    if os.path.exists(old_path) and not os.path.exists(new_path):
        try:
            shutil.move(old_path, new_path)
        except Exception as e:
            log_error(f"設定ファイルの移行に失敗した: {old_path} -> {new_path}", e)

    return new_path


def backup_config():
    """現在の設定を menus.backup.json に退避し、そのパスを返す。

    インポートは設定を丸ごと上書きするので、戻せる先を必ず1つ残しておく。
    設定がまだ無い場合は何もせず None を返す。
    """
    path = get_config_path()
    if not os.path.exists(path):
        return None
    backup_path = os.path.join(os.path.dirname(path), "menus.backup.json")
    try:
        shutil.copy2(path, backup_path)
        return backup_path
    except Exception as e:
        log_error(f"設定のバックアップに失敗した: {backup_path}", e)
        return None


def count_commands(config):
    """設定に含まれるコマンド項目の数を数える。

    インポート確認ダイアログで「いくつの実行可能コマンドを取り込むのか」を
    利用者に見せるために使う。コマンドは exec されるので、規模は伝えるべき情報。
    """
    total = 0
    for menu in config.get("menus", []):
        for item in menu.get("items", []):
            if item.get("command"):
                total += 1
    for entry in config.get("command_pool", []):
        if isinstance(entry, dict) and entry.get("command"):
            total += 1
    return total

def load_config():
    path = get_config_path()
    if not os.path.exists(path):
        default_config = {
            "active_deck": "default",
            "decks": [
                {"id": "default", "name": "Default Deck"}
            ],
            "command_pool": [],
            "menus": [
                {
                    "id": "sample_pie",
                    "name": "Sample Pie Menu",
                    "type": "PIE",
                    "deck_id": "default",
                    "modes": [],
                    "areas": [],
                    "items": [
                        {"label": "Search", "icon": "VIEWZOOM", "command": "bpy.ops.wm.search_menu()"},
                        {"label": "Save", "icon": "FILE_TICK", "command": "bpy.ops.wm.save_mainfile('INVOKE_DEFAULT')"},
                    ]
                }
            ]
        }
        save_config(default_config)
        return default_config
    
    try:
        with open(path, 'r', encoding='utf-8') as f:
            raw_text = f.read()
            data = json.loads(raw_text)
            
            if isinstance(data, list):
                data = {
                    "active_deck": "default",
                    "decks": [{"id": "default", "name": "Default Deck"}],
                    "menus": data
                }

            if "decks" not in data:
                data["decks"] = [{"id": "default", "name": "Default Deck"}]
            if "active_deck" not in data:
                data["active_deck"] = "default"
            if "command_pool" not in data:
                data["command_pool"] = []

            valid_deck_ids = {d["id"] for d in data.get("decks", [])}
            for m in data.get("menus", []):
                if m.get("deck_id", "default") not in valid_deck_ids:
                    m["deck_id"] = "default"
            
            if data.get("active_deck") not in valid_deck_ids:
                data["active_deck"] = "default"

            for m in data.get("menus", []):
                if "deck_id" not in m:
                    m["deck_id"] = "default"
                if "type" not in m:
                    m["type"] = "PIE"
                
                if "shortcut" not in m:
                    m["shortcut"] = {
                        "type": 'NONE',
                        "value": 'PRESS',
                        "shift": False,
                        "ctrl": False,
                        "alt": False,
                        "oskey": False,
                        "key_modifier": 'NONE'
                    }
                
                menu_id = m.get("id", "")
                for item in m.get("items", []):
                    if "type" not in item:
                        if "menu_id" in item and item["menu_id"]:
                            item["type"] = "MENU"
                        else:
                            item["type"] = "COMMAND"
                    
                    if item.get("type") == "MENU" and item.get("menu_id") == menu_id:
                        item["menu_id"] = ""
                    
                    if "poll" not in item:
                        item["poll"] = ""
                    if "data_path" not in item:
                        item["data_path"] = ""
                    if "prop_name" not in item:
                        item["prop_name"] = ""
                    if "use_slider" not in item:
                        item["use_slider"] = True

            migrated_text = json.dumps(data, indent=4, ensure_ascii=False)
            if migrated_text != raw_text:
                with open(path, 'w', encoding='utf-8') as fw:
                    fw.write(migrated_text)

            return data
    except Exception as e:
        log_error(f"設定の読み込みに失敗した: {path}", e)
        return {
            "active_deck": "default", 
            "decks": [{"id": "default", "name": "Default Deck"}], 
            "menus": []
        }

def sync_shortcuts_to_config(config):
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if not kc:
        return
    
    km = kc.keymaps.get("Window")
    if not km:
        return
        
    target_idnames = {"wm.pie_creator_call", "wm.pie_creator_stack", "wm.pie_creator_sticky", "wm.pie_creator_popup"}
    menu_map = {m["id"]: m for m in config.get("menus", [])}
    
    for kmi in km.keymap_items:
        if kmi.idname in target_idnames:
            m_id = getattr(kmi.properties, "menu_id", "")
            if m_id in menu_map:
                menu_map[m_id]["shortcut"] = {
                    "type": kmi.type,
                    "value": kmi.value,
                    "shift": kmi.shift,
                    "ctrl": kmi.ctrl,
                    "alt": kmi.alt,
                    "oskey": kmi.oskey,
                    "key_modifier": kmi.key_modifier
                }

def load_menus():
    config = load_config()
    return config.get("menus", [])

def save_config(data):
    try:
        sync_shortcuts_to_config(data)
    except Exception as e:
        # ショートカットの取り込みに失敗しても設定本体は保存する。
        log_error("ショートカットの同期に失敗した（設定の保存は続行する）", e)

    path = get_config_path()
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def save_menus(menus_list):
    config = load_config()
    config["menus"] = menus_list
    save_config(config)

def generate_unique_id(base_str, menus):
    existing_ids = {m["id"] for m in menus}
    idx = 1
    new_id = f"{base_str}_{idx}"
    while new_id in existing_ids:
        idx += 1
        new_id = f"{base_str}_{idx}"
    return new_id
