import bpy
import os
import json
import webbrowser

HANDBOOK_TEMPLATE = """
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <title>PieCreator Full Menu Handbook V10</title>
    <style>
        :root { --bg: #111; --card: #222; --text: #eee; --accent: #00aaff; --border: #333; --tag-orphan: #ff8800; --tag-tree: #00cc66; }
        body { background: var(--bg); color: var(--text); font-family: 'Segoe UI', sans-serif; margin: 0; padding: 0; display: flex; flex-direction: column; height: 100vh; }
        .header { background: #1a1a1a; padding: 20px; border-bottom: 2px solid var(--accent); }
        h1 { margin: 0 0 15px 0; font-size: 1.5em; color: var(--accent); display: flex; align-items: center; justify-content: space-between; }
        .stats { font-size: 0.4em; background: #333; color: #aaa; padding: 4px 10px; border-radius: 20px; }
        .search-container { position: relative; }
        #search { width: 100%; padding: 15px; background: #000; border: 1px solid var(--border); color: #fff; border-radius: 8px; font-size: 1.1em; outline: none; }
        #search:focus { border-color: var(--accent); box-shadow: 0 0 10px rgba(0,170,255,0.3); }
        .main-content { flex-grow: 1; overflow-y: auto; padding: 20px; display: grid; grid-template-columns: repeat(auto-fill, minmax(400px, 1fr)); gap: 15px; }
        .menu-card { background: var(--card); border: 1px solid var(--border); border-radius: 8px; transition: 0.2s; display: flex; flex-direction: column; }
        .menu-card:hover { border-color: #555; transform: translateY(-2px); box-shadow: 0 5px 15px rgba(0,0,0,0.5); }
        .card-header { padding: 12px; border-bottom: 1px solid var(--border); display: flex; align-items: flex-start; justify-content: space-between; cursor: pointer; }
        .card-title-area { flex-grow: 1; }
        .label { font-weight: bold; font-size: 1.1em; margin-bottom: 4px; display: block; }
        .idname { font-family: monospace; font-size: 0.85em; color: #888; }
        .tag { font-size: 0.7em; padding: 2px 8px; border-radius: 4px; text-transform: uppercase; margin-left: 10px; flex-shrink: 0; }
        .tag.orphan { background: rgba(255,136,0,0.1); color: var(--tag-orphan); border: 1px solid var(--tag-orphan); }
        .tag.tree { background: rgba(0,204,102,0.1); color: var(--tag-tree); border: 1px solid var(--tag-tree); }
        .card-body { padding: 10px; font-size: 0.9em; max-height: 300px; overflow-y: auto; background: #181818; }
        .hidden { display: none; }
        .item-row { display: flex; align-items: center; padding: 6px; border-bottom: 1px solid #2a2a2a; gap: 10px; }
        .item-row:last-child { border-bottom: none; }
        .i-type { font-size: 0.7em; width: 60px; color: #666; font-weight: bold; }
        .i-label { flex-grow: 1; }
        .i-id { font-size: 0.8em; color: #555; font-family: monospace; }
        .copy-btn { background: #333; border: 1px solid #444; color: #ccc; padding: 5px 12px; border-radius: 4px; cursor: pointer; font-size: 0.8em; }
        .copy-btn:hover { background: var(--accent); color: white; border-color: var(--accent); }
        ::-webkit-scrollbar { width: 8px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: #333; border-radius: 4px; }
        ::-webkit-scrollbar-thumb:hover { background: #444; }
    </style>
</head>
<body>
    <div class="header">
        <h1>
            PieCreator Full Handbook V10
            <span class="stats" id="stats">Scanning...</span>
        </h1>
        <div class="search-container">
            <input type="text" id="search" placeholder="Search ID or Name (multiple words supported)..." autofocus>
        </div>
    </div>
    <div class="main-content" id="content"></div>
    <script>
        const menuData = __DATA_JSON__;
        const container = document.getElementById('content');
        const searchInput = document.getElementById('search');
        document.getElementById('stats').innerText = `Total: ${Object.keys(menuData).length} Menus`;
        const cards = [];
        function initRender() {
            const fragment = document.createDocumentFragment();
            Object.values(menuData).forEach(menu => {
                const card = document.createElement('div');
                card.className = 'menu-card';
                const tagClass = menu.is_orphan ? 'orphan' : 'tree';
                const tagText = menu.is_orphan ? 'Orphan / Internal' : 'UI Tree';
                const searchText = (menu.label + ' ' + menu.idname + ' ' + JSON.stringify(menu.items)).toLowerCase();
                card.dataset.search = searchText;
                card.innerHTML = `
                    <div class="card-header">
                        <div class="card-title-area">
                            <span class="label">${menu.label}</span>
                            <span class="idname">${menu.idname}</span>
                        </div>
                        <span class="tag ${tagClass}">${tagText}</span>
                    </div>
                    <div class="card-body hidden">
                        ${menu.items.length === 0 ? '<div style="color:#555; padding:10px">No items or submenus</div>' : ''}
                        ${menu.items.map(item => `
                            <div class="item-row">
                                <span class="i-type">${item.type}</span>
                                <span class="i-label">${item.label || ''}</span>
                                <span class="i-id">${item.idname || ''}</span>
                            </div>
                        `).join('')}
                    </div>
                    <div style="padding: 10px; border-top: 1px solid #2a2a2a; display:flex; justify-content:flex-end;">
                        <button class="copy-btn" onclick="copyId('${menu.idname}', this)">Copy ID</button>
                    </div>
                `;
                card.querySelector('.card-header').onclick = () => {
                    card.querySelector('.card-body').classList.toggle('hidden');
                };
                cards.push(card); fragment.appendChild(card);
            });
            container.appendChild(fragment);
        }
        window.copyId = (id, btn) => {
            navigator.clipboard.writeText(id);
            const original = btn.innerText; btn.innerText = 'Copied!';
            btn.style.borderColor = '#00aaff';
            setTimeout(() => { btn.innerText = original; btn.style.borderColor = ''; }, 1000);
        };
        let searchTimeout;
        searchInput.addEventListener('input', (e) => {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => {
                const query = e.target.value.toLowerCase();
                const terms = query.split(/\s+/).filter(t => t.length > 0);
                let visibleCount = 0;
                cards.forEach(card => {
                    if (terms.length === 0) { card.classList.remove('hidden'); visibleCount++; }
                    else {
                        const content = card.dataset.search;
                        const match = terms.every(term => content.includes(term));
                        if (match) { card.classList.remove('hidden'); visibleCount++; }
                        else card.classList.add('hidden');
                    }
                });
                document.getElementById('stats').innerText = `Total: ${Object.keys(menuData).length} Menus (Found: ${visibleCount})`;
            }, 100);
        });
        initRender();
    </script>
</body>
</html>
"""

def generate_handbook(context):
    from ..ops.io import MockLayout
    
    # 1. 全メニューのリストアップ
    all_menu_ids = []
    for attr in dir(bpy.types):
        cls = getattr(bpy.types, attr)
        if isinstance(cls, type) and issubclass(cls, bpy.types.Menu):
            all_menu_ids.append(attr)
    
    hierarchy = {}
    processed_ids = set()
    
    def get_menu_label(cls):
        label = getattr(cls, "bl_label", "")
        if not label: label = getattr(cls, "bl_idname", "")
        return label

    # 全件の基本情報をまず作成
    for mid in all_menu_ids:
        cls = getattr(bpy.types, mid)
        hierarchy[mid] = {
            "idname": mid,
            "label": get_menu_label(cls),
            "items": [],
            "is_orphan": True
        }

    def scan_menu(menu_id, depth=0, max_depth=4):
        if depth > max_depth or menu_id in processed_ids: return
        processed_ids.add(menu_id)
        
        cls = getattr(bpy.types, menu_id, None)
        if not cls or not hasattr(cls, "draw"): return
        
        mock = MockLayout(verbose=False)
        try:
            class Dummy: pass
            dummy_self = Dummy()
            dummy_self.layout = mock
            cls.draw(dummy_self, context)
        except: return
        
        items = []
        for item in mock.results:
            if item["type"] == "MENU":
                sub_id = item["idname"]
                if sub_id in hierarchy: hierarchy[sub_id]["is_orphan"] = False
                scan_menu(sub_id, depth + 1)
                items.append({"type": "MENU", "label": item["label"], "idname": sub_id})
            else: items.append(item)
        if menu_id in hierarchy: hierarchy[menu_id]["items"] = items

    # 主要ルートからスキャン
    root_menus = ["VIEW3D_MT_editor_menus", "NODE_MT_editor_menus", "IMAGE_MT_editor_menus", "TOPBAR_MT_editor_menus"]
    for root in root_menus:
        if root in hierarchy:
            hierarchy[root]["is_orphan"] = False
            scan_menu(root)
            
    # HTML生成
    json_data = json.dumps(hierarchy, ensure_ascii=False)
    full_html = HANDBOOK_TEMPLATE.replace("__DATA_JSON__", json_data)
    
    # アドオンのテンポラリディレクトリまたはデスクトップに出力
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    filepath = os.path.join(desktop, "pie_creator_handbook.html")
    
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(full_html)
    
    webbrowser.open(f"file:///{filepath}")
    return len(all_menu_ids), filepath
