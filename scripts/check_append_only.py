"""Fail if a file lost or changed any text compared with a git ref. Appending is the
only allowed change. Usage: python scripts/check_append_only.py <ref> <path>

Comparing text (not `git diff --numstat` deletions) matters: a file without a final
newline shows its last line as deleted on every legitimate append."""
import subprocess
import sys
from pathlib import Path


def is_append_only(old: str, new: str) -> bool:
    old = old.replace("\r\n", "\n").rstrip("\n")
    return new.replace("\r\n", "\n").startswith(old)


def first_changed_line(old: str, new: str) -> int:
    old_l, new_l = old.replace("\r\n", "\n").split("\n"), new.replace("\r\n", "\n").split("\n")
    for n, (a, b) in enumerate(zip(old_l, new_l), 1):
        if a != b:
            return n
    return min(len(old_l), len(new_l)) + 1


def git(*args) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], capture_output=True, text=True, encoding="utf-8")


def main(argv) -> int:
    ref, path = argv[1], argv[2]
    if git("rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}").returncode != 0:
        print(f"::error::unknown git ref {ref!r}; refusing to pass without a comparison")
        return 2
    if git("cat-file", "-e", f"{ref}:{path}").returncode != 0:
        print(f"{path} does not exist at {ref}: nothing to protect yet")
        return 0
    if not Path(path).exists():
        print(f"::error::{path} was deleted; it is append-only")
        return 1
    old = git("show", f"{ref}:{path}").stdout
    new = Path(path).read_text(encoding="utf-8")
    if is_append_only(old, new):
        print(f"{path}: append-only check passed")
        return 0
    print(f"::error file={path},line={first_changed_line(old, new)}::{path} is append-only: "
          "existing text was changed or removed. Add a new section instead.")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
