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
                    if "marketing-polished-socials" in line:
                        try:
                            data = json.loads(line)
                            # Let's search inside tool_calls or content
                            content = ""
                            if "tool_calls" in data:
                                for tc in data["tool_calls"]:
                                    args = tc.get("args", {})
                                    if isinstance(args, str):
                                        args = json.loads(args)
                                    content += args.get("CodeContent", args.get("codeContent", args.get("ReplacementContent", "")))
                            else:
                                content = data.get("content", "")
                            
                            if "marketing-polished-socials" in content and len(content) > 1000:
                                matches.append((tf, i, len(content), content))
                        except Exception:
                            pass

print(f"Found {len(matches)} matches.")
# Let's save the largest one
matches.sort(key=lambda x: x[2], reverse=True)
if matches:
    tf, i, size, content = matches[0]
    with open("restored_marketing_styles.css", "w", encoding="utf-8") as out:
        out.write(content)
    print(f"Saved largest match ({size} chars) from {tf} Line {i} to restored_marketing_styles.css")
