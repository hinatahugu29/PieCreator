import bpy
import json
import os

def deep_scan_blender():
    print("Starting Deep Scan of Blender API...")
    
    catalog = {
        "modules": {},
        "icons": []
    }
    
    # 1. Scan Icons
    # BlenderのRNAから全アイコン名を取得
    icon_enum = bpy.types.UILayout.bl_rna.functions["prop"].parameters["icon"].enum_items
    catalog["icons"] = sorted([i.identifier for i in icon_enum if i.identifier != 'NONE'])
    print(f"Scanned {len(catalog['icons'])} icons.")

    # 2. Scan Operators
    op_count = 0
    # bpy.ops の各モジュール（mesh, object, etc.）をループ
    for attr in dir(bpy.ops):
        module = getattr(bpy.ops, attr)
        if str(type(module)) != "<class 'module'>":
            continue
            
        module_ops = []
        # モジュール内の各オペレーターをループ
        for op_name in dir(module):
            if op_name.startswith("_"): continue
            
            try:
                op = getattr(module, op_name)
                # オペレーターのRNA情報を取得
                rna = op.get_rna_type()
                
                module_ops.append({
                    "id": f"{attr}.{op_name}",
                    "name": rna.name or op_name,
                    "desc": rna.description or ""
                })
                op_count += 1
            except:
                # 一部の動的なオペレーターなどで失敗する場合があるためスキップ
                continue
        
        if module_ops:
            catalog["modules"][attr] = module_ops

    print(f"Scanned {op_count} operators across {len(catalog['modules'])} modules.")
    
    # 3. Save to Project Directory
    # 保存先をプロジェクトルートに設定
    output_path = r"g:\blender_addon\PieCreator\blender_catalog.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(catalog, f, indent=2, ensure_ascii=False)
    
    print(f"Catalog saved to: {output_path}")

if __name__ == "__main__":
    deep_scan_blender()
