# Let's read all lines from reconstructed_App_historic.css and filter the ones we want
with open("reconstructed_App_historic.css", "r", encoding="utf-8") as f:
    lines = f.readlines()

# Let's find the lines in the file that actually correspond to line 1100 to 2395 of App.css
# Wait, in reconstructed_App_historic.css, we saved the lines sequentially.
# Let's inspect where the marketing-page styles start.
# We will read all the lines from reconstructed_App_historic.css starting from the first line that has ".marketing-page"
# up to the end of the file.

marketing_content = []
started = False
for line in lines:
    if ".marketing-page {" in line:
        started = True
    if started:
        marketing_content.append(line)

print(f"Extracted {len(marketing_content)} lines of marketing styles.")
with open("marketing_styles.css", "w", encoding="utf-8") as out:
    out.writelines(marketing_content)
print("Saved to marketing_styles.css")
