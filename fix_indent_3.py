
import os

filename = "selenium_scraper.py"
start_line = 635
end_line = 641

with open(filename, "r") as f:
    lines = f.readlines()

new_lines = []
for i, line in enumerate(lines):
    line_num = i + 1
    if start_line <= line_num <= end_line:
        # Dedent by 4 spaces
        if line.startswith("    "):
            new_lines.append(line[4:])
        else:
            new_lines.append(line)
    else:
        new_lines.append(line)

with open(filename, "w") as f:
    f.writelines(new_lines)

print("Indentation fixed (round 3).")
