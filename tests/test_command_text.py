"""pie_creator.command_text の単体テスト。

Blender を起動せず、素の Python で走らせる:

    python -m unittest discover -s tests -v

コマンド文字列の組み立ては、壊れても症状が「押しても何も起きない」に
なりやすく、Blender 上で目視確認しても気付きにくい。ここだけは自動で
固定しておく。
"""

import importlib.util
import os
import unittest

# `import pie_creator.command_text` にすると pie_creator/__init__.py が走り、
# そこで bpy を読むため Blender の外では失敗する。テスト対象は bpy に依存
# しないので、パッケージを介さずファイルから直接読み込む。
_MODULE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "pie_creator", "command_text.py",
)
_spec = importlib.util.spec_from_file_location("pc_command_text", _MODULE_PATH)
command_text = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(command_text)

ensure_exec_context = command_text.ensure_exec_context
sanitize_command = command_text.sanitize_command
format_arg = command_text.format_arg


class TestEnsureExecContext(unittest.TestCase):
    def test_引数なしの呼び出しに補う(self):
        self.assertEqual(
            ensure_exec_context("bpy.ops.wm.save_mainfile()"),
            "bpy.ops.wm.save_mainfile('INVOKE_DEFAULT')",
        )

    def test_引数ありの呼び出しでは区切りを付けて補う(self):
        self.assertEqual(
            ensure_exec_context("bpy.ops.mesh.primitive_cube_add(size=2)"),
            "bpy.ops.mesh.primitive_cube_add('INVOKE_DEFAULT', size=2)",
        )

    def test_既に実行コンテキストがあれば触らない(self):
        for original in (
            "bpy.ops.wm.save_mainfile('EXEC_DEFAULT')",
            "bpy.ops.wm.save_mainfile('INVOKE_DEFAULT')",
            'bpy.ops.transform.translate("EXEC_REGION_WIN", value=(1, 0, 0))',
        ):
            with self.subTest(original=original):
                self.assertEqual(ensure_exec_context(original), original)

    def test_利用者が書いた_EXEC_DEFAULT_が優先される(self):
        # プリファレンスの自動付与より、項目に書いた指定を尊重する
        original = "bpy.ops.object.delete('EXEC_DEFAULT')"
        self.assertEqual(ensure_exec_context(original), original)

    def test_マクロの複数コマンドすべてに補う(self):
        self.assertEqual(
            ensure_exec_context("bpy.ops.object.select_all(); bpy.ops.object.delete()"),
            "bpy.ops.object.select_all('INVOKE_DEFAULT'); bpy.ops.object.delete('INVOKE_DEFAULT')",
        )

    def test_混在したマクロでは足りないものだけ補う(self):
        self.assertEqual(
            ensure_exec_context("bpy.ops.a.b('EXEC_DEFAULT'); bpy.ops.c.d()"),
            "bpy.ops.a.b('EXEC_DEFAULT'); bpy.ops.c.d('INVOKE_DEFAULT')",
        )

    def test_実行コンテキストを明示的に指定できる(self):
        self.assertEqual(
            ensure_exec_context("bpy.ops.wm.quit_blender()", "EXEC_DEFAULT"),
            "bpy.ops.wm.quit_blender('EXEC_DEFAULT')",
        )

    def test_bpy_ops_でない文字列は素通し(self):
        for original in (
            "bpy.context.object.location.x = 5",
            "print('hello')",
            "",
        ):
            with self.subTest(original=original):
                self.assertEqual(ensure_exec_context(original), original)

    def test_None_を渡しても落ちない(self):
        self.assertIsNone(ensure_exec_context(None))

    def test_実行コンテキストに見えるだけの第1引数は補う対象(self):
        # 'MESH' は実行コンテキストではないので、前に補う必要がある
        self.assertEqual(
            ensure_exec_context("bpy.ops.object.add(type='MESH')"),
            "bpy.ops.object.add('INVOKE_DEFAULT', type='MESH')",
        )

    def test_呼び出し括弧の直後に空白があっても壊れない(self):
        # 引数が無いので区切りのカンマは不要。空白はそのまま後ろに残る。
        self.assertEqual(
            ensure_exec_context("bpy.ops.wm.save_mainfile( )"),
            "bpy.ops.wm.save_mainfile('INVOKE_DEFAULT' )",
        )

    def test_生成結果は常に構文として妥当(self):
        # 補った結果が壊れた Python になっていないことを構文解析で確かめる。
        # ここが崩れると症状は「押しても何も起きない」になり、原因が見えない。
        import ast
        for original in (
            "bpy.ops.wm.save_mainfile()",
            "bpy.ops.wm.save_mainfile( )",
            "bpy.ops.mesh.primitive_cube_add(size=2)",
            "bpy.ops.object.add(type='MESH')",
            "bpy.ops.a.b(); bpy.ops.c.d()",
            "bpy.ops.a.b('EXEC_DEFAULT'); bpy.ops.c.d()",
            "bpy.ops.transform.translate(value=(1, 0, 0))",
            "bpy.ops.object.rename(name=\"Bob's Cube\")",
        ):
            with self.subTest(original=original):
                ast.parse(ensure_exec_context(original))


class TestSanitizeCommand(unittest.TestCase):
    def test_前後の空白を落とす(self):
        self.assertEqual(sanitize_command("  bpy.ops.a.b()\n"), "bpy.ops.a.b()")

    def test_mathutils_のリテラルを素のタプルにする(self):
        self.assertEqual(
            sanitize_command("bpy.ops.transform.translate(value=Vector((1.0, 0.0, 0.0)))"),
            "bpy.ops.transform.translate(value=(1.0, 0.0, 0.0))",
        )

    def test_Euler_Color_Quaternion_も変換する(self):
        self.assertEqual(sanitize_command("f(r=Euler((0.0, 0.0, 1.5)))"), "f(r=(0.0, 0.0, 1.5))")
        self.assertEqual(sanitize_command("f(c=Color((1.0, 0.0, 0.0)))"), "f(c=(1.0, 0.0, 0.0))")
        self.assertEqual(sanitize_command("f(q=Quaternion((1.0, 0.0, 0.0, 0.0)))"), "f(q=(1.0, 0.0, 0.0, 0.0))")

    def test_空文字と_None_は空文字になる(self):
        self.assertEqual(sanitize_command(""), "")
        self.assertEqual(sanitize_command(None), "")


class TestFormatArg(unittest.TestCase):
    def test_アポストロフィ入りの値でも壊れない(self):
        # "Bob's Cube" のようなオブジェクト名は普通に存在する。
        # 手で引用符を付けていた頃は、ここで壊れた Python が生成されていた。
        arg = format_arg("name", "Bob's Cube")
        namespace = {}
        exec(f"result = dict({arg})", {}, namespace)
        self.assertEqual(namespace["result"], {"name": "Bob's Cube"})

    def test_バックスラッシュ入りの値でも壊れない(self):
        arg = format_arg("filepath", r"C:\tmp\new.blend")
        namespace = {}
        exec(f"result = dict({arg})", {}, namespace)
        self.assertEqual(namespace["result"], {"filepath": r"C:\tmp\new.blend"})

    def test_真偽値と数値はそのまま読める形になる(self):
        self.assertEqual(format_arg("use_x", True), "use_x=True")
        self.assertEqual(format_arg("count", 3), "count=3")

    def test_生成した引数はそのまま評価できる(self):
        for value in ("plain", "quote'inside", 'double"inside', True, 0, 1.5, None):
            with self.subTest(value=value):
                namespace = {}
                exec(f"result = dict({format_arg('v', value)})", {}, namespace)
                self.assertEqual(namespace["result"]["v"], value)


if __name__ == "__main__":
    unittest.main()
