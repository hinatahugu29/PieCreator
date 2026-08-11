# PieCreator — User Guide

PieCreator turns anything you can click in Blender into a pie menu, a popup, or a
key you hold. You capture a button, drop it into a menu, and bind a shortcut —
no Python required. When you *do* want Python, every item accepts it.

- **Blender**: 4.2 LTS or newer
- **Where it lives**: `Edit > Preferences > Add-ons > PieCreator`

---

## 1. Install

### Blender 4.2 and newer (recommended)

1. `Edit > Preferences > Get Extensions > Install from Disk...`
2. Pick the PieCreator `.zip`
3. Enable it if it is not enabled already

### Legacy add-on install

1. `Edit > Preferences > Add-ons > Install from Disk...`
2. Pick the `.zip`, then tick the checkbox next to **PieCreator**

Your menus are stored outside the add-on folder, so updating or reinstalling
never erases them. On Windows they live in:

```
%APPDATA%\Blender Foundation\Blender\<version>\config\pie_creator\menus.json
```

---

## 2. Five-minute start

PieCreator ships with one example menu called **Sample Pie Menu**.

1. Open `Preferences > Add-ons > PieCreator`. The editor fills the panel.
2. Find **Sample Pie Menu** in the list and press the ▶ button. The pie opens
   right there — you do not need to close preferences to test a menu.
3. Click the shortcut field in the menu's header row and press a key
   combination. That key now opens the menu anywhere in Blender.

To put your own command in it:

1. In the 3D viewport, **right-click any button** — say `Object > Shade Smooth`.
2. Choose **PieCreator > Capture Operator**.
3. Go back to the editor, open the **Add to:** submenu from the same right-click
   menu, and pick the menu you want it in.

That is the whole loop: right-click, capture, add.

---

## 3. The editor at a glance

The preferences panel is split in two.

**Left sidebar** — three tabs:

| Tab | What it holds |
|---|---|
| **Menus** | Every menu in the active deck, nested by parent/child |
| **Library** | The Command Pool — captured parts waiting to be assembled |
| **Catalog** | Live search across every Blender operator |

**Right editor** — the selected menu, its items, and its settings.

Each menu header row gives you, left to right: a collapse triangle, the menu
name, its type, how many items it has, its shortcut, a ▶ test button, a link
button, a settings menu, and a delete button.

---

## 4. Menu types

Change a menu's type with the `[TYPE]` button in its header.

| Type | Behavior |
|---|---|
| **Pie** | Radial menu around the cursor. Up to 8 items read well |
| **Popup** | Floating list that closes when you release the mouse |
| **Dialog** | Floating list that stays open until you confirm it |
| **Menu** | Vertical list in a box, like a standard Blender menu |
| **Stack** | Not a menu — each press runs the *next* item, then wraps around |
| **Sticky** | Not a menu — runs item 1 on press and item 2 on release |

**Stack** is for cycling: shading modes, snap targets, pivot points.

**Sticky** is for temporary states: turn on wireframe while you hold the key,
turn it off when you let go.

---

## 5. Item types

Press **+** on a menu to add an item, or click an existing item to edit it.

| Type | What it does |
|---|---|
| **Command** | Runs a Python line. This is the default |
| **Property** | Draws a live slider, toggle or dropdown, bound to a data path |
| **Submenu** | Opens another PieCreator menu |
| **Snap Panel** | Drops in Blender's whole snapping panel |
| **Separator** | A blank divider |

**Property** items are what make a pie feel native — a real slider you drag,
not a button that opens a dialog.

---

## 6. Capturing

Right-clicking a button is the fastest way to build menus. What appears depends
on what is under the cursor.

### On a button or menu entry

- **Capture Operator** — grabs the operator *and the settings it was run with*
- **Add to Pool** — sends it to the Library for later
- **Analyze Menu** — reads a whole built-in Blender menu at once (see §10)
- **Add to:** — drops it straight into any menu, grouped by deck

### On a property field

- **Capture Property** — creates a live slider or toggle bound to that property
- **Capture Value as Part** — freezes the *current value* into a command that
  sets it again later. Good for "set roughness to 0.4" style presets.

### Captured commands behave like the button you took them from

Python normally runs operators in a mode that skips their interactive step.
Called that way, `bpy.ops.transform.translate()` moves nothing, and anything
that opens a file browser or a dialog appears to do nothing at all.

PieCreator writes an explicit `'INVOKE_DEFAULT'` into captured commands so they
behave like the button you clicked. If you ever want the non-interactive
behavior for one item, edit its command and write `'EXEC_DEFAULT'` instead —
your explicit choice always wins. To turn the whole feature off, see §13.

---

## 7. Recording macros

1. Press **Record** in the top bar
2. Do things in Blender
3. Press **STOP RECORDING**

Every operator you used is appended to the menu as separate items. A counter
appears near the cursor while recording so you know it is picking things up.

To run several commands from *one* item, put them on one line separated by
semicolons:

```python
bpy.ops.object.select_all(action='DESELECT'); bpy.ops.object.select_by_type(type='MESH')
```

---

## 8. Decks

A deck is a whole set of menus that you swap in and out. Only the active deck's
menus are registered, so shortcuts never collide between decks.

Use them per task: a Modeling deck, a Sculpting deck, an Animation deck — each
free to bind the same key to something different.

- **Add a deck**: the **+** next to the deck name
- **Switch**: click the deck name
- **Move a menu**: its settings menu (⚙) > Move to Deck

---

## 9. Making menus appear only where they belong

Two filters on every menu, both in the info row under the header.

**Modes** — Object Mode, Edit Mode, Sculpt, and so on.
**Areas** — 3D Viewport, Shader Editor, UV Editor, and so on.

Leave a filter empty to mean "everywhere".

### The master key

Bind *one* key — `Ctrl+Shift+X` by default — and let PieCreator choose the menu.
When you press it, PieCreator looks for a menu in the active deck whose Modes
list contains your current mode, and opens that. If nothing matches, it falls
back to the menu you marked with ⚙ **> Set as Master**.

One key, the right menu in every mode.

### Poll conditions

Individual *items* can be hidden with a Python expression in the item's **Poll
Condition** field. The item is drawn only when the expression is true.

```python
context.active_object is not None
context.mode == 'EDIT_MESH'
len(context.selected_objects) > 1
```

`context`, `C`, `D` and `bpy` are all available.

---

## 10. Building from Blender's own menus

You do not have to capture buttons one at a time.

1. In the top bar, type a menu ID into the **Scraper** field (for example
   `VIEW3D_MT_mesh_add`) or right-click a menu and choose **Analyze Menu**
2. Press **Analyze Menu**
3. Tick the entries you want, pick a destination, and import

**Handbook** generates a searchable HTML reference of every menu Blender has
registered, and opens it in your browser. Use it to find menu IDs worth
scraping.

---

## 11. The Command Pool

The **Library** tab holds captured parts that are not in any menu yet.

Capture a handful of things while you work, tick the ones that belong together,
and assemble them into a menu in one go. Parts can be reordered before you
assemble them.

---

## 12. PieDesigner

**Designer** in the top bar scans your Blender build and opens a web-based
editor in your browser, with drag-and-drop layout and search across every
operator in your exact version.

The two sides talk through the clipboard:

- **Copy** — puts your current setup on the clipboard for the Designer
- **Paste** — reads the Designer's output back

Pasting a full project asks whether to **Append** (keep what you have) or
**Overwrite All** (replace it). Overwriting always writes a backup first.

---

## 13. Preferences

Two options sit at the top of the panel.

**Run commands the way buttons do** *(on by default)*
Adds `'INVOKE_DEFAULT'` to captured commands, as described in §6. Turn it off
only if it makes an existing menu behave worse; a single item can always
override it.

**Verbose console log** *(off by default)*
Prints detailed registration and menu-resolution logs to the system console.
Errors are always reported regardless of this setting. Turn it on when you are
tracking down why a menu or command misbehaves — and when reporting a bug.

---

## 14. Backups, import and export

**Export** writes every deck, menu and shortcut to a `.json` file.
**Import** replaces your current setup with one.

Before anything overwrites your settings — an import, or an Overwrite All from
the Designer — PieCreator copies the current file to `menus.backup.json` in the
same folder. To roll back, import that file.

> **Only import settings files you trust.** Menu items are Python, and they run
> when the item is used. A settings file from an untrusted source can run
> anything your Blender can run. This is the same power that lets you put any
> Blender API call on a pie — it cuts both ways.

---

## 15. Troubleshooting

**A menu item does nothing when clicked.**
Open the system console (`Window > Toggle System Console` on Windows). Failed
commands are always reported there, with the exact command that failed. If the
command opens a dialog or a file browser, check that it has `'INVOKE_DEFAULT'`
in it — see §6.

**My shortcut does not fire.**
Something else has claimed the key, or the menu's Modes/Areas filter excludes
where you are. Test the menu with the ▶ button first: if ▶ works and the key
does not, it is a conflict; if ▶ does not work either, it is a filter.

**A menu shows "(Broken Link)".**
It points at a submenu that has been deleted or moved to another deck.

**An item shows "(Poll Error)".**
Its poll expression raised an error. Turn on Verbose console log to see why.

**A property item shows "(Prop Error)".**
Its data path no longer resolves — usually because the object or material it
referenced is gone.

**My menus vanished after an update.**
They should not — settings live outside the add-on folder. Check for
`menus.backup.json` next to `menus.json` and import it.

---

## 16. Getting help

Include the following when reporting a problem:

- Your Blender version and PieCreator version
- The console output with **Verbose console log** turned on
- The command text of the item, if it is one item misbehaving

Issues: <https://github.com/hinatahugu29/PieCreator/issues>
