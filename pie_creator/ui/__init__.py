import bpy
import importlib
from ..log import log_debug, log_error
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
            log_error(f"UI クラス {cls.__name__} の登録に失敗した", e)

def unregister():
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception as e:
            # 未登録のクラスを外そうとするのは想定内
            log_debug(f"UI クラス {cls.__name__} の解除をスキップした: {type(e).__name__}: {e}")
