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
                    if "marketing.html" in line and "DOCTYPE html" in line:
                        try:
                            data = json.loads(line)
                            content = data.get("content", "")
                            # Check if the content itself has the HTML code
                            if "<html" in content or "DOCTYPE" in content:
                                matches.append((tf, i, content))
                        except Exception:
                            pass

print(f"Found {len(matches)} matches in step content.")
for idx, (tf, i, content) in enumerate(matches):
    fn = f"extracted_marketing_html_content_{idx}.html"
    with open(fn, "w", encoding="utf-8") as out:
        out.write(content)
    print(f"  [{idx}] Saved match from {tf} Line {i} to {fn} (Length: {len(content)})")
