import json
import os
from datetime import datetime, timezone, timedelta

log_path = r'g:\blender_addon\PieCreator\pie_creator_v11\agent-work-log.json'

new_entry = {
    "timestamp": datetime.now(timezone(timedelta(hours=9))).isoformat(),
    "user_request_summary": "マスターキーおよび各メニューのショートカットキーを明示的に解除する機能の強化依頼。",
    "task_summary": "マスターキー対応を含むショートカット解除機能の拡張実装",
    "ai_interpretation": "ユーザーは個別のメニューだけでなく、全体の『マスターキー』についても簡単に解除したいと考えている。解除ボタンが削除ボタンと混同されないよう、キー入力フィールドの直近に配置し、内部ロジックでマスターキーと個別メニューキーの両方に対応させた。",
    "status": "completed",
    "duration_minutes": 5,
    "files_changed": [
        "pie_creator_v11/ops/ui_ops.py",
        "pie_creator_v11/ui/preferences.py",
        "pie_creator_v11/ui/components.py"
    ],
    "executed_actions": [
        "PIECREATOR_OT_ClearShortcut に is_master プロパティを追加し、グローバルなマスターキーの解除に対応させた",
        "Preferences UI の Master Key 項目に解除用の『×』ボタンを追加",
        "UIの整合性を保つため、キー入力フィールドと解除ボタンを row(align=True) でグループ化した"
    ],
    "notes": "ユーザーからの指摘通り、末尾の『×』はメニュー削除ボタンであったため、キー設定のすぐ横に専用の解除ボタンを配置するように修正した。",
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
