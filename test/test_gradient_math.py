import re
import statusline_command as sl


_r = sl.Renderer()



def test_gradient_rgb_at_zero() -> None:
    assert _r.gradient_rgb(0.0) == (40, 210, 80)



def test_gradient_rgb_at_one() -> None:
    assert _r.gradient_rgb(1.0) == (170, 60, 210)


def test_gradient_rgb_clamps_above_one() -> None:
    assert _r.gradient_rgb(1.5) == (170, 60, 210)



def test_gradient_rgb_dim() -> None:
    # int(40 * 0.5)=20, int(210 * 0.5)=105, int(80 * 0.5)=40
    assert _r.gradient_rgb(0.0, dim=0.5) == (20, 105, 40)



def test_gradient_color_format() -> None:
    color = _r.gradient_color(0.5)
    assert color.startswith('\033[38;2;')


def test_gradient_color_round_trips_rgb() -> None:
    color = _r.gradient_color(0.5)
    # parse \033[38;2;r;g;bm
    m = re.match(r'\x1b\[38;2;(\d+);(\d+);(\d+)m', color)
    assert m is not None, f'ANSI escape not parsed: {color!r}'
    parsed = (int(m.group(1)), int(m.group(2)), int(m.group(3)))
    assert parsed == _r.gradient_rgb(0.5)



def test_grad_at_is_static_border() -> None:
    # Flat renderer: grad_at returns one static border colour regardless of
    # column or fill (no positional rainbow gradient, no fill-based fade).
    c = _r.grad_at(0, width=10, fill=1.0)
    assert c == _r.grad_at(9, width=10, fill=1.0)
    assert c == _r.grad_at(5, width=10, fill=0.0)
    assert c.startswith('\033[')


# spark_rgb dim factor

def test_spark_rgb_dim_half() -> None:
    """spark_rgb(t, dim=0.5) == (int(R*0.5), int(G*0.5), int(B*0.5))."""
    r, g, b = _r.spark_rgb(0.7)
    assert _r.spark_rgb(0.7, dim=0.5) == (int(r * 0.5), int(g * 0.5), int(b * 0.5))


def test_spark_rgb_dim_zero() -> None:
    """spark_rgb(t, dim=0.0) == (0, 0, 0) for any t."""
    assert _r.spark_rgb(0.3, dim=0.0) == (0, 0, 0)
    assert _r.spark_rgb(0.7, dim=0.0) == (0, 0, 0)


def test_spark_color_dim_one_matches_default() -> None:
    """spark_color(t, dim=1.0) is byte-identical to spark_color(t)."""
    assert _r.spark_color(0.5) == _r.spark_color(0.5, dim=1.0)
