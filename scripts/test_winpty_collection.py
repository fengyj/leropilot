#!/usr/bin/env python3
"""
Test script to verify winpty binary collection works correctly.
Run this in the CI environment to debug the issue.
"""

import sys

print("=" * 60)
print("Testing winpty binary collection")
print("=" * 60)

# Test 1: Check if winpty is installed
print("\n1. Checking winpty installation...")
try:
    import winpty

    print(f"   ✓ winpty installed at: {winpty.__file__}")
except ImportError as e:
    print(f"   ✗ winpty not installed: {e}")
    sys.exit(1)

# Test 2: Find DLL files
print("\n2. Searching for DLL files...")
try:
    import pathlib

    winpty_dir = pathlib.Path(winpty.__file__).parent
    dll_files = list(winpty_dir.rglob("*.dll"))

    if dll_files:
        print(f"   ✓ Found {len(dll_files)} DLL files:")
        for dll in dll_files:
            rel_path = dll.relative_to(winpty_dir.parent)
            print(f"     - {dll}")
            print(f"       → {rel_path.parent}")
    else:
        print(f"   ✗ No DLL files found in {winpty_dir}")

except Exception as e:
    print(f"   ✗ Error searching for DLLs: {e}")
    import traceback

    traceback.print_exc()

# Test 3: Test the collection function
print("\n3. Testing collection function...")


def collect_winpty_binaries() -> list[tuple[str, str]]:
    binaries = []
    try:
        import pathlib

        import winpty

        winpty_dir = pathlib.Path(winpty.__file__).parent
        for dll_file in winpty_dir.rglob("*.dll"):
            rel_path = dll_file.relative_to(winpty_dir.parent)
            binaries.append((str(dll_file), str(rel_path.parent)))
    except ImportError:
        pass
    return binaries


binaries = collect_winpty_binaries()
if binaries:
    print(f"   ✓ Collection function returned {len(binaries)} binaries:")
    for src, dst in binaries:
        print(f"     {src} → {dst}")
else:
    print("   ✗ Collection function returned empty list")

print("\n" + "=" * 60)
print("Test complete")
print("=" * 60)
