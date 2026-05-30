import json
import os

log_path = r"C:\Users\13640\.gemini\antigravity\brain\0dafbcfb-5ae3-4ea5-82ab-911f34d336e2\.system_generated\logs\transcript.jsonl"

css_edits = []
with open(log_path, "r", encoding="utf-8") as f:
    for i, line in enumerate(f):
        if "app.css" in line.lower() and ("replace_file_content" in line or "write_to_file" in line):
            try:
                data = json.loads(line)
                if "tool_calls" in data:
                    for tc in data["tool_calls"]:
                        args = tc.get("args", {})
                        if isinstance(args, str):
                            args = json.loads(args)
                        target_file = args.get("TargetFile", args.get("targetFile", ""))
                        if "app.css" in target_file.lower():
                            css_edits.append((i, tc.get("name"), args))
            except Exception:
                pass

print(f"Found {len(css_edits)} edits targeting App.css in 0dafbcfb-5ae3-4ea5-82ab-911f34d336e2.")
for idx, (line_num, name, args) in enumerate(css_edits):
    print(f"\nEdit {idx} at line {line_num}:")
    print(f"  Instruction: {args.get('Instruction')}")
    print(f"  StartLine: {args.get('StartLine')}, EndLine: {args.get('EndLine')}")
    repl = args.get("ReplacementContent", "")
    print(f"  Repl len: {len(repl)}")
    
    # Save each to a formatted file
    out_fn = f"initial_css_{idx}.css"
    formatted = repl.replace("\\n", "\n").replace("\\t", "\t").replace('\\"', '"')
    with open(out_fn, "w", encoding="utf-8") as out:
        out.write(formatted)
    print(f"  Saved to {out_fn}")
