from pathlib import Path
from types import SimpleNamespace
from worker.tools import list_files, read_file, search_files

# Fake context pointing to our workspace
ctx = SimpleNamespace(workspace=Path('sandbox/workspace'))

# Test 1: list files
print("=== Test 1: List Files ===")
result = list_files(ctx, 'inbox')
for f in result['entries']:
    print(f"  {f}")

# Test 2: read an invoice
print("\n=== Test 2: Read Invoice ===")
result = read_file(ctx, 'inbox/2026-09-22_northwind_INV-2057.txt')
print(result['content'])

# Test 3: search
print("\n=== Test 3: Search for TOTAL DUE ===")
result = search_files(ctx, 'TOTAL DUE')
for m in result['matches']:
    print(f"  {m['file']} line {m['line']}: {m['text']}")