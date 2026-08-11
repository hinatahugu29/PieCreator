"""ログ出力の共通口。

これまで登録処理やマスターメニュー呼び出しが無条件で print していたため、
メニューを開くたびにシステムコンソールが流れていた。開発中は有用だが日常
運用ではノイズなので、詳細ログはプリファレンスのトグルで切れるようにする。

一方 `log_error` は常に出す。握り潰した例外が無音になるのを避けるのが目的で、
これを黙らせると「押しても何も起きない」に逆戻りする。
"""

import bpy

_ADDON_KEY = __package__.split(".")[0]


def debug_enabled():
    """詳細ログを出すか。プリファレンスが読めない場面では出さない。"""
    try:
        addon = bpy.context.preferences.addons.get(_ADDON_KEY)
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
