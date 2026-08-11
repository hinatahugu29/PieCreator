# SPDX-License-Identifier: GPL-3.0-or-later
import bpy
import importlib

from ..log import log_debug, log_error
from . import designer, core, macro, io, pool, ui_ops

# リロード対応
if "designer" in locals():
    importlib.reload(designer)
    importlib.reload(core)
    importlib.reload(macro)
    importlib.reload(io)
    importlib.reload(pool)
    importlib.reload(ui_ops)

# 機能ごとに分割されたオペレータークラスを収集
classes = []
classes.extend(designer.classes)
classes.extend(core.classes)
classes.extend(macro.classes)
classes.extend(io.classes)
classes.extend(pool.classes)
classes.extend(ui_ops.classes)

hud_handles = []

def register():
    # 0. 強制グローバルクリーンアップ (既存の PIECREATOR クラスを根こそぎ掃除)
    # これにより、リロード時や古いバージョンとの衝突を確実に防ぐ
    all_registered_classes = [attr for attr in dir(bpy.types) if attr.startswith("PIECREATOR_")]
    for attr in all_registered_classes:
        try:
            bpy.utils.unregister_class(getattr(bpy.types, attr))
        except Exception as e:
            # 掃除なので、外せないものがあっても続行する
            log_debug(f"事前クリーンアップで {attr} を外せなかった: {type(e).__name__}: {e}")

    for cls in classes:
        # 個別のクリーンアップ（念のため）
        if hasattr(bpy.types, cls.__name__):
            try:
                bpy.utils.unregister_class(getattr(bpy.types, cls.__name__))
            except Exception as e:
                log_debug(f"{cls.__name__} の再登録前の解除に失敗した: {type(e).__name__}: {e}")

        try:
            bpy.utils.register_class(cls)
        except Exception as e:
            # 既に登録されているエラーが出ても致命的でない場合はスキップ
            if "already registered" not in str(e):
                log_error(f"オペレーター {cls.__name__} の登録に失敗した", e)

    # HUD Draw Handler 登録
    global hud_handles
    from .core import draw_hud_callback
    space_types = [
        ('SpaceView3D', 'WINDOW'),
        ('SpaceNodeEditor', 'WINDOW'),
        ('SpaceImageEditor', 'WINDOW'),
        ('SpaceSequenceEditor', 'WINDOW'),
        ('SpaceTextEditor', 'WINDOW'),
    ]
    for st_name, region in space_types:
        try:
            st = getattr(bpy.types, st_name)
            handle = st.draw_handler_add(draw_hud_callback, (st_name,), region, 'POST_PIXEL')
            hud_handles.append((st, handle, region))
        except Exception as e:
            # このスペースタイプが無い Blender もあり得る。HUD が出ないだけで
            # 致命的ではないが、出ない理由が分からないと調べようがない。
            log_error(f"{st_name} への HUD 描画ハンドラの登録に失敗した", e)

def unregister():
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception as e:
            log_debug(f"{cls.__name__} の解除をスキップした: {type(e).__name__}: {e}")

    # HUD Draw Handler 解除
    global hud_handles
    for st, handle, region in hud_handles:
        try:
            st.draw_handler_remove(handle, region)
        except Exception as e:
            log_error(f"HUD 描画ハンドラの解除に失敗した ({region})", e)
    hud_handles.clear()

