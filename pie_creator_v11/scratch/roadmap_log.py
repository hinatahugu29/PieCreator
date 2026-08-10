import json
import os
from datetime import datetime, timezone, timedelta

log_path = r'g:\blender_addon\PieCreator\pie_creator_v10_2\agent-work-log.json'

new_entry = {
    "timestamp": datetime.now(timezone(timedelta(hours=9))).isoformat(),
    "user_request_summary": "PieCreator の今後の開発方針（Smart Pie Menus の機能取り込み）についての相談。",
    "task_summary": "開発ロードマップの検討と提案",
    "ai_interpretation": "ユーザーは Smart Pie Menus の高度な機能に触発され、自身の PieCreator も同等のレベルを目指すべきか検討していると理解。特に『コンテキスト認識』や『カタログ機能』は PieCreator の利便性を劇的に向上させるため、段階的な導入を提案する。",
    "status": "completed",
    "duration_minutes": 5,
    "files_changed": [],
    "executed_actions": [
        "Smart Pie Menus の各機能の実装難易度とユーザーメリットを分析",
        "PieCreator への段階的な機能取り込みプラン（ロードマップ）を提案"
    ],
    "notes": "全てを一度に実装するのではなく、まずは『コンテキストによる自動切替』のような、既存システム（Deck等）の延長線上で実現可能な高価値機能から着手するのが現実的だと判断。",
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
