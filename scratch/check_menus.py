import bpy
all_menu_ids = []
for attr in dir(bpy.types):
    try:
        cls = getattr(bpy.types, attr)
        if isinstance(cls, type) and issubclass(cls, bpy.types.Menu):
            all_menu_ids.append(attr)
    except:
        continue
print(f"Total Menus Found: {len(all_menu_ids)}")
if len(all_menu_ids) > 0:
    print(f"Sample: {all_menu_ids[:5]}")
