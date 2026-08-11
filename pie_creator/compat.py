# SPDX-License-Identifier: GPL-3.0-or-later
"""Blender のバージョン差を吸収する層。

対応範囲は Blender 4.2 LTS 以降（`bl_info` と `blender_manifest.toml` の
宣言と揃えること）。

かつてここには gpu シェーダー名の `2D_` プレフィックス有無を吸収する
`get_shader` があったが、プレフィックスが落ちたのは 4.0 なので 4.2 以降だけを
見るなら不要で、しかもどこからも呼ばれていなかったため削除した。同様に未使用
だった `BLENDER_VERSION` も外している。バージョン分岐を足すときは、実際に
呼ぶ場所とセットで入れる。
"""

import blf

from .log import clear_error_once, log_error_once


def safe_draw_text(font_id, text, x, y, size=20, color=(1.0, 0.8, 0.2, 1.0)):
    """HUD 用のテキスト描画。

    描画ハンドラから毎フレーム呼ばれるので、ここで例外を上げると Blender の
    描画そのものを巻き込む。失敗しても握り潰さずに理由だけ残す。
    """
    try:
        blf.size(font_id, size)

        # 影付けはバージョンによって挙動が違う。出なくても本質的な問題では
        # ないので、ここだけは失敗しても続行する。
        try:
            blf.enable(font_id, blf.SHADOW)
            blf.shadow(font_id, 3, 0.0, 0.0, 0.0, color[3])
            blf.shadow_offset(font_id, 2, -2)
        except Exception as e:
            log_error_once("hud_shadow", "HUD テキストの影付けに失敗した（描画は続行）", e)

        blf.color(font_id, color[0], color[1], color[2], color[3])
        blf.position(font_id, x, y, 0)
        blf.draw(font_id, text)
        clear_error_once("hud_draw")
    except Exception as e:
        log_error_once("hud_draw", "テキストの描画に失敗した", e)
