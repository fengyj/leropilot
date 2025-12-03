#!/usr/bin/env python3
"""Test script to verify pywinpty behavior on Windows."""

import platform
import time

if platform.system() != "Windows":
    print("This script is designed to run on Windows only.")
    print("Skipping test.")
    exit(0)

from winpty import PTY

print("=" * 60)
print("Testing pywinpty PTY class")
print("=" * 60)

# Test 1: Create PTY
print("\n[Test 1] Creating PTY with cols=80, rows=24...")
try:
    pty = PTY(80, 24)
    print("  ✓ PTY created successfully")
    print(f"  fd = {pty.fd}")
except Exception as e:
    print(f"  ✗ Failed to create PTY: {e}")
    exit(1)

# Test 2: Spawn cmd.exe
print("\n[Test 2] Spawning cmd.exe...")
try:
    result = pty.spawn("cmd.exe")
    print(f"  spawn() returned: {result}")
    print(f"  pid = {pty.pid}")
    print(f"  fd = {pty.fd}")
except Exception as e:
    print(f"  ✗ Failed to spawn: {e}")
    exit(1)

# Test 3: Check if alive
print("\n[Test 3] Checking if process is alive...")
time.sleep(0.2)
is_alive = pty.isalive()
print(f"  isalive() = {is_alive}")
if not is_alive:
    print("  ✗ Process died immediately!")
    try:
        exit_status = pty.get_exitstatus()
        print(f"  exit_status = {exit_status}")
    except Exception as e:
        print(f"  Could not get exit status: {e}")
    exit(1)

# Test 4: Read with blocking=False
print("\n[Test 4] Reading with blocking=False...")
try:
    text = pty.read(blocking=False)
    if text:
        print(f"  ✓ Got {len(text)} characters")
        print(f"  Content preview: {repr(text[:100])}")
    else:
        print("  Got empty string (no data yet)")
except Exception as e:
    print(f"  ✗ Read error: {e}")

# Test 5: Wait and read again
print("\n[Test 5] Waiting 0.5s and reading again...")
time.sleep(0.5)
try:
    text = pty.read(blocking=False)
    if text:
        print(f"  ✓ Got {len(text)} characters")
        print(f"  Content preview: {repr(text[:200])}")
    else:
        print("  Got empty string")
        print(f"  isalive() = {pty.isalive()}")
except Exception as e:
    print(f"  ✗ Read error: {e}")

# Test 6: Write a command
print("\n[Test 6] Writing 'echo hello' command...")
try:
    pty.write("echo hello\r\n")
    print("  ✓ Write successful")
except Exception as e:
    print(f"  ✗ Write error: {e}")

# Test 7: Read the output
print("\n[Test 7] Reading command output...")
time.sleep(0.3)
try:
    text = pty.read(blocking=False)
    if text:
        print(f"  ✓ Got {len(text)} characters")
        print(f"  Content: {repr(text)}")
    else:
        print("  Got empty string")
except Exception as e:
    print(f"  ✗ Read error: {e}")

# Test 8: Final status
print("\n[Test 8] Final status check...")
print(f"  isalive() = {pty.isalive()}")
print(f"  pid = {pty.pid}")
print(f"  fd = {pty.fd}")

print("\n" + "=" * 60)
print("Test completed!")
print("=" * 60)

# Cleanup
del pty
