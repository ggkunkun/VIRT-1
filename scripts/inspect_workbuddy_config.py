import os
import json

base = r"C:\Users\Administrator\.workbuddy"
print("Scanning C:\\Users\\Administrator\\.workbuddy for configuration files...")

config_files = []
for root, dirs, files in os.walk(base):
    # limit depth
    rel = os.path.relpath(root, base)
    if rel.count(os.sep) > 2:
        continue
    for f in files:
        if f.endswith((".json", ".yaml", ".yml", ".toml", ".config", ".env", "BOOTSTRAP.md")):
            config_files.append(os.path.join(root, f))

print(f"Found {len(config_files)} config files. Showing top candidates:")
for cf in sorted(config_files):
    rel = os.path.relpath(cf, base)
    if any(k in rel.lower() for k in ["model", "llm", "setting", "config", "endpoint", "connector", "mcp", "skill", "bootstrap"]):
        size = os.path.getsize(cf)
        print(f"  {rel:45s} ({size:,} bytes)")
