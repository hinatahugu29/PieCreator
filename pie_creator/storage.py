import json
import os
import re
import bpy

# bpy.ops.foo.bar() の第1引数に置ける実行コンテキスト。
# https://docs.blender.org/api/current/bpy.ops.html
EXEC_CONTEXTS = frozenset({
    'INVOKE_DEFAULT', 'INVOKE_REGION_WIN', 'INVOKE_REGION_CHANNELS',
    'INVOKE_REGION_PREVIEW', 'INVOKE_AREA', 'INVOKE_SCREEN',
    'EXEC_DEFAULT', 'EXEC_REGION_WIN', 'EXEC_REGION_CHANNELS',
    'EXEC_REGION_PREVIEW', 'EXEC_AREA', 'EXEC_SCREEN',
})

_OPS_CALL_RE = re.compile(
    r"bpy\.ops\.[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*\s*\("
)


def ensure_exec_context(command, exec_context="INVOKE_DEFAULT"):
    """bpy.ops 呼び出しに実行コンテキストを補う。

    Python から `bpy.ops.foo.bar()` を引数なしで呼ぶと EXEC_DEFAULT になり、
    **invoke() を飛ばして execute() だけが走る。** 一方、パネルやメニューの
    ボタンが押されたときは INVOKE_DEFAULT で、invoke() から始まる。

    PieCreator はボタンから取り込んだ内容を文字列として保存して exec する
    ので、この差がそのまま落ちる。結果、invoke() に本体があるもの
    （ファイルブラウザを開く、ダイアログを出す、モーダルを開始する)が
    軒並み「押しても何も起きない」状態になっていた。

    たとえば `bpy.ops.transform.translate()` は EXEC では移動量ゼロで何も
    起きないが、INVOKE ならインタラクティブな移動が始まる。パイから呼んで
    欲しいのは後者で、それはボタンを押したときの挙動と一致する。

    invoke() を持たないオペレーターに INVOKE_DEFAULT を渡しても、Blender は
    execute() にフォールバックする。そのため一律に付けて差し支えない。

    すでに明示的な実行コンテキストが書かれている場合は触らない。利用者が
    項目エディタで `'EXEC_DEFAULT'` と書けば、それが優先される。
    """
    if not command or "bpy.ops." not in command:
        return command

    out = []
    pos = 0
    for m in _OPS_CALL_RE.finditer(command):
        out.append(command[pos:m.end()])
        pos = m.end()

        rest = command[pos:].lstrip()
        if not rest:
            continue

        # 明示指定があれば尊重する
        if rest[0] in "\"'":
            quote = rest[0]
            end = rest.find(quote, 1)
            if end != -1 and rest[1:end] in EXEC_CONTEXTS:
                continue

        out.append(f"'{exec_context}'" if rest[0] == ")" else f"'{exec_context}', ")

    out.append(command[pos:])
    return "".join(out)


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
    config_dir = bpy.utils.user_resource('CONFIG', path='pie_creator', create=True)
    new_path = os.path.join(config_dir, "menus.json")
    
    old_path = os.path.join(os.path.dirname(__file__), "menus.json")
    if os.path.exists(old_path) and not os.path.exists(new_path):
        try:
            import shutil
            shutil.move(old_path, new_path)
        except Exception as e:
            print(f"PieCreator: Migration failed: {e}")
            
    return new_path

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
        print(f"PieCreator: Error loading config: {e}")
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
    except:
        pass
        
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
