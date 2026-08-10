import json
import os
import bpy

def get_config_path():
    config_dir = bpy.utils.user_resource('CONFIG', path='pie_creator_hud', create=True)
    return os.path.join(config_dir, "hud_config.json")

def load_config():
    path = get_config_path()
    if not os.path.exists(path):
        default_config = {
            "modules": [
                {
                    "name": "Quick Tools",
                    "type": "RADIAL",
                    "color": [0.1, 0.4, 0.8, 0.7],
                    "shortcut_key": "H",
                    "shortcut_ctrl": True,
                    "shortcut_shift": True,
                    "items": [
                        {"label": "Search", "icon": "VIEWZOOM", "command": "bpy.ops.wm.search_menu()"},
                        {"label": "Save", "icon": "FILE_TICK", "command": "bpy.ops.wm.save_mainfile('INVOKE_DEFAULT')"}
                    ]
                }
            ]
        }
        save_config(default_config)
        return default_config
    
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"PieCreator HUD: Error loading config: {e}")
        return {"modules": []}

def save_config(data):
    path = get_config_path()
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"PieCreator HUD: Error saving config: {e}")

def sanitize_command(command):
    if not command: return ""
    return command.strip()
