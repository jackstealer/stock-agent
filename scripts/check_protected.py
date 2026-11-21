"""Fail if a rules file changed without a written reason. Used by CI and the pre-push hook,
so the list below is the only copy. Usage: python scripts/check_protected.py <base> <head>

The reason is a line 'Rules-change-reason: <15+ characters>' in the REASON_TEXT environment
variable (CI puts the PR description there) or else in a commit message base..head."""
import os
import re
import subprocess
import sys

PROTECTED = [
    "docs/gate.md", "docs/trials.yaml", "src/gate/check.py", "src/gate/stats.py",
    "src/risk/limits.py", "src/risk/killswitch.py", "src/backtest/splits.py",
]
REASON = re.compile(r"^Rules-change-reason: .{15,}", re.MULTILINE)


def has_reason(text: str) -> bool:
    return bool(REASON.search(text or ""))


def git(*args) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True, encoding="utf-8",
                          check=True).stdout


def main(argv) -> int:
    base, head = argv[1], argv[2]
    changed = git("diff", "--name-only", base, head, "--", *PROTECTED).split()
    if not changed:
        print("protected files: none changed")
        return 0
    print("protected files changed:", ", ".join(changed))
    text = os.environ.get("REASON_TEXT") or git("log", "--format=%B", f"{base}..{head}")
    if has_reason(text):
        return 0
    print("::error::Add a line 'Rules-change-reason: <why>' (15+ characters) to the PR "
          "description or a commit message.")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
