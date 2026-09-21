import pytest
import statusline_command as sl



def test_session_cost_sonnet() -> None:
    usage = sl.TranscriptUsage(
        input_tokens=1_000_000,
        output_tokens=1_000_000,
    )
    model = sl.Model(id='claude-sonnet-4-6', display_name='Sonnet')
    cost = sl.compute_session_cost(model, usage)
    # 3.00 * 1 + 15.00 * 1 = 18.0
    assert cost == pytest.approx(18.0, abs=1e-9)



def test_session_cost_opus_cache() -> None:
    usage = sl.TranscriptUsage(
        cache_creation_input_tokens=1_000_000,
        cache_read_input_tokens=1_000_000,
    )
    model = sl.Model(id='opus', display_name='Opus 4.7')
    cost = sl.compute_session_cost(model, usage)
    # Opus 4.7 bills 5.00/25.00; writes default to the 5-minute weight.
    # 5.00 * 1.25 + 5.00 * 0.1 = 6.25 + 0.50 = 6.75
    assert cost == pytest.approx(6.75, abs=1e-9)



def test_session_cost_haiku() -> None:
    usage = sl.TranscriptUsage(
        input_tokens=2_000_000,
        output_tokens=1_000_000,
    )
    model = sl.Model(id='haiku', display_name='Claude Haiku')
    cost = sl.compute_session_cost(model, usage)
    # Current Haiku bills 1.00/5.00: 1.00 * 2 + 5.00 * 1 = 7.00
    assert cost == pytest.approx(7.00, abs=1e-9)



def test_session_cost_default_zero() -> None:
    usage = sl.TranscriptUsage()
    model = sl.Model()
    cost = sl.compute_session_cost(model, usage)
    assert cost == pytest.approx(0.0, abs=1e-9)



def test_day_cost_via_token_log() -> None:
    # Use sonnet rates: rate_in=3.00, rate_out=15.00
    # day_in=500_000, day_cache_read=200_000, day_out=100_000
    # expected = (500_000 * 3.00 + 200_000 * 3.00 * 0.1 + 100_000 * 15.00) / 1_000_000
    #           = (1_500_000 + 60_000 + 1_500_000) / 1_000_000
    #           = 3_060_000 / 1_000_000
    #           = 3.06
    log = sl.TokenLog(day_in=500_000, day_cache_read=200_000, day_out=100_000)
    model = sl.Model(id='claude-sonnet-4-6', display_name='Sonnet')
    cost = sl.compute_day_cost(model, log)
    assert cost == pytest.approx(3.06, abs=1e-9)



def test_effective_session_cost_prefers_payload() -> None:
    # Payload billed cost is authoritative even when the token estimate is huge.
    session = sl.SessionInfo.from_dict({
        'model': {'id': 'claude-opus-4-7', 'display_name': 'Opus 4.7'},
        'cost': {'total_cost_usd': 5.0},
    })
    usage = sl.TranscriptUsage(cache_read_input_tokens=10_000_000)  # est ≈ $5
    assert sl.effective_session_cost(session, usage) == pytest.approx(5.0)



def test_effective_session_cost_honours_real_zero() -> None:
    # A present 0.0 is authoritative, not treated as "absent".
    session = sl.SessionInfo.from_dict({
        'model': {'id': 'opus', 'display_name': 'Opus 4.7'},
        'cost': {'total_cost_usd': 0.0},
    })
    usage = sl.TranscriptUsage(cache_read_input_tokens=10_000_000)
    assert sl.effective_session_cost(session, usage) == pytest.approx(0.0)



def test_effective_session_cost_falls_back_when_absent() -> None:
    # Old Claude Code payload with no 'cost' key -> total_cost_usd is None ->
    # fall back to the token×rate estimate.
    session = sl.SessionInfo.from_dict({
        'model': {'id': 'claude-sonnet-4-6', 'display_name': 'Sonnet'},
    })
    usage = sl.TranscriptUsage(input_tokens=1_000_000, output_tokens=1_000_000)
    assert sl.effective_session_cost(session, usage) == pytest.approx(18.0)


def test_cache_write_ttl_weights() -> None:
    """1-hour writes bill at exactly 2x input, 5-minute writes at 1.25x."""
    model = sl.Model(id='claude-sonnet-4-6', display_name='Sonnet 4.6')   # rate_in 3.00
    hour = sl.TranscriptUsage(
        cache_creation_input_tokens=1_000_000,
        cache_creation_1h_input_tokens=1_000_000,
    )
    five_min = sl.TranscriptUsage(cache_creation_input_tokens=1_000_000)
    plain_in = sl.TranscriptUsage(input_tokens=1_000_000)

    base = sl.compute_session_cost(model, plain_in)
    assert sl.compute_session_cost(model, hour)     == pytest.approx(base * 2.00, abs=1e-9)
    assert sl.compute_session_cost(model, five_min) == pytest.approx(base * 1.25, abs=1e-9)


def test_mixed_ttl_writes_cost() -> None:
    """A mixed batch costs the weighted sum of its two TTL classes."""
    model = sl.Model(id='claude-sonnet-4-6', display_name='Sonnet 4.6')   # rate_in 3.00
    usage = sl.TranscriptUsage(
        cache_creation_input_tokens=1_000_000,
        cache_creation_1h_input_tokens=400_000,
    )
    # (600_000 * 1.25 + 400_000 * 2.00) * 3.00 / 1e6 = (750_000 + 800_000) * 3 / 1e6
    assert sl.compute_session_cost(model, usage) == pytest.approx(4.65, abs=1e-9)


def test_fable_cache_reads_are_a_quarter_of_the_usual_discount() -> None:
    """Fable/Mythos cache hits bill at 0.025x input, not 0.1x."""
    fable  = sl.Model(id='claude-fable-5-1', display_name='Fable 5.1')
    usage  = sl.TranscriptUsage(cache_read_input_tokens=1_000_000)
    # 10.00 * 0.025 = 0.25
    assert sl.compute_session_cost(fable, usage) == pytest.approx(0.25, abs=1e-9)
    opus = sl.Model(id='claude-opus-5', display_name='Opus 5')
    # 5.00 * 0.1 = 0.50
    assert sl.compute_session_cost(opus, usage) == pytest.approx(0.50, abs=1e-9)
