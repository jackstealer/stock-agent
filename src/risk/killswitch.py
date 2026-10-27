import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PATH = Path("state/KILL_SWITCH.json")


def is_engaged(path=PATH) -> bool:
    return Path(path).exists()


def status(path=PATH):
    p = Path(path)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def engage(reason: str, path=PATH) -> bool:
    """Returns True if newly engaged. If already engaged, the first reason is kept."""
    p = Path(path)
    if p.exists():
        return False
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"engaged_at": datetime.now(timezone.utc).isoformat(),
                             "reason": reason}), encoding="utf-8")
    return True


def clear(path=PATH) -> None:
    """Human-only. Trading code must never call this."""
    Path(path).unlink(missing_ok=True)


def main(argv) -> None:
    cmd = argv[1] if len(argv) > 1 else "status"
    if cmd == "status":
        s = status()
        print(f"ENGAGED: {s}" if s else "not engaged (trading allowed)")
    elif cmd == "engage":
        engage(" ".join(argv[2:]) or "manual")
        print("kill switch engaged")
    elif cmd == "clear":
        if input("Type CLEAR to re-enable trading: ").strip() == "CLEAR":
            clear()
            print("cleared")
        else:
            print("aborted")
    else:
        print("usage: python -m src.risk.killswitch [status|engage <reason>|clear]")


if __name__ == "__main__":
    main(sys.argv)