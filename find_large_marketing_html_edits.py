import os
import json

large_files = []
for i in range(36):
    fn = f"marketing_html_edit_{i}.txt"
    if os.path.exists(fn):
        size = os.path.getsize(fn)
        if size > 3000:
            large_files.append((fn, size))

print(f"Found {len(large_files)} files larger than 3000 bytes:")
for fn, size in large_files:
    print(f"  {fn}: {size} bytes")
    # let's read the JSON
    with open(fn, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"    Instruction: {data.get('Instruction')}")
    print(f"    StartLine: {data.get('StartLine')}, EndLine: {data.get('EndLine')}")
    repl = data.get('ReplacementContent', '')
    code = data.get('CodeContent', '')
    print(f"    ReplacementContent len: {len(repl)}")
    print(f"    CodeContent len: {len(code)}")
