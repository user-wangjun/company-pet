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
                    if "marketing.html" in line and ("DOCTYPE html" in line or "<html" in line):
                        matches.append((tf, i, line))

print(f"Found {len(matches)} matches.")
for tf, i, line in matches[:10]:
    print(f"\nFile: {tf}, Line {i}")
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
                print(f"    Target: {target}")
                content = args.get("CodeContent", args.get("codeContent", args.get("ReplacementContent", "")))
                print(f"    Content length: {len(content)}")
                if content:
                    fn = f"extracted_marketing_html_{i}.html"
                    with open(fn, "w", encoding="utf-8") as out:
                        out.write(content)
                    print(f"    SUCCESS! Saved to {fn}")
        else:
            print("  No tool calls in JSON step")
    except Exception as e:
        print(f"  Error: {e}")
