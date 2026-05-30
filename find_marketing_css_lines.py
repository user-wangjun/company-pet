with open("reconstructed_App_historic.css", "r", encoding="utf-8") as f:
    lines = f.readlines()

marketing_lines = []
for i, line in enumerate(lines):
    if "marketing" in line.lower():
        marketing_lines.append((i, line))

print(f"Found {len(marketing_lines)} lines with 'marketing'.")
if marketing_lines:
    print(f"First line: {marketing_lines[0][0]}, Content: {marketing_lines[0][1].strip()}")
    print(f"Last line: {marketing_lines[-1][0]}, Content: {marketing_lines[-1][1].strip()}")
