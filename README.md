# PieCreator

Blender 用のパイメニュー作成アドオン。任意の Blender オペレーターやマクロを、
コンテキストに応じて切り替わる階層型パイメニューとして組み立てられる。

- **Blender**: 5.0 以降
- **バージョン**: 11.0.0
- **作者**: hinata_hugu

## インストール

1. `pie_creator/` フォルダを zip に固める
2. Blender の `Edit > Preferences > Add-ons > Install...` でその zip を指定
3. 有効化すると `Preferences > Add-ons > PieCreator V11` に設定 UI が出る

## リポジトリ構成

| パス | 中身 |
|---|---|
| `pie_creator/` | **アドオン本体。配布物はこのフォルダのみ** |
| `pie_creator/ops/` | オペレーター（コア・マクロ・IO・デザイナー連携・プール） |
| `pie_creator/ui/` | プリファレンス UI とメニュー定義 |
| `pie_creator/designer/` | 外部メニューエディタ（HTML/JS の PieDesigner） |
| `pie_creator/tools/` | ハンドブック生成などの補助ツール |
| `docs/` | 設計メモ・マニュアル・ロードマップ |
| `docs/html/` | 生成済み HTML（マニュアル、ハンドブック、ロゴアニメ、プロトタイプ） |
| `data/` | 生成データ（Blender API カタログ、メニュー階層 JSON） |
| `tests/` | Blender 上で走らせる検証スクリプト |
| `scratch/` | 使い捨ての調査スクリプトと作業ログ。参照専用 |

`data/blender_catalog.json` はアドオンからは読まれない。PieDesigner の
「Load Catalog」で読み込む用の書き出し済みデータで、アドオン側は実行時に
`pie_creator/designer/blender_catalog.js` を生成する。

## 開発

過去は `pie_creator_v1` 〜 `v11` とフォルダを増やして世代管理していたが、
現在は `pie_creator/` 一本を Git の履歴で追う方式に統一している。
旧世代のコードは Git 履歴とローカルの zip に残っている。

作業ルールは [CLAUDE.md](CLAUDE.md) を参照。
