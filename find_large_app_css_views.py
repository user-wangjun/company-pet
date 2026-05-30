import json
import os

brain_dir = r"C:\Users\13640\.gemini\antigravity\brain"
matches = []

for root, dirs, files in os.walk(brain_dir):
    for file in files:
        if file == "transcript.jsonl":
            tf = os.path.join(root, file)
            parts = tf.split(os.sep)
            try:
                idx = parts.index("brain")
                conv_id = parts[idx + 1]
            except:
                conv_id = "unknown"
                
            with open(tf, "r", encoding="utf-8") as f:
                for i, line in enumerate(f):
                    if "app.css" in line.lower() and "view_file" in line.lower():
                        try:
                            data = json.loads(line)
                            content = data.get("content", "")
                            if len(content) > 1000:
                                matches.append((tf, i, conv_id, len(content), content))
                        except Exception:
                            pass

print(f"Found {len(matches)} App.css views.")
matches.sort(key=lambda x: x[3], reverse=True)
for idx, (tf, i, conv_id, size, content) in enumerate(matches[:5]):
    fn = f"app_css_view_{conv_id}_{i}.css"
    with open(fn, "w", encoding="utf-8") as out:
        out.write(content)
    print(f"  [{idx}] Saved {size} chars from {conv_id} Line {i} to {fn}")
