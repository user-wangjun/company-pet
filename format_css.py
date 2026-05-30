import os

for file in os.listdir("."):
    if file.endswith("_untruncated.css"):
        with open(file, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Replace escaped newlines if any, or just write it with proper formatting
        formatted = content.replace("\\n", "\n").replace("\\t", "\t").replace('\\"', '"')
        
        out_name = file.replace("_untruncated.css", "_formatted.css")
        with open(out_name, "w", encoding="utf-8") as out:
            out.write(formatted)
        print(f"Formatted {file} -> {out_name}")
