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
                # Check for view_file tool call in MODEL or output in SYSTEM / tool response
                # Let's search if the string "function MarketingPage" is in this line.
                if "function MarketingPage" in line:
                    print(f"\n--- LITERAL MATCH in Conv: {conv_id}, Line {i} ---")
                    # If this is a step, let's see its type and content length
                    print(f"  Type: {data.get('type')}, Status: {data.get('status')}")
                    content = data.get("content", "")
                    print(f"  Content len: {len(content)}")
                    
                    # Check tool_calls or responses
                    tool_calls = data.get("tool_calls", [])
                    for tc in tool_calls:
                        if tc.get("name") == "view_file":
                            print(f"  Tool call view_file args: {tc.get('args')}")
                    
                    # If it's a SYSTEM response (the output of the tool)
                    # Often the tool output is in 'content'
                    if len(content) > 1000:
                        fn = f"viewed_{conv_id}_{i}.tsx"
                        with open(fn, "w", encoding="utf-8") as out:
                            out.write(content)
                        print(f"  Saved literal content to {fn}!")
            except Exception as e:
                pass
