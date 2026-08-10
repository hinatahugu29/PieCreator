"""pie_creator_v11 の実行コンテキスト補正とエラー通知を確認する。

    blender --background --factory-startup --python tests/test_exec_context.py
    blender             --factory-startup --python tests/test_exec_context.py

**GUI でも一度は走らせること。** 中核の「INVOKE_DEFAULT を付けると invoke()
から始まる」は --background では確認できない。バックグラウンドにはウィンドウも
イベントも無く、Blender は INVOKE を execute() にフォールバックさせるため、
補正が効いていても効いていなくても同じ結果になる。GUI 実行時は結果を
tests/_last_gui_result.txt に書き、Blender を自分で終了する。

なお wm.operators に操作履歴が積まれるのは実際の UI 操作を経たときだけで、
スクリプトからでは溜まらない。そのため右クリック → Capture Operator の
経路そのものは人が触って確かめるしかない。ここでは get_op_command が
組み立てる文字列だけを見ている。
"""
import os
import sys
import traceback

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_last_gui_result.txt")

sys.path.insert(0, REPO_ROOT)

import bpy

results = []


def check(name, condition, detail=""):
    results.append(("ok  " if condition else "FAIL", name, detail))


def run():
    trace = []

    class TEST_OT_probe(bpy.types.Operator):
        bl_idname = "test.pie_probe"
        bl_label = "Probe"

        def invoke(self, context, event):
            trace.append("invoke")
            return {'FINISHED'}

        def execute(self, context):
            trace.append("execute")
            return {'FINISHED'}

    import pie_creator_v11 as pc
    pc.register()
    bpy.utils.register_class(TEST_OT_probe)

    from pie_creator_v11.storage import ensure_exec_context
    from pie_creator_v11.ops.core import (
        execute_pie_command, get_op_command, auto_invoke_enabled,
    )

    # --- 文字列の組み立て ---
    for src, want in [
        ("bpy.ops.mesh.primitive_cube_add()",
         "bpy.ops.mesh.primitive_cube_add('INVOKE_DEFAULT')"),
        ("bpy.ops.mesh.primitive_cube_add(size=2.0)",
         "bpy.ops.mesh.primitive_cube_add('INVOKE_DEFAULT', size=2.0)"),
        ("bpy.ops.transform.translate()",
         "bpy.ops.transform.translate('INVOKE_DEFAULT')"),
        # 明示指定は尊重する（利用者による上書き）
        ("bpy.ops.object.delete('EXEC_DEFAULT')",
         "bpy.ops.object.delete('EXEC_DEFAULT')"),
        ("bpy.ops.wm.save_mainfile('INVOKE_DEFAULT')",
         "bpy.ops.wm.save_mainfile('INVOKE_DEFAULT')"),
        # bpy.ops 呼び出しでないものは触らない
        ("bpy.context.scene.frame_current = 5",
         "bpy.context.scene.frame_current = 5"),
        ("", ""),
        # 壊れた入力で例外を出さない
        ("bpy.ops.foo.bar(", "bpy.ops.foo.bar("),
        # 複数行
        ("bpy.ops.a.b()\nbpy.ops.c.d(x=1)",
         "bpy.ops.a.b('INVOKE_DEFAULT')\nbpy.ops.c.d('INVOKE_DEFAULT', x=1)"),
    ]:
        got = ensure_exec_context(src)
        check(f"ensure_exec_context: {src[:44]!r}", got == want,
              "" if got == want else f"got {got!r}")

    class FakeOp:
        bl_idname = "mesh.primitive_cube_add"
        bl_rna = None

    captured = get_op_command(FakeOp())
    check("get_op_command が INVOKE_DEFAULT を含めて返す",
          bool(captured) and "INVOKE_DEFAULT" in captured, f"captured={captured!r}")

    check("auto_invoke_enabled() が既定で True", auto_invoke_enabled() is True)

    # --- 失敗が呼び出し側に返るか ---
    ok, msg = execute_pie_command("bpy.ops.nonexistent.operator()", label="Bogus")
    check("存在しない操作で (False, メッセージ) が返る", ok is False and bool(msg), f"msg={msg!r}")

    ok, _ = execute_pie_command("", label="Empty")
    check("空コマンドで False が返る", ok is False)

    ok, msg = execute_pie_command("bpy.ops.test.pie_probe()", label="Probe")
    check("成功時は (True, '') が返る", ok is True and msg == "", f"msg={msg!r}")

    # --- 実行経路（GUI でのみ意味がある） ---
    trace.clear()
    exec("bpy.ops.test.pie_probe()", {"bpy": bpy})
    check("引数なしだと execute() だけが走る", trace == ["execute"], f"trace={trace}")

    if bpy.app.background:
        results.append(("skip", "補正すると invoke() から始まる",
                        "--background ではウィンドウもイベントも無く、"
                        "INVOKE は execute にフォールバックするため確認できない"))
    else:
        trace.clear()
        exec(ensure_exec_context("bpy.ops.test.pie_probe()"), {"bpy": bpy})
        check("補正すると invoke() から始まる", trace[:1] == ["invoke"], f"trace={trace}")


def report():
    out = []
    for mark, name, detail in results:
        out.append(f"[{mark}] {name}" + (f"  -- {detail}" if detail else ""))
    failed = [r for r in results if r[0] == "FAIL"]
    skipped = [r for r in results if r[0] == "skip"]
    out.append("-" * 60)
    out.append(f"{len(results) - len(failed) - len(skipped)} passed, "
               f"{len(failed)} failed, {len(skipped)} skipped"
               f"  ({'background' if bpy.app.background else 'GUI'})")
    text = "\n".join(out)

    print("\n" + text)
    if not bpy.app.background:
        with open(RESULT_FILE, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
    return bool(failed)


def main():
    try:
        run()
    except Exception:
        results.append(("FAIL", "例外で中断", traceback.format_exc()))
    failed = report()
    if bpy.app.background:
        sys.exit(1 if failed else 0)
    bpy.ops.wm.quit_blender()
    return None


if bpy.app.background:
    main()
else:
    # GUI ではウィンドウが立ち上がってから走らせる
    bpy.app.timers.register(main, first_interval=1.5)
