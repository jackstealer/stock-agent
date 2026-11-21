import subprocess

import pytest

from scripts.check_protected import has_reason, main


def test_reason_line_is_accepted():
    assert has_reason("fix limits\n\nRules-change-reason: raise cap after review of #12\n")


@pytest.mark.parametrize("text", ["", "no reason here", "Rules-change-reason: too short",
                                  "  Rules-change-reason: indented lines do not count"])
def test_missing_short_or_indented_reason_is_rejected(text):
    assert not has_reason(text)


def test_unknown_ref_fails_loudly():
    with pytest.raises(subprocess.CalledProcessError):
        main(["x", "no-such-ref-zz9", "HEAD"])


def test_no_protected_change_passes():
    assert main(["x", "HEAD", "HEAD"]) == 0
