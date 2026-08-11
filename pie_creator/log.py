# SPDX-License-Identifier: GPL-3.0-or-later
"""ログ出力の共通口。

これまで登録処理やマスターメニュー呼び出しが無条件で print していたため、
メニューを開くたびにシステムコンソールが流れていた。開発中は有用だが日常
運用ではノイズなので、詳細ログはプリファレンスのトグルで切れるようにする。

一方 `log_error` は常に出す。握り潰した例外が無音になるのを避けるのが目的で、
これを黙らせると「押しても何も起きない」に逆戻りする。
"""

import bpy

# アドオンのルートパッケージ名。プリファレンスを引くキーであり、
# AddonPreferences.bl_idname でもある。
#
# このモジュールはアドオン直下にあるので、__package__ がそのままルート
# パッケージ名になる。以前は各所で `__package__.split(".")[0]` と書いて
# いたが、これは Extensions 形式 (Blender 4.2 以降) で壊れる:
#
#   旧来のアドオン形式 : "pie_creator"                    -> "pie_creator"  OK
#   Extensions 形式    : "bl_ext.user_default.pie_creator" -> "bl_ext"      NG
#
# 壊れてもエラーは出ず、プリファレンスが引けずに既定値へ落ちるだけなので、
# 「設定を変えても効かない」という追いにくい症状になる。参照はここに集約する。
ADDON_ID = __package__


def debug_enabled():
    """詳細ログを出すか。プリファレンスが読めない場面では出さない。"""
    try:
        addon = bpy.context.preferences.addons.get(ADDON_ID)
        if addon and addon.preferences:
            return bool(getattr(addon.preferences, "debug_logging", False))
    except Exception:
        pass
    return False


def log_debug(message):
    """開発時だけ見たい情報。既定では出ない。"""
    if debug_enabled():
        print(f"[PieCreator] {message}")


def log_error(message, exc=None):
    """握り潰した失敗の記録。常に出す。"""
    if exc is not None:
        print(f"[PieCreator] {message}: {type(exc).__name__}: {exc}")
    else:
        print(f"[PieCreator] {message}")


# log_error_once で報告済みの失敗。キーごとに直近の内容を覚えておく。
_reported_once = {}


def log_error_once(key, message, exc=None):
    """毎フレーム通る場所（描画・タイマー）用の log_error。

    同じ失敗を繰り返し出すとコンソールが埋まって、肝心の別のエラーが
    流れてしまう。同一内容の間は最初の一度だけ出し、内容が変わるか
    `clear_error_once` で消されるまで黙る。

    実際に報告したときだけ True を返す。HUD 表示など、コンソール出力と
    足並みを揃えたい副作用の判定に使う。
    """
    signature = f"{message}: {type(exc).__name__}: {exc}" if exc is not None else message
    if _reported_once.get(key) == signature:
        return False
    _reported_once[key] = signature
    log_error(message, exc)
    return True


def clear_error_once(key):
    """成功したときに呼ぶ。次に同じ失敗が起きたら改めて報告される。"""
    _reported_once.pop(key, None)
