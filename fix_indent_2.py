
import os

filename = "selenium_scraper.py"
start_line = 549
# End line should be just before the 'except' block I added.
# In view_file output, 'except' is at 641.
# So I need to indent up to 640 inclusive.
end_line = 640

with open(filename, "r") as f:
    lines = f.readlines()

new_lines = []
for i, line in enumerate(lines):
    line_num = i + 1
    if start_line <= line_num <= end_line:
        if line.strip(): 
            new_lines.append("    " + line)
        else:
            new_lines.append(line)
    else:
        new_lines.append(line)

with open(filename, "w") as f:
    f.writelines(new_lines)

print("Indentation fixed (round 2).")
