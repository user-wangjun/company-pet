import json
import os

brain_dir = r"C:\Users\13640\.gemini\antigravity\brain"
matches = []

for root, dirs, files in os.walk(brain_dir):
    for file in files:
        if file == "transcript.jsonl":
            tf = os.path.join(root, file)
            with open(tf, "r", encoding="utf-8") as f:
                for i, line in enumerate(f):
                    if "marketing.html" in line.lower():
                        try:
                            data = json.loads(line)
                            if "tool_calls" in data:
                                for tc in data["tool_calls"]:
                                    args = tc.get("args", {})
                                    if isinstance(args, str):
                                        args = json.loads(args)
                                    target_file = args.get("TargetFile", args.get("targetFile", ""))
                                    if "marketing.html" in target_file.lower():
                                        matches.append((tf, i, tc.get("name"), args))
                        except Exception:
                            pass

print(f"Found {len(matches)} tool calls targeting marketing.html.")
for idx, (tf, i, name, args) in enumerate(matches):
    print(f"\n[{idx}] File: {tf}, Line: {i}, Tool: {name}")
    # print keys of args
    print(f"  Keys: {list(args.keys())}")
    target = args.get("TargetFile", args.get("targetFile", ""))
    print(f"  Target: {target}")
    # Let's save each of them to a separate file
    fn = f"marketing_html_edit_{idx}.txt"
    with open(fn, "w", encoding="utf-8") as out:
        out.write(json.dumps(args, indent=2, ensure_ascii=False))
    print(f"  Saved to {fn}")
