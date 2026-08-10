import json
import os
from datetime import datetime, timezone, timedelta

log_path = r'g:\blender_addon\PieCreator\pie_creator_v11\agent-work-log.json'

new_entry = {
    "timestamp": datetime.now(timezone(timedelta(hours=9))).isoformat(),
    "user_request_summary": "PieCreator V11 の新規プロジェクト作成と更新プランの策定。",
    "task_summary": "V11 開発環境の構築とロードマップ作成",
    "ai_interpretation": "ユーザーは Smart Pie Menus の機能をベンチマークとした次世代バージョン V11 の開発を決定した。既存コードを v11 フォルダに継承し、コンテキスト認識やカタログ機能を中心とした野心的な更新プランを策定した。",
    "status": "completed",
    "duration_minutes": 10,
    "files_changed": [
        "pie_creator_v11/__init__.py"
    ],
    "executed_actions": [
        "pie_creator_v11 フォルダの作成と全ファイルのコピー",
        "__init__.py の bl_info を V11.0.0 に更新",
        "V11 向けの実装プラン (v11_implementation_plan.md) の作成"
    ],
    "notes": "V11 は PieCreator にとって『スマート化』の重要なステップとなる。既存の Deck システムとの親和性を保ちつつ、自動化機能を組み込んでいく。",
    "artifacts": [
        "v11_implementation_plan.md"
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
