import bpy
import blf

BLENDER_VERSION = bpy.app.version

def get_shader(shader_name):
    """Blender 4.x / 5.0 / 5.1 / 5.2 互換シェーダー取得"""
    import gpu
    
    # 5.1/5.2 以降で '2D_' プリフィックスが削除されたシェーダーに対応
    try:
        return gpu.shader.from_builtin(shader_name)
    except ValueError:
        # '2D_' プレフィックスを削除して再試行
        if shader_name.startswith("2D_"):
            fallback_name = shader_name[3:]
            try:
                return gpu.shader.from_builtin(fallback_name)
            except ValueError:
                pass
        # 逆に '2D_' プレフィックスを付与して再試行
        else:
            fallback_name = f"2D_{shader_name}"
            try:
                return gpu.shader.from_builtin(fallback_name)
            except ValueError:
                pass
        raise

def safe_draw_text(font_id, text, x, y, size=20, color=(1.0, 0.8, 0.2, 1.0)):
    """Blender 4.x〜5.2 互換の安全なテキスト描画"""
    try:
        blf.size(font_id, size)
        
        # blf.enable / shadow はバージョンによって挙動が異なるため安全保護
        try:
            blf.enable(font_id, blf.SHADOW)
            blf.shadow(font_id, 3, 0.0, 0.0, 0.0, color[3])
            blf.shadow_offset(font_id, 2, -2)
        except Exception:
            pass
            
        blf.color(font_id, color[0], color[1], color[2], color[3])
        blf.position(font_id, x, y, 0)
        blf.draw(font_id, text)
    except Exception as e:
        print(f"[PieCreator Compat] Text draw error: {e}")
