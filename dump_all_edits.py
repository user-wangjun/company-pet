import json
import os

brain_dir = r"C:\Users\13640\.gemini\antigravity\brain"
edits = []

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
                    try:
                        data = json.loads(line)
                        if "tool_calls" in data:
                            for tc in data["tool_calls"]:
                                if tc.get("name") in ("replace_file_content", "write_to_file", "multi_replace_file_content"):
                                    args = tc.get("args", {})
                                    if isinstance(args, str):
                                        args = json.loads(args)
                                    target_file = args.get("TargetFile", args.get("targetFile", ""))
                                    if "MarketingPage.tsx" in target_file:
                                        edits.append({
                                            "conv_id": conv_id,
                                            "line": i,
                                            "tool": tc.get("name"),
                                            "args": args,
                                            "created_at": data.get("created_at", "")
                                        })
                    except Exception:
                        pass

# Sort edits by created_at
edits.sort(key=lambda x: x["created_at"])

with open("all_edits_dump.txt", "w", encoding="utf-8") as out:
    out.write(f"Found {len(edits)} edits.\n")
    for idx, edit in enumerate(edits):
        out.write(f"\n========================================================\n")
        out.write(f"[{idx}] Conv: {edit['conv_id']}, Line: {edit['line']}, Tool: {edit['tool']}, Created At: {edit['created_at']}\n")
        out.write(f"========================================================\n")
        args = edit["args"]
        if edit["tool"] == "replace_file_content":
            out.write(f"StartLine: {args.get('StartLine')}, EndLine: {args.get('EndLine')}\n")
            out.write(f"TargetContent:\n{args.get('TargetContent')}\n")
            out.write(f"ReplacementContent:\n{args.get('ReplacementContent')}\n")
        elif edit["tool"] == "write_to_file":
            out.write(f"IsArtifact: {args.get('IsArtifact')}, Overwrite: {args.get('Overwrite')}\n")
            out.write(f"CodeContent:\n{args.get('CodeContent')}\n")
        elif edit["tool"] == "multi_replace_file_content":
            chunks = args.get("ReplacementChunks", [])
            out.write(f"Chunks count: {len(chunks)}\n")
            for c_idx, c in enumerate(chunks):
                out.write(f"  Chunk {c_idx} [Start:{c.get('StartLine')}, End:{c.get('EndLine')}]:\n")
                out.write(f"    TargetContent:\n{c.get('TargetContent')}\n")
                out.write(f"    ReplacementContent:\n{c.get('ReplacementContent')}\n")

print(f"Dumped {len(edits)} edits to all_edits_dump.txt")
