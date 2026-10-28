from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def names(filename: str) -> set:
    out = set()
    for line in (ROOT / filename).read_text(encoding="utf-8-sig").splitlines():
        line = line.split("#")[0].strip()
        if line and not line.startswith("-"):
            for sep in ("==", ">=", "<=", "~="):
                line = line.split(sep)[0]
            out.add(line.strip().lower())
    return out


def test_jobs_requirements_are_a_subset_of_full_requirements():
    assert names("requirements-jobs.txt") <= names("requirements.txt")