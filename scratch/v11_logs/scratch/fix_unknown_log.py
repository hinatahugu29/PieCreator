import json
import os
from datetime import datetime, timezone, timedelta

log_path = r'g:\blender_addon\PieCreator\pie_creator_v11\agent-work-log.json'

new_entry = {
    "timestamp": datetime.now(timezone(timedelta(hours=9))).isoformat(),
    "user_request_summary": "キャプチャ時のラベルが『未知の物』になる問題の深掘りと修正。",
    "task_summary": "ラベル取得ロジックの多重化とフォールバック強化",
    "ai_interpretation": "ユーザーは、ドキュメント化されていない（undocumented）オペレーターや、特定のサードパーティ製アドオンのボタンをキャプチャした際、名前が空になってしまうことを疑問に感じている。Blender 内部で名前が定義されていない場合でも、ID名（mesh.primitive_cube_add 等）を最終的なラベルとして採用することで、空欄や『未知の物』を避けるように改善した。",
    "status": "completed",
    "duration_minutes": 10,
    "files_changed": [
        "pie_creator_v11/ops/core.py"
    ],
    "executed_actions": [
        "get_op_label 内で、RNA、bl_label、name、bl_idname の順で名前取得を試みる多重フォールバックを実装",
        "名前が全く定義されていないオペレーターでも、ID名をラベルとして表示するように修正"
    ],
    "notes": "Blenderの『undocumented operator』は内部的に名前を持たないことがあるが、ID名を表示することでユーザーが何をキャプチャしたか判別可能にした。",
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
