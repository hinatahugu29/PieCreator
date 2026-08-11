import bpy
import importlib
from . import preferences, menus, components

# リロード対応
if "preferences" in locals():
    importlib.reload(preferences)
    importlib.reload(menus)
    importlib.reload(components)

classes = (
    preferences.PIECREATOR_Preferences,
) + menus.classes

def register():
    for cls in classes:
        try:
            if hasattr(bpy.types, cls.__name__):
                bpy.utils.unregister_class(getattr(bpy.types, cls.__name__))
            bpy.utils.register_class(cls)
        except Exception as e:
            print(f"PieCreator UI: Failed to register {cls.__name__}: {e}")

def unregister():
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except:
            pass
