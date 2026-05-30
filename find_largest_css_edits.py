import os
import json

large_css = []
for file in os.listdir("."):
    if file.startswith("css_edit_") and file.endswith(".txt"):
        size = os.path.getsize(file)
        large_css.append((file, size))

large_css.sort(key=lambda x: x[1], reverse=True)
print(f"Found {len(large_css)} CSS edit files:")
for file, size in large_css[:10]:
    print(f"  {file}: {size} bytes")
    with open(file, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
            print(f"    Instruction: {data.get('Instruction')}")
            print(f"    StartLine: {data.get('StartLine')}, EndLine: {data.get('EndLine')}")
            repl = data.get('ReplacementContent', '')
            print(f"    ReplacementContent len: {len(repl)}")
        except Exception as e:
            print(f"    Error: {e}")
