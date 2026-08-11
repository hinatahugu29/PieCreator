import json
import os
from datetime import datetime, timezone, timedelta

log_path = r'g:\blender_addon\PieCreator\pie_creator_v10_2\agent-work-log.json'

new_entry = {
    "timestamp": datetime.now(timezone(timedelta(hours=9))).isoformat(),
    "user_request_summary": "競合アドオン「Smart Pie Menus」の機能調査依頼。",
    "task_summary": "Smart Pie Menus の機能とデザインの調査",
    "ai_interpretation": "ユーザーは自身の開発している PieCreator の機能拡張やデザイン向上のため、類似アドオンである Smart Pie Menus の特徴を把握したいと考えていると理解。コンテキスト認識やビジュアルエディタ、高度なレイアウト機能などの主要な特徴を抽出し、PieCreator への応用可能性を整理した。",
    "status": "completed",
    "duration_minutes": 5,
    "files_changed": [],
    "executed_actions": [
        "指定された URL (superhivemarket.com) をブラウザで開き、アドオンの機能を分析",
        "コンテキスト認識、ビジュアルエディタ、プロパティカタログ等の主要機能をリストアップ",
        "PieCreator へのフィードバック案を整理"
    ],
    "notes": "Smart Pie Menus の『モードに応じた動的切り替え』や『ビジュアルエディタ』は、現在の PieCreator をさらに進化させるための重要なベンチマークになると考えられる。",
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
