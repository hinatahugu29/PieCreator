import bpy
import os
import sys

# アドオンのパスを追加
addon_path = r"e:\blender_addon\PieCreator"
if addon_path not in sys.path:
    sys.path.append(addon_path)

# アドオンを有効化
addon_name = "pie_creator"
bpy.ops.preferences.addon_enable(module=addon_name)

# サンプルメニューを呼び出す
print("Calling sample_pie...")
bpy.ops.wm.pie_creator_call(menu_id="sample_pie")

print("Test script finished.")
