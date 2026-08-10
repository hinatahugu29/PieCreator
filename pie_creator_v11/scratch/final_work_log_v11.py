import json
import os
from datetime import datetime, timezone, timedelta

log_path = r'g:\blender_addon\PieCreator\pie_creator_v11\agent-work-log.json'

new_entry = {
  "timestamp": datetime.now(timezone(timedelta(hours=9))).isoformat(),
  "user_request_summary": "カタログ機能（検索して追加）の実装と、ショートカット解除機能の安定化、およびUIの選択状態の改善。",
  "task_summary": "PieCreator V11 の中核機能（カタログ検索・コンテキスト切替）の完成",
  "ai_interpretation": "ユーザーは、Blenderの標準機能をより素早くメニューに組み込めるワークフローを求めていた。カタログ機能により、キャプチャの手間を省き、検索から即座に追加できる環境を構築。また、複雑なキー管理を整理するため、明示的な解除ボタンとコンテキスト切替ロジックを安定化させた。",
  "status": "completed",
  "duration_minutes": 45,
  "files_changed": [
    "pie_creator_v11/__init__.py",
    "pie_creator_v11/ui/components.py",
    "pie_creator_v11/ops/ui_ops.py",
    "pie_creator_v11/ui/preferences.py"
  ],
  "executed_actions": [
    "Blenderの全オペレーターを検索・追加できる『カタログ』タブをサイドバーに実装",
    "タイマーとキャッシュを利用したリアルタイム検索エンジンの構築（入力中に即座に候補を表示）",
    "メニューを展開（▶）した際に、自動的にそのメニューを追加対象（アクティブ）として認識するロジックの実装",
    "ショートカット解除ボタン（×）が、Blenderの設定とアドオンの保存データ（menus.json）の両方を確実に更新するように修正",
    "UI描画ループ内でのプロパティ上書きを廃止し、メニュー選択時のハイライトが消えるバグを修正"
  ],
  "uploaded_images": [
    {
      "description": "カタログタブのUI。検索窓と検索結果が表示されている状態。",
      "context": "検索エンジンの動作確認"
    },
    {
      "description": "メニューリストのUI。選択状態が維持され、ショートカット解除ボタンが配置されている状態。",
      "context": "UIのハイライトとキー管理の確認"
    }
  ],
  "notes": "検索エンジンは初回実行時に全オペレーターをキャッシュするため、最初の1回だけ数秒の待ちが発生するが、以降は爆速で動作する設計とした。",
  "artifacts": []
}

if os.path.exists(log_path):
    with open(log_path, 'r', encoding='utf-8') as f:
        try:
            data = json.load(f)
        except:
            data = []
else:
    data = []

data.append(new_entry)

with open(log_path, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
