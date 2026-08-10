let config = {
    active_deck: "default",
    menus: [
        { id: "main_pie", name: "Main Menu", type: "PIE", items: [
            { id: "i1", label: "Object Mode", type: "COMMAND", command: "bpy.ops.object.mode_set(mode='OBJECT')", dir: "pie-n" },
            { id: "i2", label: "Modeling Tools", type: "MENU", menu_id: "mod_popup", dir: "pie-w" }
        ]},
        { id: "mod_popup", name: "Modeling Utils", type: "POPUP", items: [
            { id: "s1", label: "Subdivide", type: "COMMAND", command: "bpy.ops.mesh.subdivide()" }
        ]}
    ]
};

let currentMenuId = "main_pie";
let selectedId = null;
let isMapView = false;
let isSplitView = false;
let blenderCatalog = null;
let commandHistory = [];
let dirHandle = null; // For File System Access API

function init() {
    const saved = localStorage.getItem('pie_designer_config');
    if (saved) {
        config = JSON.parse(saved);
        // Ensure all items have IDs
        ensureItemIds(config);
    }
    const savedHistory = localStorage.getItem('pie_designer_history');
    if (savedHistory) commandHistory = JSON.parse(savedHistory);

    // Use the global variable loaded via <script> tag if available
    if (typeof BLENDER_CATALOG !== 'undefined') {
        blenderCatalog = BLENDER_CATALOG;
        logToUI("Catalog loaded via JS tag");
    } else {
        logToUI("No local catalog (JS) found.");
    }
    renderAll();
}

function logToUI(msg) {
    console.log(msg);
}

function loadCatalog(e) {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (re) => {
        blenderCatalog = JSON.parse(re.target.result);
        alert(`Catalog Loaded: ${Object.keys(blenderCatalog.modules).length} modules found.`);
        renderAll();
    };
    reader.readAsText(file);
}

function ensureItemIds(cfg) {
    if (!cfg || !cfg.menus) return;
    cfg.menus.forEach(m => {
        if (!m.items) return;
        m.items.forEach((it, idx) => {
            if (!it.id) it.id = 'it_' + Math.random().toString(36).substr(2, 9) + '_' + Date.now();
        });
    });
}

function findItem(id) {
    for (const m of config.menus) {
        const found = m.items.find(i => i.id === id);
        if (found) return found;
    }
    return null;
}

function searchCatalog() {
    const searchInput = document.getElementById('lib-search-input');
    if (!searchInput) return;
    const query = searchInput.value.toLowerCase();
    const resultsDiv = document.getElementById('lib-results-list');
    if (!blenderCatalog) {
        resultsDiv.innerHTML = '<div style="text-align:center; padding:10px; font-size:10px; color:var(--text-muted);">Please load catalog first.</div>';
        return;
    }
    resultsDiv.innerHTML = '';

    if (query.length < 2) {
        resultsDiv.innerHTML = '<div style="text-align:center; padding:10px; font-size:10px; color:var(--text-muted);">Type at least 2 chars...</div>';
        return;
    }

    const queryParts = query.split(' ').filter(p => p.length > 0);
    const matches = [];

    for (const mod in blenderCatalog.modules) {
        for (const op of blenderCatalog.modules[mod]) {
            const fullText = `${op.id} ${op.name} ${op.desc}`.toLowerCase();
            if (queryParts.every(part => fullText.includes(part))) {
                matches.push(op);
            }
            if (matches.length > 50) break;
        }
        if (matches.length > 50) break;
    }

    resultsDiv.innerHTML = matches.map(op => `
        <div class="lib-item" onclick="applyOperator('${op.id}')">
            <div class="lib-id">${op.id}</div>
            <div class="lib-name">${op.name}</div>
        </div>
    `).join('');
}

function renderHistory() {
    const area = document.getElementById('history-items');
    if (!area) return;
    area.innerHTML = commandHistory.map(id => `
        <div class="history-tag" onclick="applyOperator('${id}')">${id.split('.').pop()}</div>
    `).join('');
}

function searchIcons() {
    const input = document.getElementById('icon-search-input');
    const resultsDiv = document.getElementById('icon-results-list');
    if (!blenderCatalog || !blenderCatalog.icons) return;
    
    const query = input.value.toLowerCase();
    if (query.length < 2) {
        resultsDiv.innerHTML = '<div style="text-align:center; padding:10px; font-size:10px; color:var(--text-muted);">Type at least 2 chars...</div>';
        return;
    }

    const matches = blenderCatalog.icons.filter(icon => icon.toLowerCase().includes(query)).slice(0, 50);
    resultsDiv.innerHTML = matches.map(icon => `
        <div class="lib-item" onclick="applyIcon('${icon}')" style="padding:4px 10px;">
            <div class="lib-id" style="font-size:10px; color:#fff;">${icon}</div>
        </div>
    `).join('');
}

function applyIcon(icon) {
    const item = findItem(selectedId);
    if (item) {
        item.icon = icon;
        renderAll();
    }
}

function applyOperator(id) {
    const item = findItem(selectedId);
    if (item) {
        const isMacro = document.getElementById('macro-mode').checked;
        const newCmd = `bpy.ops.${id}()`;
        const currentCmd = (item.command || item.cmd || "").trim();
        
        if (isMacro && currentCmd.length > 0) {
            const separator = currentCmd.endsWith(';') ? ' ' : '; ';
            item.command = currentCmd + separator + newCmd;
        } else {
            item.command = newCmd;
        }
        item.cmd = item.command; // Unify

        // Add to History
        if (!commandHistory.includes(id)) {
            commandHistory.unshift(id);
            if (commandHistory.length > 15) commandHistory.pop();
            localStorage.setItem('pie_designer_history', JSON.stringify(commandHistory));
        }
        
        renderAll();
    } else {
        alert("No item selected to apply command.");
    }
}

function deleteItem() {
    if (!selectedId) {
        console.warn("Delete failed: No item selected.");
        return;
    }
    showConfirm("Delete this item?", () => {
        let found = false;
        for (const m of config.menus) {
            const idx = m.items.findIndex(i => i.id === selectedId);
            if (idx !== -1) {
                m.items.splice(idx, 1);
                found = true;
                break;
            }
        }
        if (found) {
            selectedId = null;
            renderAll();
        } else {
            console.error("Delete failed: Item not found in config.");
        }
    });
}

function moveItem(e, id, direction) {
    if (e) e.stopPropagation();
    try {
        const menu = config.menus.find(m => m.items.some(it => it.id === id));
        if (!menu) return;
        const items = menu.items;
        const item = items.find(it => it.id === id);
        const idx = items.indexOf(item);

        if (menu.type === 'PIE') {
            const priority = ['pie-w', 'pie-e', 'pie-s', 'pie-n', 'pie-nw', 'pie-ne', 'pie-sw', 'pie-se'];
            const currentDir = item.dir;
            const pIdx = priority.indexOf(currentDir);
            let targetPIdx = (direction === 'up') ? pIdx - 1 : pIdx + 1;

            if (targetPIdx >= 0 && targetPIdx < priority.length) {
                const targetDir = priority[targetPIdx];
                const other = items.find(it => it.dir === targetDir);
                if (other) {
                    // Swap Directions
                    item.dir = targetDir;
                    other.dir = currentDir;
                    // Also swap in array to keep some consistency
                    const otherIdx = items.indexOf(other);
                    [items[idx], items[otherIdx]] = [items[otherIdx], items[idx]];
                    logToUI(`Swapped #${pIdx+1} and #${targetPIdx+1}`);
                } else {
                    // Just move to empty slot
                    item.dir = targetDir;
                    logToUI(`Moved to slot #${targetPIdx+1}`);
                }
            }
        } else {
            // Standard List Swap
            let targetIdx = (direction === 'up') ? idx - 1 : idx + 1;
            if (targetIdx >= 0 && targetIdx < items.length) {
                [items[idx], items[targetIdx]] = [items[targetIdx], items[idx]];
                logToUI(`Moved in list: ${idx} -> ${targetIdx}`);
            }
        }
        renderAll();
    } catch (err) {
        logToUI(`Error: ${err.message}`);
    }
}

function deleteMenu(e, id) {
    if (e) e.stopPropagation();
    
    const rootId = config.menus[0].id;
    if (id === rootId) {
        alert("The Root menu cannot be deleted.");
        return;
    }
    
    const isReferenced = config.menus.some(m => m.items.some(it => (it.type === 'SUBMENU' || it.type === 'MENU') && it.menu_id === id));
    const msg = isReferenced 
        ? "This menu is referenced by another menu. Deleting it will break those links. Continue?" 
        : "Are you sure you want to delete this menu?";
        
    showConfirm(msg, () => {
        config.menus = config.menus.filter(m => m.id !== id);
        if (currentMenuId === id) {
            currentMenuId = rootId;
        }
        selectedId = null;
        renderAll();
    });
}

function renderAll() {
    renderSidebar();
    if (isSplitView) {
        renderCanvas();
        renderMap();
    } else if (isMapView) {
        renderMap();
    } else {
        renderCanvas();
    }
    renderProperties();
    renderMenuSettings();
    renderHistory();
    renderItemOrder();
    localStorage.setItem('pie_designer_config', JSON.stringify(config));
}

function renderItemOrder() {
    const list = document.getElementById('item-order-list');
    if (!list) return;
    const menu = config.menus.find(m => m.id === currentMenuId);
    if (!menu || !menu.items || menu.items.length === 0) {
        list.innerHTML = '<div style="text-align:center; padding:10px; color:var(--text-muted); font-size:10px;">No items in this menu.</div>';
        return;
    }

    list.innerHTML = menu.items.map((it, idx) => `
        <div class="popup-row ${it.id === selectedId ? 'selected' : ''}" style="padding:4px 8px; font-size:11px;" onclick="selectIt('${it.id}')">
            <span style="opacity:0.4; margin-right:8px; font-family:monospace;">#${idx}</span>
            <span style="flex-grow:1; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${it.label}</span>
            <div class="reorder-controls" onclick="event.stopPropagation()">
                <button class="reorder-btn" onclick="moveItem(event, '${it.id}', 'up')" ${idx === 0 ? 'disabled style="opacity:0.2"' : ''}>▲</button>
                <button class="reorder-btn" onclick="moveItem(event, '${it.id}', 'down')" ${idx === menu.items.length - 1 ? 'disabled style="opacity:0.2"' : ''}>▼</button>
            </div>
        </div>
    `).join('');
}

function toggleMapView() {
    isSplitView = false;
    isMapView = !isMapView;
    updateDisplayModes();
}

function toggleSplitView() {
    isMapView = false;
    isSplitView = !isSplitView;
    updateDisplayModes();
}

function updateDisplayModes() {
    const canvas = document.querySelector('.canvas');
    const viewport = document.getElementById('viewport');
    const mapContainer = document.getElementById('map-container');

    canvas.classList.toggle('split-mode', isSplitView);
    
    if (isSplitView) {
        viewport.style.display = 'flex';
        mapContainer.style.display = 'block';
    } else if (isMapView) {
        viewport.style.display = 'none';
        mapContainer.style.display = 'block';
    } else {
        viewport.style.display = 'flex';
        mapContainer.style.display = 'none';
    }

    document.getElementById('btn-map').classList.toggle('active', isMapView);
    document.getElementById('btn-split').classList.toggle('active', isSplitView);
    renderAll();
}

// --- Resizer Logic ---
let isDraggingH = false; // Horizontal split (Top/Bottom)
let isDraggingL = false; // Left sidebar
let isDraggingR = false; // Right sidebar

window.addEventListener('load', () => {
    const resizer = document.getElementById('resizer');
    const resizerL = document.getElementById('resizer-l');
    const resizerR = document.getElementById('resizer-r');
    const viewport = document.getElementById('viewport');
    const sidebar = document.querySelector('.sidebar');
    const properties = document.querySelector('.properties');

    // Horizontal Split Resizer
    if (resizer) {
        resizer.addEventListener('mousedown', (e) => {
            isDraggingH = true;
            resizer.classList.add('dragging');
            document.body.classList.add('resizing');
            document.body.style.cursor = 'row-resize';
            e.preventDefault();
        });
    }

    // Left Sidebar Resizer
    if (resizerL) {
        resizerL.addEventListener('mousedown', (e) => {
            isDraggingL = true;
            resizerL.classList.add('dragging');
            document.body.classList.add('resizing');
            document.body.style.cursor = 'col-resize';
            document.body.style.userSelect = 'none';
            e.preventDefault();
        });
    }

    // Right Sidebar Resizer
    if (resizerR) {
        resizerR.addEventListener('mousedown', (e) => {
            isDraggingR = true;
            resizerR.classList.add('dragging');
            document.body.classList.add('resizing');
            document.body.style.cursor = 'col-resize';
            document.body.style.userSelect = 'none';
            e.preventDefault();
        });
    }

    window.addEventListener('mousemove', (e) => {
        // Horizontal Resize
        if (isDraggingH && isSplitView) {
            const canvas = document.querySelector('.canvas');
            const canvasRect = canvas.getBoundingClientRect();
            const relativeY = e.clientY - canvasRect.top;
            const percentage = (relativeY / canvasRect.height) * 100;
            if (percentage > 10 && percentage < 90) {
                viewport.style.height = percentage + '%';
            }
        }
        
        // Left Sidebar Resize
        if (isDraggingL) {
            const newWidth = e.clientX;
            if (newWidth > 150 && newWidth < 500) {
                sidebar.style.width = newWidth + 'px';
            }
        }

        // Right Sidebar Resize
        if (isDraggingR) {
            const newWidth = window.innerWidth - e.clientX;
            if (newWidth > 200 && newWidth < 600) {
                properties.style.width = newWidth + 'px';
            }
        }
    });

    window.addEventListener('mouseup', () => {
        isDraggingH = false;
        isDraggingL = false;
        isDraggingR = false;
        document.body.classList.remove('resizing');
        document.body.style.cursor = 'default';
        document.body.style.userSelect = 'auto';
        [resizer, resizerL, resizerR].forEach(r => r && r.classList.remove('dragging'));
    });
});

function renderMap() {
    const nodeContainer = document.getElementById('map-nodes');
    const svg = document.getElementById('map-svg');
    if (!nodeContainer || !svg) return;
    nodeContainer.innerHTML = '';
    svg.innerHTML = '';

    const levelX = 300;
    const levelY = 150;
    const positions = {};
    let maxY = 0;

    // Simple Auto-Layout (Recursive Tree)
    function layout(menuId, x, y) {
        if (positions[menuId]) return;
        positions[menuId] = { x, y };
        const menu = config.menus.find(m => m.id === menuId);
        if (!menu) return;
        
        let childY = y;
        menu.items.filter(it => (it.type === 'SUBMENU' || it.type === 'MENU') && it.menu_id).forEach((it, i) => {
            layout(it.menu_id, x + levelX, childY);
            childY += levelY;
            if (childY > maxY) maxY = childY;
        });
    }

    // Start layout from all root menus (usually the first one)
    layout(config.menus[0].id, 100, 100);

    // Layout Orphans (Menus not visited during recursive layout)
    let orphanX = 100;
    let orphanY = maxY + 300;
    if (orphanY < 600) orphanY = 800; // Minimum Y for orphans

    config.menus.forEach(m => {
        if (!positions[m.id]) {
            positions[m.id] = { x: orphanX, y: orphanY, isOrphan: true };
            orphanX += levelX;
            if (orphanX > 1500) {
                orphanX = 100;
                orphanY += levelY;
            }
        }
    });

    // Draw Nodes
    config.menus.forEach(m => {
        const pos = positions[m.id];
        const node = document.createElement('div');
        node.className = `map-node ${m.id === currentMenuId ? 'active' : ''} ${pos.isOrphan ? 'orphan' : ''}`;
        node.style.left = pos.x + 'px';
        node.style.top = pos.y + 'px';
        node.innerHTML = `<div class="m-type">${m.type}</div><div class="m-name">${m.name}</div>`;
        
        node.onclick = () => { 
            currentMenuId = m.id; 
            if (isSplitView) {
                renderAll(); 
            } else {
                isMapView = false;
                updateDisplayModes(); 
            }
        };
        nodeContainer.appendChild(node);

        // Draw Bezier Links & Labels
        m.items.filter(it => (it.type === 'SUBMENU' || it.type === 'MENU') && it.menu_id).forEach(it => {
            const childPos = positions[it.menu_id];
            if (childPos) {
                const startX = pos.x + 180;
                const startY = pos.y + 35;
                const endX = childPos.x;
                const endY = childPos.y + 35;
                
                // Draw Path
                const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
                const cp1x = startX + (endX - startX) / 2;
                const cp2x = startX + (endX - startX) / 2;
                const d = `M ${startX} ${startY} C ${cp1x} ${startY}, ${cp2x} ${endY}, ${endX} ${endY}`;
                path.setAttribute("d", d);
                path.setAttribute("stroke", "var(--accent-blue)");
                path.setAttribute("stroke-width", "2");
                path.setAttribute("fill", "none");
                path.setAttribute("style", "opacity: 0.15;");
                svg.appendChild(path);

                // Draw Label Bubble at midpoint
                const label = document.createElement('div');
                label.className = 'map-link-label';
                label.style.left = (startX + endX) / 2 + 'px';
                label.style.top = (startY + endY) / 2 + 'px';
                label.innerText = it.label;
                nodeContainer.appendChild(label);
            }
        });
    });
}

function renderSidebar() {
    const list = document.getElementById('menu-list');
    if (!list) return;
    list.innerHTML = config.menus.map(m => `
        <div class="nav-item ${m.id === currentMenuId ? 'active' : ''}" onclick="switchMenu('${m.id}')">
            <span>${m.type === 'PIE' ? '🥧' : '🗂️'} ${m.name}</span>
            <span class="del-btn" onclick="deleteMenu(event, '${m.id}')">✕</span>
        </div>
    `).join('');

    const select = document.getElementById('p-sub-id');
    if (select) {
        select.innerHTML = config.menus.map(m => `<option value="${m.id}">${m.name}</option>`).join('') + '<option value="new">+ Create New</option>';
    }
}

function findParentMenu(childId) {
    return config.menus.find(m => m.items.some(it => (it.type === 'SUBMENU' || it.type === 'MENU') && it.menu_id === childId));
}

function switchMenu(id) { currentMenuId = id; selectedId = null; renderAll(); }
function selectIt(id) { selectedId = id; renderAll(); }

function dive(menuId, itemId) {
    selectedId = itemId;
    const viewport = document.getElementById('viewport');
    viewport.classList.add('diving');
    setTimeout(() => {
        currentMenuId = menuId;
        viewport.classList.remove('diving');
        viewport.classList.add('emerging');
        setTimeout(() => viewport.classList.remove('emerging'), 300);
        renderAll();
    }, 300);
}

function goUp() {
    const parent = findParentMenu(currentMenuId);
    if (parent) switchMenu(parent.id);
    else goToRoot();
}

function goToRoot() { switchMenu(config.menus[0].id); }

function renderCanvas() {
    const viewport = document.getElementById('viewport');
    if (!viewport) return;
    const menu = config.menus.find(m => m.id === currentMenuId);
    if (!menu) return;

    // Ensure IDs exist before rendering
    menu.items.forEach((it, idx) => {
        if (!it.id) it.id = 'it_' + Math.random().toString(36).substr(2, 9) + '_' + Date.now();
    });

    // Auto-assign directions for items without 'dir'
    if (menu.type === 'PIE') {
        const priority = ['pie-w', 'pie-e', 'pie-s', 'pie-n', 'pie-nw', 'pie-ne', 'pie-sw', 'pie-se'];
        menu.items.forEach(item => {
            if (item.command && !item.cmd) item.cmd = item.command;
            if (item.icon === "NONE") item.icon = "";
            if (!item.dir) {
                for (let pDir of priority) {
                    if (!menu.items.some(it => it.dir === pDir)) {
                        item.dir = pDir;
                        break;
                    }
                }
            }
        });
    } else {
        menu.items.forEach(item => {
            if (item.command && !item.cmd) item.cmd = item.command;
            if (item.cmd && !item.command) item.command = item.cmd;
            if (item.icon === "NONE") item.icon = "";
        });
    }

    // Breadcrumbs
    let breadcrumbHtml = ``;
    const parent = findParentMenu(currentMenuId);
    if (currentMenuId !== config.menus[0].id) {
        breadcrumbHtml += `<span class="back-btn" onclick="goUp()" style="margin-right:12px; color:var(--accent-blue); font-weight:bold;">← Back</span>`;
    }
    breadcrumbHtml += `<span onclick="goToRoot()">Root</span>`;
    if (parent && parent.id !== config.menus[0].id) {
        breadcrumbHtml += ` / <span onclick="switchMenu('${parent.id}')">${parent.name}</span>`;
    }
    if (currentMenuId !== config.menus[0].id) {
        breadcrumbHtml += ` / <span class="current">${menu.name}</span>`;
    }
    const bcElem = document.getElementById('breadcrumb');
    if (bcElem) bcElem.innerHTML = breadcrumbHtml;

    if (menu.type === 'PIE') {
        const dirs = ['pie-n', 'pie-ne', 'pie-e', 'pie-se', 'pie-s', 'pie-sw', 'pie-w', 'pie-nw'];
        const priority = ['pie-w', 'pie-e', 'pie-s', 'pie-n', 'pie-nw', 'pie-ne', 'pie-sw', 'pie-se'];
        
        viewport.innerHTML = `<div class="pie-container">
            <div class="pie-center" onclick="addNextItem()" title="Add Next (Blender Order)" style="cursor:pointer">
                <div class="type-label">PIE</div>
                <div style="font-size:18px; margin-top:4px;">＋</div>
            </div>` + 
            dirs.map(d => {
                const it = menu.items.find(i => i.dir === d);
                const idxInArray = it ? menu.items.indexOf(it) : -1;
                const pIdx = priority.indexOf(d) + 1;
                if (it) {
                    const isSub = it.type === 'SUBMENU' || it.type === 'MENU';
                    return `<div class="pie-item ${d} ${it.id === selectedId ? 'selected' : ''}" 
                                 onclick="selectIt('${it.id}')" 
                                 ${isSub ? `ondblclick="dive('${it.menu_id}', '${it.id}')"` : ''}>
                        <div style="position:absolute; top:-15px; left:50%; transform:translateX(-50%); font-size:9px; color:var(--text-muted); font-weight:bold;">#${pIdx}</div>
                        ${it.label}
                        ${isSub ? `<span class="dive-icon" onclick="event.stopPropagation(); dive('${it.menu_id}', '${it.id}')" style="color:var(--accent-blue); margin-left:8px; padding:4px;">❯</span>` : ''}
                        
                        <div class="reorder-controls mini" onclick="event.stopPropagation()" style="position:absolute; right:-25px; top:50%; transform:translateY(-50%);">
                            <button class="reorder-btn" onclick="moveItem(event, '${it.id}', 'up')" ${idxInArray === 0 ? 'disabled style="opacity:0.2"' : ''}>▲</button>
                            <button class="reorder-btn" onclick="moveItem(event, '${it.id}', 'down')" ${idxInArray === menu.items.length - 1 ? 'disabled style="opacity:0.2"' : ''}>▼</button>
                        </div>
                    </div>`;
                }
                return `<div class="pie-item ${d}" style="opacity:0.1; border-style:dashed;" onclick="addIt('${d}')">
                    <div style="font-size:9px; margin-bottom:4px; opacity:0.5;">#${pIdx}</div>
                    +
                </div>`;
            }).join('') + `</div>`;
    } else {
        viewport.innerHTML = `<div class="popup-container"><div class="popup-header">${menu.name}</div><div class="popup-list">` +
            menu.items.map((it, idx) => {
                const isSub = it.type === 'SUBMENU' || it.type === 'MENU';
                return `<div class="popup-row ${it.id === selectedId ? 'selected' : ''}" 
                             onclick="selectIt('${it.id}')"
                             ${isSub ? `ondblclick="dive('${it.menu_id}', '${it.id}')"` : ''}>
                    ⚓ ${it.label} 
                    ${isSub ? `<span class="dive-icon" onclick="event.stopPropagation(); dive('${it.menu_id}', '${it.id}')" style="margin-left:auto; color:var(--accent-blue); padding:4px;">❯</span>` : ''}
                    <div class="reorder-controls" onclick="event.stopPropagation()">
                        <button class="reorder-btn" onclick="moveItem(event, '${it.id}', 'up')" ${idx === 0 ? 'disabled style="opacity:0.2"' : ''}>▲</button>
                        <button class="reorder-btn" onclick="moveItem(event, '${it.id}', 'down')" ${idx === menu.items.length - 1 ? 'disabled style="opacity:0.2"' : ''}>▼</button>
                    </div>
                </div>`;
            }).join('') +
            `<div class="popup-row" style="opacity:0.3; justify-content:center;" onclick="addIt()">+ Add Item</div></div></div>`;
    }
}

function renderMenuSettings() {
    const menu = config.menus.find(m => m.id === currentMenuId);
    if (!menu) return;
    const nameInput = document.getElementById('m-name');
    if (nameInput) nameInput.value = menu.name;
    const mtPie = document.getElementById('mt-pie');
    const mtPop = document.getElementById('mt-pop');
    if (mtPie) mtPie.classList.toggle('active', menu.type === 'PIE');
    if (mtPop) mtPop.classList.toggle('active', menu.type === 'POPUP');
}

function renderProperties() {
    const content = document.getElementById('prop-content');
    if (!content) return;
    if (!selectedId) { content.style.display = 'none'; return; }
    content.style.display = 'block';

    let it = null;
    config.menus.forEach(m => {
        const found = m.items.find(i => i.id === selectedId);
        if (found) it = found;
    });
    if (!it) return;

    document.getElementById('item-title').innerText = it.label;
    document.getElementById('p-label').value = it.label;
    document.getElementById('p-cmd').value = it.command || it.cmd || "";
    document.getElementById('p-icon').value = it.icon || "";
    document.getElementById('p-sub-id').value = it.menu_id || "";
    
    setT((it.type === 'MENU' || it.type === 'SUBMENU') ? 'SUBMENU' : 'COMMAND', true);
}

function setMenuT(type) {
    const menu = config.menus.find(m => m.id === currentMenuId);
    if (menu) {
        menu.type = type;
        renderAll();
    }
}

function saveMenuChange() {
    const menu = config.menus.find(m => m.id === currentMenuId);
    if (menu) {
        menu.name = document.getElementById('m-name').value;
        renderAll();
    }
}

function setT(type, skip) {
    document.getElementById('t-cmd').classList.toggle('active', type === 'COMMAND');
    document.getElementById('t-sub').classList.toggle('active', type === 'SUBMENU');
    document.getElementById('fields-cmd').style.display = type === 'COMMAND' ? 'block' : 'none';
    document.getElementById('fields-sub').style.display = type === 'SUBMENU' ? 'block' : 'none';
    
    if (!skip) {
        const menu = config.menus.find(m => m.items.some(i => i.id === selectedId));
        const it = menu.items.find(i => i.id === selectedId);
        
        if (type === 'SUBMENU' && !it.menu_id) {
            const newMenuId = "m_" + Date.now();
            const newMenu = { id: newMenuId, name: it.label + " Sub", type: "POPUP", items: [] };
            config.menus.push(newMenu);
            it.menu_id = newMenuId;
        }
        saveChange();
    }
}

function saveChange() {
    let it = null;
    config.menus.forEach(m => {
        const found = m.items.find(i => i.id === selectedId);
        if (found) it = found;
    });
    if (!it) return;

    it.label = document.getElementById('p-label').value;
    const cmdVal = document.getElementById('p-cmd').value;
    it.command = cmdVal;
    it.cmd = cmdVal;
    it.icon = document.getElementById('p-icon').value;
    it.type = document.getElementById('t-cmd').classList.contains('active') ? 'COMMAND' : 'MENU';
    
    const subId = document.getElementById('p-sub-id').value;
    if (subId === 'new') {
        const newMenuId = "m_" + Date.now();
        const newMenu = { id: newMenuId, name: "New Submenu", type: "POPUP", items: [] };
        config.menus.push(newMenu);
        it.menu_id = newMenuId;
    } else {
        it.menu_id = subId;
    }
    renderAll();
}

function addIt(dir) {
    const menu = config.menus.find(m => m.id === currentMenuId);
    const newIt = { id: 'it_'+Date.now(), label: 'New Item', type: 'COMMAND', dir: dir };
    menu.items.push(newIt);
    selectedId = newIt.id;
    renderAll();
}

function addNextItem() {
    const menu = config.menus.find(m => m.id === currentMenuId);
    if (menu.type !== 'PIE') return;
    const priority = ['pie-w', 'pie-e', 'pie-s', 'pie-n', 'pie-nw', 'pie-ne', 'pie-sw', 'pie-se'];
    for (const dir of priority) {
        if (!menu.items.some(it => it.dir === dir)) {
            addIt(dir);
            return;
        }
    }
    alert("All 8 slots are full.");
}

function prepareDataForExport() {
    const exportConfig = JSON.parse(JSON.stringify(config));
    exportConfig.menus.forEach(m => {
        m.items.forEach(it => {
            if (!it.icon || it.icon.trim() === "") it.icon = "NONE";
            if (it.cmd && !it.command) it.command = it.cmd;
        });
    });
    return exportConfig;
}

function exportData() {
    const data = prepareDataForExport();
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'menus.json';
    a.click();
}

function importData(e) {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (re) => {
        config = JSON.parse(re.target.result);
        currentMenuId = config.menus[0].id;
        renderAll();
    };
    reader.readAsText(file);
}

function resetData() {
    showConfirm('Reset to default? All current work will be lost.', () => {
        localStorage.removeItem('pie_designer_config');
        location.reload();
    });
}

function copyToClipboard() {
    const data = { type: "PIE_CREATOR_PROJECT", payload: prepareDataForExport() };
    const json = JSON.stringify(data, null, 2);
    navigator.clipboard.writeText(json).then(() => {
        alert("Project JSON copied to clipboard!");
    }).catch(err => {
        alert("Failed to copy: " + err);
    });
}

function copyMenuToClipboard() {
    const menu = config.menus.find(m => m.id === currentMenuId);
    if (!menu) return;
    const exportMenu = JSON.parse(JSON.stringify(menu));
    exportMenu.items.forEach(it => {
        if (!it.icon || it.icon.trim() === "") it.icon = "NONE";
        if (it.cmd && !it.command) it.command = it.cmd;
    });
    const data = { type: "PIE_CREATOR_MENU", payload: exportMenu };
    const json = JSON.stringify(data, null, 2);
    navigator.clipboard.writeText(json).then(() => {
        alert(`Menu '${menu.name}' copied!`);
    }).catch(err => {
        alert("Failed to copy menu: " + err);
    });
}

let confirmCallback = null;
function showConfirm(msg, onOk) {
    document.getElementById('confirm-msg').innerText = msg;
    const modal = document.getElementById('confirm-modal');
    const okBtn = document.getElementById('confirm-ok-btn');
    modal.style.display = 'flex';
    confirmCallback = onOk;
    okBtn.onclick = () => { closeConfirm(true); };
}

function closeConfirm(isOk) {
    document.getElementById('confirm-modal').style.display = 'none';
    if (isOk && confirmCallback) { confirmCallback(); }
    confirmCallback = null;
}

async function pasteFromClipboard() {
    try {
        const text = await navigator.clipboard.readText();
        if (!text) return;
        const data = JSON.parse(text);
        if (!data || !data.payload) {
            alert("Invalid data format.");
            return;
        }
        if (data.type === "PIE_CREATOR_PROJECT") {
            showConfirm("Import full project?", () => {
                config = data.payload;
                ensureItemIds(config);
                if (config.menus && config.menus.length > 0) currentMenuId = config.menus[0].id;
                renderAll();
            });
        } else if (data.type === "PIE_CREATOR_MENU") {
            const newMenu = data.payload;
            // Ensure items in the new menu have IDs
            if (newMenu.items) {
                newMenu.items.forEach(it => {
                    if (!it.id) it.id = 'it_' + Math.random().toString(36).substr(2, 9) + '_' + Date.now();
                });
            }
            const exists = config.menus.find(m => m.id === newMenu.id);
            if (exists) {
                showConfirm(`Menu ID '${newMenu.id}' already exists. Overwrite?`, () => {
                    const idx = config.menus.findIndex(m => m.id === newMenu.id);
                    config.menus[idx] = newMenu;
                    currentMenuId = newMenu.id;
                    renderAll();
                });
            } else {
                config.menus.push(newMenu);
                currentMenuId = newMenu.id;
                renderAll();
            }
        }
    } catch (err) {
        alert("Failed to read clipboard: " + err);
    }
}

// Global script load
window.addEventListener('DOMContentLoaded', init);
