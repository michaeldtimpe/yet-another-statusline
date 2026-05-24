import statusline_command as sl


# Renderer instance shared by all tests in this module
_r = sl.Renderer()



class TestFillColour:
    def test_0_is_ok(self) -> None:
        assert _r.fill_colour(0) == sl.CLR_GREEN_OK

    def test_69_999_is_ok(self) -> None:
        assert _r.fill_colour(69.999) == sl.CLR_GREEN_OK

    def test_70_is_warn(self) -> None:
        assert _r.fill_colour(70) == sl.CLR_WARN

    def test_89_999_is_warn(self) -> None:
        assert _r.fill_colour(89.999) == sl.CLR_WARN

    def test_90_is_alert(self) -> None:
        assert _r.fill_colour(90) == sl.CLR_ALERT

    def test_100_is_alert(self) -> None:
        assert _r.fill_colour(100) == sl.CLR_ALERT



class TestModelColour:
    def test_opus(self) -> None:
        assert _r.model_colour('Opus 4.7') == sl.CLR_YELLOW

    def test_sonnet_lowercase(self) -> None:
        assert _r.model_colour('sonnet') == sl.CLR_GREEN_OK

    def test_haiku_upper(self) -> None:
        assert _r.model_colour('HAIKU') == sl.CLR_SKY_BLUE

    def test_unknown(self) -> None:
        assert _r.model_colour('gpt-5') == sl.CLR_PURPLE
