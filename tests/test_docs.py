"""Docs stay honest and portable: no BOM, ASCII only, no overclaims, links resolve."""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOCS = [ROOT / "README.md", *sorted((ROOT / "docs").glob("*.md"))]
BANNED = [
    "production-ready",
    "production ready",
    "beats the market",
    "guaranteed",
    "every experiment was pre-registered",
]
LINK = re.compile(r"\]\(([^)\s]+)\)")


@pytest.mark.parametrize("path", DOCS, ids=lambda p: p.name)
def test_no_bom_and_ascii_only(path):
    raw = path.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf"), "UTF-8 BOM found"
    bad = [(n, line) for n, line in enumerate(raw.decode("utf-8").splitlines(), 1)
           if not line.isascii()]
    assert not bad, f"non-ASCII on lines {[n for n, _ in bad]}"


@pytest.mark.parametrize("path", DOCS, ids=lambda p: p.name)
def test_no_banned_phrases(path):
    text = path.read_text(encoding="utf-8").lower()
    assert not [p for p in BANNED if p in text]


@pytest.mark.parametrize("path", DOCS, ids=lambda p: p.name)
def test_relative_links_resolve(path):
    targets = [t.split("#")[0] for t in LINK.findall(path.read_text(encoding="utf-8"))]
    local = [t for t in targets if t and not re.match(r"[a-z]+:", t)]
    missing = [t for t in local if not (path.parent / t).exists()]
    assert not missing, f"broken links: {missing}"


def test_link_checker_catches_a_broken_link(tmp_path):
    doc = tmp_path / "x.md"
    doc.write_text("[ok](x.md) [web](https://example.com) [bad](nope.md)", encoding="utf-8")
    with pytest.raises(AssertionError, match="nope.md"):
        test_relative_links_resolve(doc)
