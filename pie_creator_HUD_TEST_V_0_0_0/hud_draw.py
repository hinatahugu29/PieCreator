import bpy
import gpu
import blf
import time
from gpu_extras.batch import batch_for_shader
import math

# --- 1. GPU Renderer (描画の最小単位) ---

class HUD_Renderer:
    def __init__(self):
        self.shader = None
        self.tex_shader = None
        self.rrect_shader = None
        self.font_id = 0
        self._batch_cache = {}

    def ensure_shaders(self):
        if self.shader: return
        
        def get_shader(name):
            try: return gpu.shader.from_builtin(name)
            except: return gpu.shader.from_builtin('2D_' + name)

        # Use built-in shaders for standard tasks
        self.shader = get_shader('SMOOTH_COLOR')
        self.tex_shader = get_shader('IMAGE_COLOR')

        # Custom Rounded Rect Shader
        try:
            shader_info = gpu.types.GPUShaderCreateInfo()
            shader_info.push_constant('MAT4', 'ModelViewProjectionMatrix')
            shader_info.push_constant('VEC4', 'color')
            shader_info.push_constant('VEC2', 'size')
            shader_info.push_constant('FLOAT', 'radius')
            
            shader_info.vertex_in(0, 'VEC2', 'pos')
            shader_info.vertex_out(0, 'VEC2', 'v_pos')
            
            shader_info.vertex_source(
                "void main() {"
                "  v_pos = pos;"
                "  gl_Position = ModelViewProjectionMatrix * vec4(pos, 0.0, 1.0);"
                "}"
            )
            
            shader_info.fragment_source(
                "float sdRoundRect(vec2 p, vec2 b, float r) {"
                "  vec2 d = abs(p) - b + r;"
                "  return min(max(d.x, d.y), 0.0) + length(max(d, 0.0)) - r;"
                "}"
                "void main() {"
                "  float d = sdRoundRect(v_pos, size * 0.5, radius);"
                "  if (d > 0.0) discard;"
                "  "
                "  float alpha = smoothstep(0.0, -1.5, d);"
                "  float border = smoothstep(-1.0, -2.5, d);"
                "  vec3 final_color = mix(color.rgb + 0.2, color.rgb, border);"
                "  fragColor = vec4(final_color, color.a * alpha);"
                "}"
            )
            shader_info.fragment_out(0, 'VEC4', 'fragColor')
            
            self.rrect_shader = gpu.shader.create_from_info(shader_info)
        except Exception as e:
            print(f"PieCreator HUD: Failed to create custom shader: {e}")
            try: self.rrect_shader = gpu.shader.from_builtin('UNIFORM_COLOR')
            except: self.rrect_shader = gpu.shader.from_builtin('2D_UNIFORM_COLOR')

    def draw_primitive(self, batch_key, create_func, matrix=None):
        self.ensure_shaders()
        if batch_key not in self._batch_cache:
            self._batch_cache[batch_key] = create_func()
        
        if matrix:
            gpu.matrix.push()
            gpu.matrix.multiply_matrix(matrix)
            
        try:
            self.shader.bind()
            self._batch_cache[batch_key].draw(self.shader)
        finally:
            if matrix:
                gpu.matrix.pop()

    def draw_rounded_rect(self, w, h, radius, color, matrix=None):
        self.ensure_shaders()
        batch_key = "UNIT_QUAD"
        if batch_key not in self._batch_cache:
            coords = [(-0.5,-0.5), (0.5,-0.5), (-0.5,0.5), (0.5,0.5)]
            indices = [(0,1,2), (1,3,2)]
            self._batch_cache[batch_key] = batch_for_shader(self.rrect_shader, 'TRIS', {"pos": coords}, indices=indices)
        
        gpu.matrix.push()
        if matrix:
            gpu.matrix.multiply_matrix(matrix)
        gpu.matrix.scale((w, h, 1.0))
        
        try:
            self.rrect_shader.bind()
            try:
                self.rrect_shader.uniform_float("color", color)
                self.rrect_shader.uniform_float("size", (w, h))
                self.rrect_shader.uniform_float("radius", radius)
            except: pass
            self._batch_cache[batch_key].draw(self.rrect_shader)
        finally:
            gpu.matrix.pop()

    def draw_texture(self, texture, color=(1,1,1,1), matrix=None):
        self.ensure_shaders()
        batch_key = "UNIT_QUAD_TEX"
        if batch_key not in self._batch_cache:
            coords = [(-0.5,-0.5), (0.5,-0.5), (-0.5,0.5), (0.5,0.5)]
            uvs = [(0,0), (1,0), (0,1), (1,1)]
            indices = [(0,1,2), (1,3,2)]
            self._batch_cache[batch_key] = batch_for_shader(self.tex_shader, 'TRIS', {"pos": coords, "texCoord": uvs}, indices=indices)
        
        if matrix:
            gpu.matrix.push()
            gpu.matrix.multiply_matrix(matrix)
            
        try:
            self.tex_shader.bind()
            self.tex_shader.uniform_sampler("image", texture)
            self.tex_shader.uniform_float("color", color)
            self._batch_cache[batch_key].draw(self.tex_shader)
        finally:
            if matrix:
                gpu.matrix.pop()

    def draw_text(self, text, x, y, size=14, color=(1,1,1,1)):
        try:
            blf.size(self.font_id, int(size))
            blf.color(self.font_id, *color)
            w, h = blf.dimensions(self.font_id, text)
            blf.position(self.font_id, x - w/2, y - h/2, 0)
            blf.enable(self.font_id, blf.SHADOW)
            blf.shadow(self.font_id, 3, 0, 0, 0, 0.5)
            blf.draw(self.font_id, text)
            blf.disable(self.font_id, blf.SHADOW)
        except: pass

# --- 2. Geometry Logic (数学とレイアウト) ---

class HUD_Geometry:
    @staticmethod
    def get_radial_hit(dx, dy, inner, outer, num_items):
        if num_items == 0: return None
        dist = math.sqrt(dx*dx + dy*dy)
        if inner <= dist <= outer:
            angle = math.atan2(dy, dx)
            if angle < 0: angle += 2 * math.pi
            return int(angle / ((2 * math.pi) / num_items))
        return None

    @staticmethod
    def get_grid_hit(dx, dy, cols, cell_w, cell_h, num_items):
        if num_items == 0 or cols == 0: return None
        rows = math.ceil(num_items / cols)
        tw, th = cols * cell_w, rows * cell_h
        gx, gy = dx + tw/2, dy + th/2
        if 0 <= gx <= tw and 0 <= gy <= th:
            c = int(gx / cell_w)
            r = (rows - 1) - int(gy / cell_h)
            idx = r * cols + c
            return idx if idx < num_items else None
        return None

# --- 3. Session Manager (状態管理) ---

class HUD_Session:
    def __init__(self):
        self.start_time = 0
        self.origin = (0, 0)
        self.active_hit = (None, None)
        self.initial_module_index = -1

    def start(self, mouse_pos):
        self.start_time = time.time()
        self.origin = mouse_pos

    def get_anim_factor(self, duration=0.25):
        t = (time.time() - self.start_time) / duration
        return min(1.0, 1.0 - math.pow(2, -10 * t))

# --- 4. Main Drawer (統括エンジン) ---

class HUD_Drawer:
    def __init__(self):
        self.renderer = HUD_Renderer()
        self.session = HUD_Session()
        self.geo = HUD_Geometry()

    def init_session(self, module_index=-1):
        self.session.initial_module_index = module_index
        self.session.origin = None

    def create_arc_batch(self, inner, outer, start, end, color_top, color_bottom):
        def _create():
            coords, colors, indices = [], [], []
            steps = 24
            step_a = (end - start) / steps
            for i in range(steps + 1):
                a = start + i * step_a
                s, c = math.sin(a), math.cos(a)
                coords.append((c * inner, s * inner))
                coords.append((c * outer, s * outer))
                colors.append(color_bottom)
                colors.append(color_top)
                if i < steps:
                    idx = i * 2
                    indices.append((idx, idx + 1, idx + 2))
                    indices.append((idx + 1, idx + 3, idx + 2))
            return batch_for_shader(self.renderer.shader, 'TRIS', {"pos": coords, "color": colors}, indices=indices)
        return _create

    def get_icon_texture(self, icon_name):
        if not icon_name or icon_name == 'NONE': return None
        if not hasattr(self, "_icon_tex_cache"): self._icon_tex_cache = {}
        if icon_name not in self._icon_tex_cache:
            try:
                icon_id = bpy.types.UILayout.bl_rna.functions['prop'].parameters['icon'].enum_items.get(icon_name)
                if icon_id:
                    self._icon_tex_cache[icon_name] = gpu.texture.from_icon(icon_id.value)
                else:
                    self._icon_tex_cache[icon_name] = None
            except:
                self._icon_tex_cache[icon_name] = None
        return self._icon_tex_cache[icon_name]

    def draw_module(self, mod, m_idx, alpha, scale, slide, mx, my):
        cx, cy = self.session.origin
        ox = cx + mod.offset_x + (slide if mod.offset_x >= 0 else -slide)
        oy = cy + mod.offset_y
        dx, dy = mx - ox, my - oy
        
        active_item = -1
        if mod.type == 'RADIAL':
            hit = self.geo.get_radial_hit(dx, dy, mod.inner_r * scale, mod.outer_r * scale, len(mod.items))
        else:
            hit = self.geo.get_grid_hit(dx, dy, mod.columns, mod.cell_w * scale, mod.cell_h * scale, len(mod.items))
        
        if hit is not None:
            active_item = hit
            self.session.active_hit = (m_idx, hit)

        for i, item in enumerate(mod.items):
            is_hover = (i == active_item)
            base_col = list(mod.color)
            if is_hover: 
                base_col = [min(1.0, c + 0.3) for c in base_col[:3]] + [1.0]
            
            c_top = (base_col[0], base_col[1], base_col[2], base_col[3] * alpha)
            c_bot = (base_col[0]*0.7, base_col[1]*0.7, base_col[2]*0.7, base_col[3]*0.5 * alpha)
            
            icon_tex = self.get_icon_texture(item.icon)
            
            if mod.type == 'RADIAL':
                a_w = (2 * math.pi) / len(mod.items) if len(mod.items) > 0 else 1
                start, end = i * a_w + 0.02, (i+1) * a_w - 0.02
                key = ('ARC_GRAD', mod.inner_r, mod.outer_r, len(mod.items), i, c_top, c_bot)
                
                gpu.matrix.push()
                try:
                    gpu.matrix.translate((ox, oy, 0))
                    gpu.matrix.scale((scale, scale, 1.0))
                    self.renderer.draw_primitive(key, self.create_arc_batch(mod.inner_r, mod.outer_r, start, end, c_top, c_bot))
                finally:
                    gpu.matrix.pop()
                
                ma, mr = (start + end)/2, (mod.inner_r + mod.outer_r)/2
                tx, ty = ox + math.cos(ma) * mr * scale, oy + math.sin(ma) * mr * scale
                
                if icon_tex:
                    gpu.matrix.push()
                    try:
                        gpu.matrix.translate((tx, ty + 10 * scale, 0))
                        gpu.matrix.scale((24 * scale, 24 * scale, 1.0))
                        self.renderer.draw_texture(icon_tex, color=(1,1,1,alpha))
                    finally:
                        gpu.matrix.pop()
                    ty -= 10 * scale
                
                label = item.label + (" >" if item.link_module else "")
                self.renderer.draw_text(label, tx, ty, size=int(14*scale), color=(1,1,1,alpha))

            else:
                cols = mod.columns
                r, c = divmod(i, cols)
                rows = math.ceil(len(mod.items) / cols)
                tw = cols * mod.cell_w
                th = rows * mod.cell_h
                bx = (c * mod.cell_w - tw / 2) * scale
                by = ((rows - 1 - r) * mod.cell_h - th / 2) * scale
                bw, bh = (mod.cell_w - 6) * scale, (mod.cell_h - 4) * scale
                
                gpu.matrix.push()
                try:
                    gpu.matrix.translate((ox + bx + bw/2, oy + by + bh/2, 0))
                    self.renderer.draw_rounded_rect(bw, bh, 8 * scale, c_top)
                finally:
                    gpu.matrix.pop()
                
                tx, ty = ox + bx + bw/2, oy + by + bh/2
                if icon_tex:
                    gpu.matrix.push()
                    try:
                        gpu.matrix.translate((ox + bx + 18 * scale, ty, 0))
                        gpu.matrix.scale((20 * scale, 20 * scale, 1.0))
                        self.renderer.draw_texture(icon_tex, color=(1,1,1,alpha))
                    finally:
                        gpu.matrix.pop()
                    tx += 12 * scale
                
                self.renderer.draw_text(item.label, tx, ty, size=int(13*scale), color=(1,1,1,alpha))

    def draw(self, context, mx, my):
        if self.session.origin is None:
            self.session.start((mx, my))
        
        t = self.session.get_anim_factor()
        alpha, scale = t, 0.9 + 0.1 * t
        slide = (1.0 - t) * 60
        
        prefs = context.preferences.addons[__package__].preferences
        gpu.state.blend_set('ALPHA')
        
        self.session.active_hit = (None, None)
        mode = context.mode
        
        for m_idx, mod in enumerate(prefs.modules):
            is_initial = (m_idx == self.session.initial_module_index)
            if not is_initial:
                if not mod.is_visible: continue
                if mod.show_mode != 'ALL' and mod.show_mode != mode: continue
            
            try:
                self.draw_module(mod, m_idx, alpha, scale, slide, mx, my)
            except: pass
            
        gpu.state.blend_set('NONE')

    def get_last_hit(self):
        return self.session.active_hit

_drawer = HUD_Drawer()
def draw_callback(self, context):
    if hasattr(self, "mouse_pos"):
        try:
            _drawer.draw(context, self.mouse_pos[0], self.mouse_pos[1])
        except Exception as e:
            print(f"PieCreator HUD Error: {e}")
