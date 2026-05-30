with open("marketing_pure.css", "r", encoding="utf-8") as f:
    lines = f.readlines()

# Part 1: Initial core browser wrapper styles (Lines 1 to 47, which is index 0 to 46)
part1 = lines[0:47]

# Part 2: Premium space layout and wobbly animations (Lines 396 to the end, which is index 395 to the end)
# Let's double check if lines[395] is indeed ".marketing-hero {"
print(f"Line 396 (index 395): {lines[395].strip()}")

part2 = lines[395:]

final_lines = part1 + ["\n"] + part2

with open("final_marketing.css", "w", encoding="utf-8") as out:
    out.writelines(final_lines)

print(f"Assembled final_marketing.css with {len(final_lines)} lines!")
