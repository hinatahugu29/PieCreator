# PieCreator V10.2 機能紹介

このドキュメントでは、進化した PieCreator V10.2 の主要な機能を紹介します。

## 1. アドオン側：メインツールバー（Preferences）

アドオン設定画面（Preferences）の上部には、データの管理や外部エディタとの連携を行う強力なツールバーが配置されています。

![Addon Toolbar](docs/images/media__1777666772605.png)

### 🛠️ 基本機能
- **🔄 Reload**: 最新の設定ファイル（`menus.json`）を強制的に再読み込みし、Blender の実行環境へ同期させます。
- **📤 Export**: 作成した全てのデッキ、メニュー、項目を JSON ファイルとして書き出します。
- **📥 Import**: JSON ファイルからメニュー設定を一括インポートします。

### 🌐 外部エディタ連携
- **💻 Designer**: 外部の Web ブラウザベース・ビジュアルエディタ「**PieDesigner**」を起動します。
- **↗️ Copy (to Designer)**: Blender 内の現在の全設定データをクリップボードにコピーします。
- **↘️ Paste (from Designer)**: PieDesigner で編集・コピーした JSON データを Blender 側へ流し込みます。

### 🔍 その他
- **📖 Handbook**: 現在の全メニュー構造を網羅した「機能ハンドブック（HTML）」を生成・出力します。
- **🔴 Macro Record**: マクロレコーダーの開始/停止を行います。

## 2. 高度なツール群：解析と自動化

![Advanced Tools](docs/images/media__1777666772605.png)

### 🔍 Scraper (Analyze Menu)
Blender 自体が持つ膨大な既存メニューを「解析」し、自分専用のメニューとして取り込む機能です。
- **検索と解析**: Blender 標準のメニューや他アドオンのメニューを検索し、その構成要素を瞬時にスキャンします。
- **一括インポート**: スキャンした項目から必要なものだけを選択し、自分のメニューへ一括追加できます。

### 🔴 Macro Recorder
あなたの Blender 上での操作を「記憶」させ、一つのボタンとして保存する機能です。
- **リアルタイム記録**: 録画中のオペレーター操作をすべてスクリプトとして記録します。
- **即時ボタン化**: 記録した流れを一つのコマンドボタンとしてメニューに登録できます。

### 📖 Handbook Generation
- **HTML出力**: 現在登録されている全メニューの構造、ショートカットキー、アイコンなどを網羅した視覚的なハンドブックを HTML 形式で出力します。

## 3. サイドバー：ナビゲーターとライブラリ

![Sidebar Navigator](docs/images/media__1777679354057.png)

### 📂 Navigator (Menus タブ)
作成したメニューを、実際の呼び出し関係に基づいた**「ツリー形式」**で表示します。
- **階層の可視化**: 子メニューへの繋がりが視覚的にわかりやすく、複雑な構成も迷わず管理できます。
- **ステータス表示**: アイコンの色や形でメニュータイプ（PIE/POPUP等）を瞬時に判別可能です。

### 📚 Library タブ
よく使うアクションやテンプレートを保管し、ドラッグ＆ドロップで再利用できます。

## 4. メニューエディタ：詳細設定と項目編集

![Menu Editor](docs/images/media__1777679448889.png)

### 📦 Deck & Master Key
- **Deck (デッキ)**: メニューのセットを切り替えます。用途に合わせて環境を丸ごと変更可能です。
- **Master Key**: 全カスタムメニューの親となるショートカットキーを一括管理します。

### 🛠️ Menu Entry (メニューの基本設定)
- **タイプ選択**: PIE, POPUP, STACK, STICKY など、挙動をワンクリックで変更。
- **コンテキスト設定**: モードやエリアによる表示条件を細かく指定できます。

### 📋 Item Editor (項目リスト)
- **直感的な操作**: 矢印での並べ替え、クローン作成、削除などがスムーズに行えます。

## 5. PieDesigner (Web エディタ)：サイドバー

![PieDesigner Sidebar](docs/images/media__1777679508551.png)

### 📊 ビジュアル管理ツール
- **Toggle Graph View**: メニュー構造をノードグラフとして可視化。
- **Split View**: 複数メニューを同時に比較編集。
- **Load Catalog**: Blender API のカタログを読み込み。

### ⚡ Blender Sync (リアルタイム同期)
- **Paste Items into Menu (New!)**: Blender でコピーした項目を、現在のメニューへ直接展開してアペンドします。

## 6. PieDesigner (Web エディタ)：メインキャンバス

![PieDesigner Main Canvas](docs/images/media__1777679618590.png)

### 🎨 Visual Item Editor
- **視覚的配置**: 8方向のスロットを実際の見た目通りにレイアウト。

### 🕸️ Graph View
- **遷移の管理**: メニュー同士の繋がりをノードとして俯瞰し、クリックで編集対象を切り替え。

## 7. PieDesigner (Web エディタ)：プロパティエディタ

![PieDesigner Property Editor](docs/images/media__1777679655982.png)

### ⚙️ Current Menu Settings
- メニュー名やタイプの変更を一括で行えます。

### 🔘 Item Properties
- **Icon Search**: Blender アイコンをキーワード検索。
- **Command Editor**: Python コマンドの直接編集と微調整。

## 8. 裏方のこだわり：パーソナライズされた API カタログ

### 🧠 Deep Scan & API Synchronization
PieDesigner は、あなたの Blender 環境を完全に理解しています。
- **全オペレーターの網羅**: 標準機能だけでなく、**インストール済みの他アドオン**の機能もすべてスキャンして認識します。
- **インテリジェンスな補完**: 独自の API カタログにより、コマンド入力時の強力なオートコンプリートを提供します。

---
**PieCreator V10.2** は、Blender のパワーを最大限に引き出し、理想のワークフローを構築するための最強のパートナーです。
