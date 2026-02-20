
import os

filename = "selenium_scraper.py"
start_line = 502
end_line = 541

with open(filename, "r") as f:
    lines = f.readlines()

new_lines = []
for i, line in enumerate(lines):
    line_num = i + 1
    if start_line <= line_num <= end_line:
        # Check if it needs indentation (don't double indent if I run twice)
        # But wait, looking at file, it has 20 spaces. I need 24.
        # "                    title =" -> 20 spaces.
        if line.strip(): # Only indent non-empty lines, or all lines?
            # It's safer to add 4 spaces to everything in range.
            new_lines.append("    " + line)
        else:
            new_lines.append(line)
    else:
        new_lines.append(line)

with open(filename, "w") as f:
    f.writelines(new_lines)

print("Indentation fixed.")
