"""コマンド文字列の解析と整形。

このモジュールは **bpy に依存しない**。Blender を起動しなくても素の Python で
インポートでき、`tests/test_command_text.py` がそれを利用して単体テストする。
コマンド文字列を組み立てる処理は壊れても症状が「押しても何も起きない」に
なりがちで気付きにくいため、ここだけはテストで固定しておく。
"""

import re

# bpy.ops.foo.bar() の第1引数に置ける実行コンテキスト。
# https://docs.blender.org/api/current/bpy.ops.html
EXEC_CONTEXTS = frozenset({
    'INVOKE_DEFAULT', 'INVOKE_REGION_WIN', 'INVOKE_REGION_CHANNELS',
    'INVOKE_REGION_PREVIEW', 'INVOKE_AREA', 'INVOKE_SCREEN',
    'EXEC_DEFAULT', 'EXEC_REGION_WIN', 'EXEC_REGION_CHANNELS',
    'EXEC_REGION_PREVIEW', 'EXEC_AREA', 'EXEC_SCREEN',
})

_OPS_CALL_RE = re.compile(
    r"bpy\.ops\.[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*\s*\("
)

# Vector((1, 2, 3)) のような mathutils 型のリテラルを素のタプルに落とす。
_MATHUTILS_LITERAL_RES = tuple(
    (re.compile(r'%s\(\((.*?)\)\)' % name), r'(\1)')
    for name in ("Vector", "Euler", "Color", "Quaternion")
)


def ensure_exec_context(command, exec_context="INVOKE_DEFAULT"):
    """bpy.ops 呼び出しに実行コンテキストを補う。

    Python から `bpy.ops.foo.bar()` を引数なしで呼ぶと EXEC_DEFAULT になり、
    **invoke() を飛ばして execute() だけが走る。** 一方、パネルやメニューの
    ボタンが押されたときは INVOKE_DEFAULT で、invoke() から始まる。

    PieCreator はボタンから取り込んだ内容を文字列として保存して exec する
    ので、この差がそのまま落ちる。結果、invoke() に本体があるもの
    （ファイルブラウザを開く、ダイアログを出す、モーダルを開始する)が
    軒並み「押しても何も起きない」状態になっていた。

    たとえば `bpy.ops.transform.translate()` は EXEC では移動量ゼロで何も
    起きないが、INVOKE ならインタラクティブな移動が始まる。パイから呼んで
    欲しいのは後者で、それはボタンを押したときの挙動と一致する。

    invoke() を持たないオペレーターに INVOKE_DEFAULT を渡しても、Blender は
    execute() にフォールバックする。そのため一律に付けて差し支えない。

    すでに明示的な実行コンテキストが書かれている場合は触らない。利用者が
    項目エディタで `'EXEC_DEFAULT'` と書けば、それが優先される。
    """
    if not command or "bpy.ops." not in command:
        return command

    out = []
    pos = 0
    for m in _OPS_CALL_RE.finditer(command):
        out.append(command[pos:m.end()])
        pos = m.end()

        rest = command[pos:].lstrip()
        if not rest:
            continue

        # 明示指定があれば尊重する
        if rest[0] in "\"'":
            quote = rest[0]
            end = rest.find(quote, 1)
            if end != -1 and rest[1:end] in EXEC_CONTEXTS:
                continue

        out.append(f"'{exec_context}'" if rest[0] == ")" else f"'{exec_context}', ")

    out.append(command[pos:])
    return "".join(out)


def sanitize_command(command):
    """コマンドの不要なインデントや改行を整理し、Blender 固有の型表現を変換する"""
    if not command:
        return ""
    cmd = command.strip()
    for pattern, replacement in _MATHUTILS_LITERAL_RES:
        cmd = pattern.sub(replacement, cmd)
    return cmd


def format_arg(name, value):
    """`name=value` の形の引数文字列を作る。

    値は必ず repr() を通す。手で `f"{name}='{value}'"` と書くと、値に
    アポストロフィが入ったとき（"Bob's Cube" のようなオブジェクト名は普通に
    存在する）壊れた Python を生成してしまう。
    """
    return f"{name}={value!r}"
