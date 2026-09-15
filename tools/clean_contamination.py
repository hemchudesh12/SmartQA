import json
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
RESULTS_FILE = DATA_DIR / "test_results.jsonl"

def clean():
    if not RESULTS_FILE.exists():
        print("No test_results.jsonl found.")
        return

    valid_records = []
    removed_records = 0

    with open(RESULTS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                test_file = record.get("test_file", "").replace("\\", "/")
                test_nodeid = record.get("test_nodeid", "").replace("\\", "/")
                
                # SUT tests start with automation/tests/
                if test_file.startswith("automation/tests/") or test_nodeid.startswith("automation/tests/"):
                    valid_records.append(record)
                else:
                    removed_records += 1
            except json.JSONDecodeError:
                pass

    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        for record in valid_records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"[OK] Cleaned dataset: removed {removed_records} contaminated tooling records, kept {len(valid_records)} valid SUT records.")

if __name__ == "__main__":
    clean()
