from eval.metrics import canonicalize, execution_match


def test_execution_match_ignores_row_order():
    a = [(1, "Alice"), (2, "Bob")]
    b = [(2, "Bob"), (1, "Alice")]
    assert execution_match(a, b) is True


def test_execution_match_ignores_value_type_differences():
    # int vs str-of-int for the same logical value should still match, since
    # canonicalize stringifies everything before comparing.
    a = [(1, "Alice")]
    b = [("1", "Alice")]
    assert execution_match(a, b) is True


def test_execution_match_false_on_join_fanout_duplicate():
    golden = [(1, "Alice"), (2, "Bob")]
    generated = [(1, "Alice"), (1, "Alice"), (2, "Bob")]  # duplicated row, e.g. fan-out
    assert execution_match(golden, generated) is False


def test_execution_match_false_on_genuinely_different_rows():
    golden = [(1, "Alice")]
    generated = [(1, "Alice"), (2, "Bob")]
    assert execution_match(golden, generated) is False


def test_canonicalize_rounds_floats_within_tolerance():
    # 4dp rounding (see FLOAT_ROUND_DP in metrics.py) treats these as equal.
    assert canonicalize([(1.0,)]) == canonicalize([(1.00000001,)])


def test_canonicalize_distinguishes_floats_outside_tolerance():
    assert canonicalize([(1.0,)]) != canonicalize([(1.001,)])
