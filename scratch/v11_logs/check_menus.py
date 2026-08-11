import bpy
import json

def check_menus():
    results = {
        "total_types": len(dir(bpy.types)),
        "mt_count": 0,
        "sample_menus": [],
        "errors": []
    }
    
    for attr in dir(bpy.types):
        if "_MT_" in attr:
            results["mt_count"] += 1
            try:
                cls = getattr(bpy.types, attr)
                label = getattr(cls, "bl_label", "NO_LABEL")
                if len(results["sample_menus"]) < 10:
                    results["sample_menus"].append({"attr": attr, "label": label})
            except Exception as e:
                results["errors"].append(f"Error getting {attr}: {str(e)}")
                
    return results

print(json.dumps(check_menus(), indent=2))
