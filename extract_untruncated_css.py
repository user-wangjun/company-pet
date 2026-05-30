import json
import os

# We want to extract the untruncated CSS replacement contents
# Let's inspect the files in order of their lines/relevance

files_to_parse = [
    # Initial multi-layered CSS block
    "css_edit_0dafbcfb-5ae3-4ea5-82ab-911f34d336e2_116.txt",
    # Popover styles
    "css_edit_12d163ea-518d-4922-a90e-d5f1401faf15_133.txt",
    # Modal styles
    "css_edit_12d163ea-518d-4922-a90e-d5f1401faf15_70.txt",
    # WeChat popover addition
    "css_edit_12d163ea-518d-4922-a90e-d5f1401faf15_112.txt",
    # Toast addition
    "css_edit_12d163ea-518d-4922-a90e-d5f1401faf15_185.txt"
]

print("Parsing files:")
for fn in files_to_parse:
    if os.path.exists(fn):
        with open(fn, "r", encoding="utf-8") as f:
            data = json.load(f)
        repl = data.get("ReplacementContent", "")
        out_fn = fn.replace(".txt", "_untruncated.css")
        with open(out_fn, "w", encoding="utf-8") as out:
            out.write(repl)
        print(f"  Extracted {len(repl)} chars from {fn} to {out_fn}")
    else:
        print(f"  File not found: {fn}")
