import json
import os

brain_dir = r"C:\Users\13640\.gemini\antigravity\brain"
app_edits = []

for root, dirs, files in os.walk(brain_dir):
    for file in files:
        if file == "transcript.jsonl":
            tf = os.path.join(root, file)
            with open(tf, "r", encoding="utf-8") as f:
                for i, line in enumerate(f):
                    try:
                        data = json.loads(line)
                        if "tool_calls" in data:
                            for tc in data["tool_calls"]:
                                if tc.get("name") in ("replace_file_content", "multi_replace_file_content"):
                                    args = tc.get("args", {})
                                    if isinstance(args, str):
                                        args = json.loads(args)
                                    target_file = args.get("TargetFile", args.get("targetFile", ""))
                                    if "App.tsx" in target_file and ("MarketingPage" in line or "isMarketingRoute" in line):
                                        app_edits.append((tf, i, tc.get("name"), args))
                    except Exception:
                        pass

print(f"Found {len(app_edits)} edits to App.tsx involving MarketingPage.")
for tf, i, name, args in app_edits:
    print(f"\nFile: {tf}, Line: {i}, Tool: {name}")
    if name == "replace_file_content":
        print(f"  StartLine: {args.get('StartLine')}, EndLine: {args.get('EndLine')}")
        print(f"  TargetContent:\n{args.get('TargetContent')}")
        print(f"  ReplacementContent:\n{args.get('ReplacementContent')}")
    elif name == "multi_replace_file_content":
        chunks = args.get("ReplacementChunks", [])
        for c_idx, c in enumerate(chunks):
            print(f"  Chunk {c_idx} [Start:{c.get('StartLine')}, End:{c.get('EndLine')}]:")
            print(f"    TargetContent:\n{c.get('TargetContent')}")
            print(f"    ReplacementContent:\n{c.get('ReplacementContent')}")
