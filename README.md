# PieCreator

Blender 用のパイメニュー作成アドオン。任意の Blender オペレーターやマクロを、
コンテキストに応じて切り替わる階層型パイメニューとして組み立てられる。

- **Blender**: 4.2 LTS 以降
- **バージョン**: 11.0.0
- **作者**: hinata_hugu
- **ライセンス**: GPL-3.0-or-later（[LICENSE](LICENSE)）

## インストール

Blender 4.2 以降は Extensions 形式を推奨する:

```
blender --command extension build --source-dir pie_creator
```

生成された zip を `Edit > Preferences > Get Extensions > Install from Disk`
で読み込む。旧来のアドオン形式で入れる場合は `pie_creator/` を zip に固めて
`Add-ons > Install from Disk` を使う。

有効化すると `Preferences > Add-ons > PieCreator` に設定 UI が出る。

使い方は [docs/user-guide.md](docs/user-guide.md)（英語）を参照。

### メタデータは二重に持っている

| ファイル | 使われる場面 |
|---|---|
| `pie_creator/blender_manifest.toml` | Extensions 形式（Blender 4.2 以降） |
| `pie_creator/__init__.py` の `bl_info` | 旧来のアドオン形式 |

**バージョンと対応 Blender を上げるときは必ず両方直す。** 片方だけだと
配布形式によって表示が食い違う。

## リポジトリ構成

| パス | 中身 |
|---|---|
| `pie_creator/` | **アドオン本体。配布物はこのフォルダのみ** |
| `pie_creator/ops/` | オペレーター（コア・マクロ・IO・デザイナー連携・プール） |
| `pie_creator/ui/` | プリファレンス UI とメニュー定義 |
| `pie_creator/designer/` | 外部メニューエディタ（HTML/JS の PieDesigner） |
| `pie_creator/tools/` | ハンドブック生成などの補助ツール |
| `docs/user-guide.md` | **利用者向けマニュアル（英語・配布物に添える想定）** |
| `docs/` | 設計メモ・旧マニュアル・ロードマップ（開発者向け） |
| `docs/html/` | 生成済み HTML（マニュアル、ハンドブック、ロゴアニメ、プロトタイプ） |
| `data/` | 生成データ（Blender API カタログ、メニュー階層 JSON） |
| `tests/` | Blender 上で走らせる検証スクリプト |
| `scratch/` | 使い捨ての調査スクリプトと作業ログ。参照専用 |
| `LICENSE` | GPL-3.0 全文 |

`data/blender_catalog.json` はアドオンからは読まれない。PieDesigner の
「Load Catalog」で読み込む用の書き出し済みデータで、アドオン側は実行時に
`pie_creator/designer/blender_catalog.js` を生成する。

## 設定ファイルの取り扱い（重要）

メニュー項目の `command` は、呼び出された時点で `exec()` に渡される。
これは「Blender API へ制限なくアクセスできる」という設計上の狙いだが、
裏返すと **設定ファイルの取り込みは任意の Python の実行を意味する**。

- 出所の分からない `.json` をインポートしない
- PieDesigner からの貼り付けも同じ扱い

上書きを伴う操作（設定のインポート、Designer からの Overwrite All）は、
実行前に現在の設定を同じフォルダの `menus.backup.json` に退避する。

## テスト

コマンド文字列を組み立てる処理は `pie_creator/command_text.py` にあり、
`bpy` に依存しない。Blender なしで単体テストが走る:

```
python -m unittest discover -s tests
```

`tests/test_addon.py` は Blender の Scripting ワークスペースで実行する
スモークテストで、こちらは Blender が要る。

## 開発

過去は `pie_creator_v1` 〜 `v11` とフォルダを増やして世代管理していたが、
現在は `pie_creator/` 一本を Git の履歴で追う方式に統一している。
旧世代のコードは Git 履歴とローカルの zip に残っている。

作業ルールは [CLAUDE.md](CLAUDE.md) を参照。

## ライセンス

GPL-3.0-or-later。`bpy` を import する Blender アドオンは Blender の派生物
として扱われるため、GPL 系での配布になる。有償販売は GPL のもとで問題なく
行える（Superhive / Blender Market の大半がこの形）。
