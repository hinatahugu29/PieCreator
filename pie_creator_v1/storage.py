import json
import os
import bpy

def sanitize_command(command):
    """コマンドの不要なインデントや改行を整理し、Blender固有の型表現を変換する"""
    if not command: return ""
    import re
    cmd = command.strip()
    
    # Vector((...)) -> (...) のような変換
    patterns = [
        (r'Vector\(\((.*?)\)\)', r'(\1)'),
        (r'Euler\(\((.*?)\)\)', r'(\1)'),
        (r'Color\(\((.*?)\)\)', r'(\1)'),
        (r'Quaternion\(\((.*?)\)\)', r'(\1)'),
    ]
    for pat, repl in patterns:
        cmd = re.sub(pat, repl, cmd)
    
    return cmd

def get_config_path():
    import bpy
    # Blenderのユーザー設定フォルダ（User Config）内に専用フォルダを作成
    # 例: %APPDATA%\Blender Foundation\Blender\X.X\config\pie_creator\
    config_dir = bpy.utils.user_resource('CONFIG', path='pie_creator', create=True)
    new_path = os.path.join(config_dir, "menus.json")
    
    # 移行処理: アドオンフォルダ内に古いファイルがあり、かつ新しい場所にまだファイルがない場合に移動
    old_path = os.path.join(os.path.dirname(__file__), "menus.json")
    if os.path.exists(old_path) and not os.path.exists(new_path):
        try:
            import shutil
            shutil.move(old_path, new_path)
            # print(f"PieCreator: Migrated config from {old_path} to {new_path}")
        except Exception as e:
            print(f"PieCreator: Migration failed: {e}")
            
    return new_path

def load_config():
    path = get_config_path()
    if not os.path.exists(path):
        # デフォルト設定
        default_config = {
            "active_deck": "default",
            "decks": [
                {"id": "default", "name": "Default Deck"}
            ],
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
            data = json.load(f)
            
            # マイグレーション: リスト形式（旧形式）だった場合、辞書形式に変換
            if isinstance(data, list):
                new_data = {
                    "active_deck": "default",
                    "decks": [{"id": "default", "name": "Default Deck"}],
                    "menus": data
                }
                # 旧メニューに deck_id を付与
                for m in new_data["menus"]:
                    if "deck_id" not in m:
                        m["deck_id"] = "default"
                return new_data
            
            return data
    except Exception as e:
        print(f"PieCreator: Error loading config: {e}")
        # 致命的なエラー時は最小限の構成で立ち上げる
        return {
            "active_deck": "default", 
            "decks": [{"id": "default", "name": "Default Deck"}], 
            "menus": []
        }

def load_menus():
    config = load_config()
    return config.get("menus", [])

def save_config(data):
    path = get_config_path()
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def save_menus(menus_list):
    config = load_config()
    config["menus"] = menus_list
    save_config(config)

def generate_unique_id(base_str, menus):
    """
    既存のメニューのIDと被らない一意なIDを生成する。
    """
    existing_ids = {m["id"] for m in menus}
    idx = 1
    new_id = f"{base_str}_{idx}"
    while new_id in existing_ids:
        idx += 1
        new_id = f"{base_str}_{idx}"
    return new_id
