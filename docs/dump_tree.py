import os
import ast
from pathlib import Path

def print_tree(startpath, max_depth=4, ignore_dirs={'.git', 'node_modules', 'venv', 'venv5', '__pycache__', 'dist', 'build', '.pytest_cache', '.ruff_cache'}):
    for root, dirs, files in os.walk(startpath):
        dirs[:] = [d for d in dirs if d not in ignore_dirs]
        level = root.replace(startpath, '').count(os.sep)
        if level > max_depth:
            continue
        indent = ' ' * 4 * level
        print(f'{indent}{os.path.basename(root)}/')
        subindent = ' ' * 4 * (level + 1)
        for f in files:
            if not f.endswith('.pyc'):
                print(f'{subindent}{f}')

print("=== PROJECT TREE ===")
print_tree('d:/ClinExtract', max_depth=5)
