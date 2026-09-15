import json
from pathlib import Path

p = Path("data/test_results.jsonl")
lines = p.read_text(encoding="utf-8").splitlines()

valid = []
removed = 0
for line in lines:
    if not line.strip():
        continue
    rec = json.loads(line)
    nodeid = rec.get("test_nodeid", "").replace("\\", "/")
    if nodeid.startswith("automation/tests/"):
        valid.append(line)
    else:
        removed += 1

p.write_text("\n".join(valid) + "\n", encoding="utf-8")
print(f"Removed {removed} invalid records, kept {len(valid)} valid records.")
