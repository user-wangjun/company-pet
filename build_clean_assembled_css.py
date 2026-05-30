import re

# Read the stitched historic App.css
with open("reconstructed_App_historic.css", "r", encoding="utf-8") as f:
    lines = f.readlines()

clean_css_lines = []
for i, line in enumerate(lines):
    # Heuristics to skip JSX/React lines
    # Pure CSS should not contain JSX constructs like imports, select statements, JSX comments, return statement, React lifecycle, double curly braces, angle brackets etc.
    line_stripped = line.strip()
    if not line_stripped:
        clean_css_lines.append(line)
        continue
        
    # React imports and hooks
    if line_stripped.startswith("import ") or line_stripped.startswith("const ") or line_stripped.startswith("function ") or line_stripped.startswith("let ") or line_stripped.startswith("return "):
        continue
    if "useEffect(" in line_stripped or "useRef(" in line_stripped or "useState(" in line_stripped or "window." in line_stripped:
        continue
        
    # JSX tags or react comments
    if line_stripped.startswith("<") or line_stripped.endswith(">") or line_stripped.endswith("/>") or "{/*" in line_stripped or "*/}" in line_stripped:
        continue
        
    # React styled properties with quotes
    if 'value={' in line_stripped or 'onChange={' in line_stripped or 'style={{' in line_stripped or 'onClick={' in line_stripped:
        continue
        
    # Random react lines
    if "display: \"flex\"" in line_stripped or "borderRadius:" in line_stripped or "RefreshCw" in line_stripped or "selectPet" in line_stripped or "playAnimation" in line_stripped or "disposed" in line_stripped:
        continue
        
    # If the line is part of react code blocks like curly braces closing after a react method
    if line_stripped == "}" and i > 0:
        # If previous line was react, let's skip it
        # (we'll just let a few close braces go, but we can clean them up)
        pass

    clean_css_lines.append(line)

# Let's save the cleaned CSS starting from the ".marketing-page" rule
marketing_css = []
started = False
for line in clean_css_lines:
    if ".marketing-page {" in line:
        started = True
    if started:
        marketing_css.append(line)

print(f"Extracted {len(marketing_css)} pure CSS lines.")

with open("marketing_pure.css", "w", encoding="utf-8") as out:
    out.writelines(marketing_css)
print("Saved clean CSS to marketing_pure.css")
