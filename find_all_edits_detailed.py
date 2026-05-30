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

print(f"Found {len(edits)} edits targeting MarketingPage.tsx.")

for idx, edit in enumerate(edits):
    print(f"\n[{idx}] Conv: {edit['conv_id']}, Line: {edit['line']}, Tool: {edit['tool']}")
    args = edit["args"]
    if edit["tool"] == "replace_file_content":
        print(f"  StartLine: {args.get('StartLine')}, EndLine: {args.get('EndLine')}")
        print(f"  TargetContent:\n{args.get('TargetContent')}")
        print(f"  ReplacementContent:\n{args.get('ReplacementContent')}")
    elif edit["tool"] == "write_to_file":
        print(f"  IsArtifact: {args.get('IsArtifact')}, Overwrite: {args.get('Overwrite')}")
        print(f"  CodeContent length: {len(args.get('CodeContent', ''))}")
    elif edit["tool"] == "multi_replace_file_content":
        chunks = args.get("ReplacementChunks", [])
        print(f"  Chunks count: {len(chunks)}")
        for c_idx, c in enumerate(chunks):
            print(f"    Chunk {c_idx} [Start:{c.get('StartLine')}, End:{c.get('EndLine')}]:")
            print(f"      TargetContent:\n{c.get('TargetContent')}")
            print(f"      ReplacementContent:\n{c.get('ReplacementContent')}")
