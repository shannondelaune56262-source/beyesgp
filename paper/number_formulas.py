"""Add continuous numbering to $$ formulas in main.md."""
import sys, io, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

path = 'C:/pscad/beyesgp/paper/main.md'
with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Remove existing \qquad (N) numbering first
for i, line in enumerate(lines):
    lines[i] = re.sub(r'\s*\\qquad\s*\(\d+\)\s*$', '', line)
    # Also remove standalone (2-1) style numbering
    lines[i] = re.sub(r'\s*\\qquad\s*式\(\d+-\d+\)\s*$', '', lines[i])

counter = 0
in_formula = False
formula_start = -1
formula_lines = []
# Sections to skip: algorithm block, reference list
skip_sections = False

for i, line in enumerate(lines):
    stripped = line.strip()

    # Detect sections to skip
    if stripped.startswith('## 算法') or stripped.startswith('## 参考文献'):
        skip_sections = True
    elif stripped.startswith('## ') and skip_sections:
        skip_sections = False

    if skip_sections:
        continue

    if stripped == '$$':
        if not in_formula:
            # Start of formula block
            in_formula = True
            formula_start = i
            formula_lines = []
        else:
            # End of formula block - add numbering
            in_formula = False
            counter += 1

            # Check if formula is multi-line (more than just $$...$$)
            content = '\n'.join(formula_lines).strip()

            # For single-line formulas, append number to the last content line
            # For multi-line, append to the last non-empty content line
            last_content_idx = formula_start + 1
            for j in range(formula_start + 1, i):
                if lines[j].strip():
                    last_content_idx = j

            # Add number to last content line
            lines[last_content_idx] = lines[last_content_idx].rstrip() + f' \\qquad ({counter})\n'
    else:
        if in_formula:
            formula_lines.append(stripped)

print(f'Numbered {counter} formulas')

with open(path, 'w', encoding='utf-8') as f:
    f.writelines(lines)
