import bpy
import os
import json
import webbrowser

class PIECREATOR_OT_OpenDesigner(bpy.types.Operator):
    """Scan Blender API and Open Web Designer"""
    bl_idname = "wm.pie_creator_open_designer"
    bl_label = "Open PieDesigner"
    bl_options = {'REGISTER'}

    def execute(self, context):
        self.report({'INFO'}, "Scanning Blender API & Icons...")
        
        catalog = {
            "modules": {},
            "icons": []
        }
        
        # Scan Icons
        icon_enum = bpy.types.UILayout.bl_rna.functions["prop"].parameters["icon"].enum_items
        catalog["icons"] = sorted([i.identifier for i in icon_enum if i.identifier != 'NONE'])
        
        # Scan Operators
        for attr in dir(bpy.ops):
            module = getattr(bpy.ops, attr)
            if str(type(module)) != "<class 'module'>":
                continue
            module_ops = []
            for op_name in dir(module):
                if op_name.startswith("_"): continue
                try:
                    op = getattr(module, op_name)
                    rna = op.get_rna_type()
                    module_ops.append({
                        "id": f"{attr}.{op_name}",
                        "name": rna.name or op_name,
                        "desc": rna.description or ""
                    })
                except:
                    continue
            if module_ops:
                catalog["modules"][attr] = module_ops

        # Save to designer directory as .js
        addon_dir = os.path.dirname(os.path.dirname(__file__))
        designer_dir = os.path.join(addon_dir, "designer")
        catalog_path = os.path.join(designer_dir, "blender_catalog.js")
        
        try:
            with open(catalog_path, 'w', encoding='utf-8') as f:
                f.write("var BLENDER_CATALOG = ")
                json.dump(catalog, f, indent=2, ensure_ascii=False)
                f.write(";")
            self.report({'INFO'}, f"Catalog updated: {catalog_path}")
        except Exception as e:
            self.report({'ERROR'}, f"Failed to save catalog: {e}")
            return {'CANCELLED'}

        # Open HTML
        html_path = os.path.join(designer_dir, "index.html")
        if os.path.exists(html_path):
            url = "file://" + html_path.replace("\\", "/")
            webbrowser.open(url)
            self.report({'INFO'}, "Designer opened in browser.")
        else:
            self.report({'ERROR'}, f"Designer HTML not found in: {designer_dir}")
            return {'CANCELLED'}

        return {'FINISHED'}

class PIECREATOR_OT_PasteDesignerData(bpy.types.Operator):
    """Paste data from PieDesigner Clipboard"""
    bl_idname = "wm.pie_creator_paste_designer_data"
    bl_label = "Paste from Designer"
    bl_options = {'REGISTER', 'UNDO'}

    import_mode: bpy.props.EnumProperty(
        items=[
            ('APPEND', "Append New", "既存のメニューを残し、新しいものだけ追加します"),
            ('OVERWRITE', "Overwrite All", "現在の設定を全て消去し、コピーした内容で上書きします")
        ],
        name="Import Mode",
        default='APPEND'
    )

    def execute(self, context):
        clipboard = context.window_manager.clipboard
        if not clipboard:
            self.report({'ERROR'}, "Clipboard is empty.")
            return {'CANCELLED'}
        try:
            data = json.loads(clipboard)
        except:
            self.report({'ERROR'}, "Clipboard content is not valid JSON.")
            return {'CANCELLED'}
        if not isinstance(data, dict) or "type" not in data:
            self.report({'ERROR'}, "Unknown format. Please copy from PieDesigner.")
            return {'CANCELLED'}

        from ..storage import load_config, save_config, generate_unique_id
        config = load_config()
        existing_menus = config.get("menus", [])
        payload = data.get("payload")

        if data["type"] == "PIE_CREATOR_MENU":
            new_menu = payload
            new_menu["id"] = generate_unique_id(new_menu["id"], existing_menus)
            existing_menus.append(new_menu)
            self.report({'INFO'}, f"Appended Menu: {new_menu['name']}")
        elif data["type"] == "PIE_CREATOR_PROJECT":
            new_menus = payload.get("menus", [])
            if self.import_mode == 'OVERWRITE':
                config["menus"] = new_menus
                self.report({'INFO'}, f"Overwritten with {len(new_menus)} menus.")
            else:
                for nm in new_menus:
                    nm["id"] = generate_unique_id(nm["id"], existing_menus)
                    existing_menus.append(nm)
                self.report({'INFO'}, f"Merged {len(new_menus)} new menus.")

        save_config(config)
        bpy.ops.wm.pie_creator_reload()
        return {'FINISHED'}

    def invoke(self, context, event):
        clipboard = context.window_manager.clipboard
        try:
            data = json.loads(clipboard)
            if data.get("type") == "PIE_CREATOR_PROJECT":
                return context.window_manager.invoke_props_dialog(self)
        except: pass
        return self.execute(context)

class PIECREATOR_OT_CopyDesignerData(bpy.types.Operator):
    """Copy current config to clipboard for PieDesigner"""
    bl_idname = "wm.pie_creator_copy_designer_data"
    bl_label = "Copy for Designer"
    bl_options = {'REGISTER'}

    def execute(self, context):
        from ..storage import load_config
        config = load_config()
        data = {"type": "PIE_CREATOR_PROJECT", "payload": config}
        context.window_manager.clipboard = json.dumps(data, indent=2, ensure_ascii=False)
        self.report({'INFO'}, "Config copied for Designer.")
        return {'FINISHED'}

classes = (
    PIECREATOR_OT_OpenDesigner,
    PIECREATOR_OT_PasteDesignerData,
    PIECREATOR_OT_CopyDesignerData,
)
