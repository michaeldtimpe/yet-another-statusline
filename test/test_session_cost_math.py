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
    # 15.00 * 1.25 + 15.00 * 0.1 = 18.75 + 1.50 = 20.25
    assert cost == pytest.approx(20.25, abs=1e-9)



def test_session_cost_haiku() -> None:
    usage = sl.TranscriptUsage(
        input_tokens=2_000_000,
        output_tokens=1_000_000,
    )
    model = sl.Model(id='haiku', display_name='Claude Haiku')
    cost = sl.compute_session_cost(model, usage)
    # 0.80 * 2 + 4.00 * 1 = 1.60 + 4.00 = 5.60
    assert cost == pytest.approx(5.60, abs=1e-9)



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
    usage = sl.TranscriptUsage(cache_read_input_tokens=10_000_000)  # est ≈ $15
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
