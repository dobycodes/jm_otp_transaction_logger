import os
import re
import json
from pathlib import Path

CONFIG_PATH = Path("config.json")
PROJECT_ROOT = Path(".")  # Adjust if needed

def extract_config_keys_with_locations():
    pattern = re.compile(r'config\[\s*[\'"](.+?)[\'"]\s*\]|config\.get\(\s*[\'"](.+?)[\'"]')
    key_usage = {}

    for root, _, files in os.walk(PROJECT_ROOT):
        for file in files:
            if file.endswith(".py"):
                file_path = Path(root) / file
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                        matches = pattern.findall(content)
                        for key1, key2 in matches:
                            key = key1 or key2
                            key_usage.setdefault(key, set()).add(str(file_path))
                except Exception as e:
                    print(f"⚠️ Could not read {file_path}: {e}")
    return key_usage

def audit_config_keys():
    if not CONFIG_PATH.exists():
        print(f"❌ config.json not found at: {CONFIG_PATH.resolve()}")
        return

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)

    config_keys = set(config.keys())
    key_usage = extract_config_keys_with_locations()
    used_keys = set(key_usage.keys())

    missing_keys = used_keys - config_keys
    unused_keys = config_keys - used_keys

    print("\n🔍 Config Key Audit Report")
    print("-" * 40)

    if missing_keys:
        print(f"\n❌ Missing keys in config.json:")
        for key in sorted(missing_keys):
            print(f"  - '{key}' used in:")
            for file in sorted(key_usage[key]):
                print(f"     • {file}")
    else:
        print("✅ All used keys are present in config.json")

    if unused_keys:
        print(f"\n⚠️ Unused keys in config.json:")
        for key in sorted(unused_keys):
            print(f"  - '{key}'")
    else:
        print("✅ No unused keys in config.json")

if __name__ == "__main__":
    audit_config_keys()
