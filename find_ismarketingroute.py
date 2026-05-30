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
                    if "isMarketingRoute" in line:
                        matches.append((tf, i, line))

print(f"Found {len(matches)} lines containing isMarketingRoute.")
for tf, i, line in matches[:15]:
    print(f"\nFile: {tf}, Line: {i}")
    # let's search context
    try:
        data = json.loads(line)
        # Check tool calls
        if "tool_calls" in data:
            for tc in data["tool_calls"]:
                print(f"  Tool: {tc.get('name')}")
                args = tc.get("args", {})
                if isinstance(args, str):
                    args = json.loads(args)
                target = args.get("TargetFile", args.get("targetFile", ""))
                print(f"    TargetFile: {target}")
                if "ReplacementContent" in args:
                     print(f"    ReplContent length: {len(args['ReplacementContent'])}")
                if "ReplacementChunks" in args:
                     print(f"    Chunks count: {len(args['ReplacementChunks'])}")
        else:
            print("  No tool_calls in JSON step")
    except Exception as e:
        print(f"  Error parsing: {e}")
