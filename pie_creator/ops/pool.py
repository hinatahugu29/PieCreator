import bpy
from ..storage import load_config, save_config, load_menus, save_menus
from ..log import log_error

class PIECREATOR_OT_AddToPool(bpy.types.Operator):
    bl_idname = "wm.pie_creator_add_to_pool"
    bl_label = "Add to Command Pool"
    command: bpy.props.StringProperty()
    label: bpy.props.StringProperty()
    def execute(self, context):
        config = load_config()
        pool = config.setdefault("command_pool", [])
        cmd = self.command or context.window_manager.pie_creator_ctx_command
        lbl = self.label or context.window_manager.pie_creator_ctx_label
        if cmd:
            pool.append({"label": lbl, "command": cmd})
            save_config(config)
        return {'FINISHED'}

class PIECREATOR_OT_CaptureValueAsCommand(bpy.types.Operator):
    bl_idname = "wm.pie_creator_capture_value_as_cmd"
    bl_label = "Capture Current Value as Part"
    def execute(self, context):
        wm = context.window_manager
        path = wm.pie_creator_ctx_data_path
        prop = wm.pie_creator_ctx_prop_name
        label = wm.pie_creator_ctx_label
        if not path or not prop:
            from .core import get_prop_info
            path, prop, label = get_prop_info(context)
        if path and prop:
            try:
                data = eval(path, {"bpy": bpy, "context": context})
                val = getattr(data, prop)
                # repr を通す。文字列に引用符を手で付けると値にアポストロフィが
                # 入ったときに壊れた Python になる。
                val_str = repr(val)
                cmd = f"{path}.{prop} = {val_str}"
                config = load_config()
                config.setdefault("command_pool", []).append({"label": f"Set {label} to {val_str}", "command": cmd})
                save_config(config)
                context.window_manager.clipboard = cmd
                return {'FINISHED'}
            except Exception as e:
                log_error(f"現在値の取り込みに失敗した: {path}.{prop}", e)
                self.report({'ERROR'}, f"値を取り込めません: {type(e).__name__}: {e}")
        return {'CANCELLED'}

class PIECREATOR_OT_MovePoolItem(bpy.types.Operator):
    bl_idname = "wm.pie_creator_move_pool_item"
    bl_label = "Move Pool Item"
    index: bpy.props.IntProperty()
    direction: bpy.props.EnumProperty(items=[('UP', "Up", ""), ('DOWN', "Down", "")])
    def execute(self, context):
        config = load_config()
        pool = config.get("command_pool", [])
        idx = self.index
        new_idx = idx - 1 if self.direction == 'UP' else idx + 1
        if 0 <= new_idx < len(pool):
            pool[idx], pool[new_idx] = pool[new_idx], pool[idx]
            save_config(config)
            wm = context.window_manager
            current = wm.pie_creator_pool_selections.split(",") if wm.pie_creator_pool_selections else []
            if str(idx) in current: current.remove(str(idx)); current.append(str(new_idx))
            wm.pie_creator_pool_selections = ",".join(sorted(list(set(current)), key=int))
        return {'FINISHED'}

class PIECREATOR_OT_RemoveFromPool(bpy.types.Operator):
    bl_idname = "wm.pie_creator_remove_from_pool"
    bl_label = "Remove from Pool"
    index: bpy.props.IntProperty()
    def execute(self, context):
        config = load_config()
        pool = config.get("command_pool", [])
        if 0 <= self.index < len(pool):
            pool.pop(self.index); save_config(config)
        return {'FINISHED'}

class PIECREATOR_OT_PoolAssembleToMenu(bpy.types.Operator):
    bl_idname = "wm.pie_creator_pool_assemble"
    bl_label = "Assemble to Menu"
    menu_id: bpy.props.StringProperty()
    selected_indices: bpy.props.StringProperty()
    def execute(self, context):
        config = load_config()
        pool = config.get("command_pool", [])
        menu = next((m for m in config.get("menus", []) if m["id"] == self.menu_id), None)
        if not menu or not self.selected_indices: return {'CANCELLED'}
        indices = [int(i) for i in self.selected_indices.split(",") if i.strip()]
        parts = [pool[i] for i in indices if 0 <= i < len(pool)]
        if parts:
            menu["items"].append({
                "type": "COMMAND",
                "label": " + ".join([p["label"] for p in parts])[:40],
                "command": " ; ".join([p["command"] for p in parts]),
                "icon": 'NONE'
            })
            save_config(config); bpy.ops.wm.pie_creator_reload()
        return {'FINISHED'}

class PIECREATOR_OT_TogglePoolSelection(bpy.types.Operator):
    bl_idname = "wm.pie_creator_toggle_pool_selection"
    bl_label = "Toggle Pool Selection"
    index: bpy.props.IntProperty()
    def execute(self, context):
        wm = context.window_manager
        current = wm.pie_creator_pool_selections.split(",") if wm.pie_creator_pool_selections else []
        idx_str = str(self.index)
        if idx_str in current: current.remove(idx_str)
        else: current.append(idx_str)
        wm.pie_creator_pool_selections = ",".join(sorted(current, key=int))
        return {'FINISHED'}

classes = (
    PIECREATOR_OT_AddToPool,
    PIECREATOR_OT_CaptureValueAsCommand,
    PIECREATOR_OT_MovePoolItem,
    PIECREATOR_OT_RemoveFromPool,
    PIECREATOR_OT_PoolAssembleToMenu,
    PIECREATOR_OT_TogglePoolSelection,
)
