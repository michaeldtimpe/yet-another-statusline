import statusline_command as sl


class TestFmtTok:
    def test_zero(self) -> None:
        assert sl.fmt_tok(0) == '0'

    def test_one(self) -> None:
        assert sl.fmt_tok(1) == '1'

    def test_below_thousand_unchanged(self) -> None:
        assert sl.fmt_tok(999) == '999'

    def test_thousand_rounds_to_k(self) -> None:
        assert sl.fmt_tok(1000) == '1.0K'

    def test_five_digit_rounds_to_one_decimal_k(self) -> None:
        assert sl.fmt_tok(12_345) == '12.3K'

    def test_just_below_million_stays_in_k(self) -> None:
        assert sl.fmt_tok(999_999) == '1000.0K'

    def test_million_displays_as_m(self) -> None:
        assert sl.fmt_tok(1_000_000) == '1.0M'

    def test_multi_million_displays_as_m(self) -> None:
        assert sl.fmt_tok(2_500_000) == '2.5M'


class TestIsWide:
    def test_ascii_not_wide(self) -> None:
        assert sl._is_wide('a') is False

    def test_cjk_not_wide(self) -> None:
        # CJK ideograph — outside the emoji block this function covers
        assert sl._is_wide('中') is False

    def test_emoji_is_wide(self) -> None:
        assert sl._is_wide('🎨') is True

    def test_lower_boundary(self) -> None:
        # U+1F300 is the first emoji in range
        assert sl._is_wide('\U0001F300') is True

    def test_upper_boundary(self) -> None:
        # U+1FAFF is the last codepoint in range
        assert sl._is_wide('\U0001FAFF') is True

    def test_just_below_range(self) -> None:
        assert sl._is_wide('\U0001F2FF') is False

    def test_just_above_range(self) -> None:
        assert sl._is_wide('\U0001FB00') is False


class TestVisibleWidth:
    def test_empty_string(self) -> None:
        assert sl._visible_width('') == 0

    def test_plain_text(self) -> None:
        assert sl._visible_width('hello') == 5

    def test_ansi_wrapped(self) -> None:
        assert sl._visible_width('\x1b[31mhi\x1b[0m') == 2

    def test_emoji_counts_as_two(self) -> None:
        assert sl._visible_width('a🎨b') == 4

    def test_ansi_plus_emoji(self) -> None:
        # ANSI escapes stripped, emoji = 2
        assert sl._visible_width('\x1b[38;5;75m🎨\x1b[0m') == 2


class TestMiddleEllipsis:
    def test_fits_no_truncation(self) -> None:
        assert sl._middle_ellipsis('hello', 10) == 'hello'

    def test_exact_fit(self) -> None:
        assert sl._middle_ellipsis('hello', 5) == 'hello'

    def test_ascii_truncates_width_respected(self) -> None:
        result = sl._middle_ellipsis('abcdefghij', 7)
        assert sl._visible_width(result) <= 7
        assert '…' in result

    def test_ascii_truncates_contains_both_ends(self) -> None:
        result = sl._middle_ellipsis('abcdefghij', 7)
        assert result.startswith('abc')
        assert result.endswith('ij')

    def test_edge_zero_width(self) -> None:
        assert sl._middle_ellipsis('hello', 0) == '…'

    def test_edge_one_width(self) -> None:
        assert sl._middle_ellipsis('hello', 1) == '…'

    def test_edge_two_width(self) -> None:
        result = sl._middle_ellipsis('hello', 2)
        assert sl._visible_width(result) <= 2
        assert '…' in result

    def test_ansi_wrapped_visible_width_respected(self) -> None:
        colored = '\x1b[31m' + 'abcdefghij' + '\x1b[0m'
        result = sl._middle_ellipsis(colored, 7)
        assert sl._visible_width(result) <= 7
        assert '…' in result

    def test_ansi_wrapped_escapes_preserved(self) -> None:
        colored = '\x1b[31m' + 'abcdefghij' + '\x1b[0m'
        result = sl._middle_ellipsis(colored, 7)
        assert '\x1b[' in result
