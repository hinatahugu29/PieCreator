import json
import os
from datetime import datetime, timezone, timedelta

log_path = r'g:\blender_addon\PieCreator\pie_creator_v11\agent-work-log.json'

new_entry = {
    "timestamp": datetime.now(timezone(timedelta(hours=9))).isoformat(),
    "user_request_summary": "PieCreator V11: コンテキスト認識による自動メニュー切替機能の実装。",
    "task_summary": "コンテキスト自動切替の実装",
    "ai_interpretation": "ユーザーはモード（オブジェクト、編集、スカルプト等）に応じてメニューが自動的に切り替わるインテリジェントな挙動を求めている。マスターキー呼び出し時に現在の Blender モードを判定し、紐付けられたメニューを優先表示するロジックを実装した。",
    "status": "completed",
    "duration_minutes": 20,
    "files_changed": [
        "pie_creator_v11/ops/core.py",
        "pie_creator_v11/ops/ui_ops.py"
    ],
    "executed_actions": [
        "PIECREATOR_OT_CallMaster において、現在のコンテキストモードに基づきメニューを検索・呼び出すロジックを追加",
        "PIECREATOR_OT_ManageModes において、選択可能なモード（Curve Edit, Paint系など）を大幅に拡充",
        "マスターメニューを介さずとも、状況に応じたツールを即座に展開できる基盤を構築"
    ],
    "notes": "この修正により、1つのキーで『編集モードならメッシュツール、スカルプトモードならブラシメニュー』といった使い分けが可能になった。",
    "artifacts": [
        "v11_task.md"
    ]
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
