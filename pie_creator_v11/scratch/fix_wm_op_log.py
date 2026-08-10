import json
import os
from datetime import datetime, timezone, timedelta

log_path = r'g:\blender_addon\PieCreator\pie_creator_v11\agent-work-log.json'

new_entry = {
    "timestamp": datetime.now(timezone(timedelta(hours=9))).isoformat(),
    "user_request_summary": "Blender5.1でbpy.ops.mesh.primitive_cube_add()が依然として『未知』と表示される問題の解決。",
    "task_summary": "wm.operators（実行履歴）から取得するオペレーターのラベル取得バグ修正",
    "ai_interpretation": "ユーザーがキャプチャした際、依然として『未知』となるのは、Blenderの wm.operators 履歴に含まれるオブジェクトが Operator クラスそのものではなく OperatorProperties インスタンスであり、bl_idname プロパティを直接持たないためだったと特定。bl_rna.identifier および bl_rna.name へのフォールバックを追加することで根本解決を図る。",
    "status": "completed",
    "duration_minutes": 5,
    "files_changed": [
        "pie_creator_v11/ops/core.py"
    ],
    "executed_actions": [
        "get_op_label() 内で、wm.operators のインスタンスが bl_idname を持たない場合に備え、op.bl_rna.identifier と op.bl_rna.name を取得する処理を追加",
        "これにより、Cube追加などの標準オペレーターをキャプチャした際に正しく名前が表示されるよう修正"
    ],
    "notes": "wm.operatorsの仕様（OperatorPropertiesであること）に依存したバグだった。",
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
