import json
import os

brain_dir = r"C:\Users\13640\.gemini\antigravity\brain"
transcript_files = []

for root, dirs, files in os.walk(brain_dir):
    for file in files:
        if file == "transcript.jsonl":
            transcript_files.append(os.path.join(root, file))

print(f"Found {len(transcript_files)} transcript files.")

for tf in transcript_files:
    # Path format: C:\Users\13640\.gemini\antigravity\brain\<conv-id>\.system_generated\logs\transcript.jsonl
    # Let's extract the conv-id by walking up
    parts = tf.split(os.sep)
    try:
        idx = parts.index("brain")
        conv_id = parts[idx + 1]
    except:
        conv_id = "unknown"
        
    print(f"Scanning {conv_id} at {tf}...")
    with open(tf, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            try:
                data = json.loads(line)
                if "tool_calls" in data:
                    for tc in data["tool_calls"]:
                        name = tc.get("name", "")
                        if name in ("write_to_file", "replace_file_content", "multi_replace_file_content"):
                            args = tc.get("args", {})
                            if isinstance(args, str):
                                try:
                                    args = json.loads(args)
                                except:
                                    pass
                            
                            target_file = args.get("TargetFile", args.get("targetFile", ""))
                            if "MarketingPage.tsx" in target_file:
                                code_content = args.get("CodeContent", args.get("codeContent", ""))
                                replacement_content = args.get("ReplacementContent", args.get("replacementContent", ""))
                                chunks = args.get("ReplacementChunks", args.get("replacementChunks", []))
                                
                                print(f"  [MATCH] Line {i}, Tool: {name}")
                                print(f"    TargetFile: {target_file}")
                                print(f"    CodeContent len: {len(code_content)}")
                                print(f"    ReplacementContent len: {len(replacement_content)}")
                                print(f"    Chunks count: {len(chunks)}")
                                
                                content_to_save = None
                                if code_content:
                                    content_to_save = code_content
                                elif replacement_content:
                                    content_to_save = replacement_content
                                
                                if content_to_save:
                                    fn = f"extracted_{conv_id}_{i}_{name}.tsx"
                                    with open(fn, "w", encoding="utf-8") as out:
                                        out.write(content_to_save)
                                    print(f"    SUCCESS: Saved to {fn}!")
                                
                                if chunks:
                                    for idx, chunk in enumerate(chunks):
                                        c_repl = chunk.get("ReplacementContent", chunk.get("replacementContent", ""))
                                        print(f"      Chunk {idx} replacement len: {len(c_repl)}")
                                        if len(c_repl) > 1000:
                                            cfn = f"extracted_{conv_id}_{i}_chunk_{idx}.tsx"
                                            with open(cfn, "w", encoding="utf-8") as out:
                                                out.write(c_repl)
                                            print(f"      SUCCESS: Saved chunk to {cfn}!")
            except Exception as e:
                pass
