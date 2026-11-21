from scripts.check_append_only import first_changed_line, is_append_only, main

OLD = "# Log\nline one\nline two"   # no final newline, like docs/experiments.md on main


def test_append_is_allowed_even_without_final_newline():
    assert is_append_only(OLD, OLD + "\nline three\n")


def test_line_endings_do_not_count_as_changes():
    assert is_append_only(OLD.replace("\n", "\r\n"), OLD + "\n")


def test_unchanged_file_passes():
    assert is_append_only(OLD, OLD)


def test_edited_line_fails_and_is_located():
    new = "# Log\nline 1\nline two\nline three"
    assert not is_append_only(OLD, new)
    assert first_changed_line(OLD, new) == 2


def test_removed_line_fails():
    assert not is_append_only(OLD, "# Log\nline two\nline three")


def test_unknown_ref_fails_closed():
    assert main(["x", "no-such-ref-zz9", "docs/experiments.md"]) == 2
