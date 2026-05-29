import json
from datetime import datetime
import os

HISTORY_FILE = "runs_history.json"

def save_run(task: str, result: dict) -> None:
    run = {
        "id": datetime.now().strftime("%Y%m%d_%H%M%S"),
        "date": datetime.now().isoformat(),
        "task": task,
        "approved": result.get("approved", False),
        "iterations": result.get("iterations", 0),
        "plan": result.get("plan", ""),
        "code": result.get("code", ""),
        "review": result.get("review", ""),
    }
    with open(HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(run, ensure_ascii=False) + "\n")

def load_history() -> list:
    if not os.path.exists(HISTORY_FILE):
        return []
    runs = []
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                runs.append(json.loads(line))
    return runs

def print_history(last_n: int = 5) -> None:
    runs = load_history()
    if not runs:
        print("История пуста.")
        return
    for run in runs[-last_n:]:
        status = "✅" if run["approved"] else "⚠️"
        print(f"{status} [{run['date'][:16]}] {run['task'][:60]}")
