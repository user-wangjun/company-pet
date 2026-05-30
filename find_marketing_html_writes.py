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
                    if "marketing.html" in line:
                        try:
                            data = json.loads(line)
                            if "tool_calls" in data:
                                for tc in data["tool_calls"]:
                                    name = tc.get("name", "")
                                    if name in ("write_to_file", "replace_file_content"):
                                        args = tc.get("args", {})
                                        if isinstance(args, str):
                                            args = json.loads(args)
                                        target_file = args.get("TargetFile", args.get("targetFile", ""))
                                        if "marketing.html" in target_file:
                                            content = args.get("CodeContent", args.get("codeContent", args.get("ReplacementContent", "")))
                                            if len(content) > 5000:
                                                matches.append((tf, i, name, len(content), content))
                        except Exception:
                            pass

print(f"Found {len(matches)} large writes targeting marketing.html.")
for idx, (tf, i, name, size, content) in enumerate(matches):
    fn = f"extracted_marketing_html_full_{idx}.html"
    with open(fn, "w", encoding="utf-8") as out:
        out.write(content)
    print(f"  [{idx}] Saved {size} chars from {tf} Line {i} to {fn}")
