# CLAUDE.md

## このリポジトリについて

Blender アドオン「PieCreator」。アドオン本体は `pie_creator/` のみで、
それ以外はドキュメント・生成データ・使い捨てスクリプト。
全体像は [README.md](README.md) を参照。

## 最重要ルール

**バージョンを上げるときに新しいフォルダを作らない。**
`pie_creator_v12/` のようなコピーは作らず、`pie_creator/` を直接編集して
コミットする。世代の区切りは Git のタグ（`v11.0.0` 形式）で表す。
かつてフォルダで世代管理していた名残が Git 履歴にあるが、その方式には戻さない。

## 編集する場所

| やりたいこと | 触るファイル |
|---|---|
| 登録・キーマップ・プロパティ定義 | `pie_creator/__init__.py` |
| メニュー呼び出し / コマンド実行 | `pie_creator/ops/core.py` |
| マクロ（`;` 区切りの連結実行） | `pie_creator/ops/macro.py` |
| 設定のインポート / エクスポート | `pie_creator/ops/io.py` |
| PieDesigner との連携・カタログ生成 | `pie_creator/ops/designer.py` |
| プリファレンス画面の見た目 | `pie_creator/ui/components.py`, `ui/preferences.py` |
| 外部エディタ（Web UI） | `pie_creator/designer/app.js`, `index.html` |
| 設定ファイルの読み書き | `pie_creator/storage.py` |
| コマンド文字列の組み立て・整形 | `pie_creator/command_text.py` |
| Blender バージョン差の吸収 | `pie_creator/compat.py` |
| ログ出力 | `pie_creator/log.py` |

`pie_creator/designer/blender_catalog.js` は `ops/designer.py` が実行時に
生成する成果物。手で編集しない。

## コミットの流儀

- **1 コミット 1 目的**。「UI 修正とバグ修正」を混ぜない。
- メッセージは**日本語で、何をしたかを一文**。既存の履歴は英語だが、
  読み手が本人なので日本語で構わない。「〜を修正」「〜を追加」の形で書く。
- 動作確認していない変更をコミットしない。Blender 上で読み込めるか、
  最低限 `tests/test_addon.py` を実行して確かめる。
- `bl_info` の `version` を上げるのはリリース時だけ。上げたらタグを打つ。

## コミットしないもの

`.gitignore` で除外済み。追加でコミットしないもの:

- 配布用 zip（`*.zip`）。その都度作り直すので履歴に入れない
- `__pycache__/`、`*.pyc`
- `scratch/` に新しく作った使い捨てスクリプト（既存分は履歴として残している）

## エラーの扱い

**裸の `except:` を書かない。** 必ず `except Exception as e:` にして、
`log.py` の `log_debug` / `log_error` のどちらかで理由を残す。

- `log_error` — 利用者が困る失敗。常にコンソールへ出る
- `log_debug` — 全走査で数件必ず出る類の失敗や、詳細な内部ログ。
  プリファレンスの "Verbose console log" が ON のときだけ出る

`print()` を直接書かない。かつて登録処理とメニュー呼び出しが無条件に
print していて、コンソールが流れて肝心のエラーが埋もれていた。

握り潰した失敗は「押しても何も起きない」という最悪の症状になる。
オペレーターの中なら `self.report({'ERROR'}, ...)` で画面にも出す。

毎フレーム通る箇所（描画・タイマー）で `log_error` を使わない。同じ
失敗でコンソールが埋まる。`log_debug` にするか、`macro.py` の
`_last_timer_error` のように同一の失敗を一度だけ報告する。

## コマンド文字列を組み立てるとき

引数の値は必ず `command_text.format_arg` か `repr()` を通す。
`f"{name}='{value}'"` と手で引用符を付けると、値にアポストロフィが
入ったとき（`Bob's Cube` のようなオブジェクト名は普通に存在する）
壊れた Python を生成する。

## 動作確認

`command_text.py` は `bpy` に依存しない。ここを触ったら Blender 抜きで
テストが走る:

```
python -m unittest discover -s tests
```

Blender が要る確認は `tests/test_addon.py`。Scripting ワークスペースで
実行すると、アドオンを有効化してサンプルパイメニューを呼び出すところまで
通る。スクリプト内の `addon_path` はこのリポジトリの絶対パスを指している
ので、別の場所にクローンしたら書き換える。
