import json
from pathlib import Path

import statusline_command as sl

_EXAMPLE = Path(__file__).resolve().parent.parent / 'claude' / 'statusline' / 'session-info-example.json'


def _usage(**kw) -> sl.TranscriptUsage:
    return sl.TranscriptUsage(
        input_tokens                = kw.get('input', 0),
        cache_creation_input_tokens = kw.get('cache_creation', 0),
        cache_read_input_tokens     = kw.get('cache_read', 0),
        output_tokens               = kw.get('output', 0),
    )


def test_effective_tokens_weights_each_class_by_price():
    # Sonnet rates: in $3, out $15 -> output ratio 5x; cache read 0.1x; cache write 1.25x.
    model = sl.Model(id='claude-sonnet-4-6', display_name='Sonnet 4.6')
    usage = _usage(input=20_000, cache_creation=4_000, cache_read=100_000, output=10_000)
    # 20000 + 4000*1.25 + 100000*0.1 + 10000*5 = 85_000
    assert sl.TokenAccounting.effective_tokens(model, usage) == 85_000


def test_effective_tokens_discounts_cache_reads_tenfold():
    # 1M raw cache reads contribute only 100K effective tokens.
    model = sl.Model(id='claude-sonnet-4-6', display_name='Sonnet 4.6')
    usage = _usage(cache_read=1_000_000)
    assert sl.TokenAccounting.effective_tokens(model, usage) == 100_000


def test_effective_tokens_tracks_session_cost_over_input_rate():
    model = sl.Model(id='claude-opus-4-8', display_name='Opus 4.8')
    usage = _usage(input=12_000, cache_creation=3_000, cache_read=400_000, output=9_000)
    rate_in, _ = sl.TokenAccounting.rates_for(model.display_name)
    eff  = sl.TokenAccounting.effective_tokens(model, usage)
    cost = sl.TokenAccounting.session_cost(model, usage)
    assert eff == cost * 1_000_000 / rate_in


def test_session_total_segment_shows_effective_tokens(monkeypatch, tmp_home, strip_ansi):
    usage = _usage(input=20_000, cache_creation=4_000, cache_read=100_000, output=10_000)
    monkeypatch.setattr(sl.TranscriptUsage, 'from_transcript', classmethod(lambda cls, p: usage))

    out = strip_ansi(sl.render(json.loads(_EXAMPLE.read_text()), 200))

    assert 'tok 85.0K' in out


def test_session_total_zero_when_no_usage(monkeypatch, tmp_home, strip_ansi):
    monkeypatch.setattr(sl.TranscriptUsage, 'from_transcript',
                        classmethod(lambda cls, p: _usage()))

    out = strip_ansi(sl.render(json.loads(_EXAMPLE.read_text()), 200))

    assert 'tok 0 ' in out


def test_session_total_drops_before_protected_segments(monkeypatch, tmp_home, strip_ansi):
    # At a narrow width the optional `tok` segment is dropped, but ctx (protected)
    # survives — confirms the new segment is not given protected priority.
    monkeypatch.setattr(sl.TranscriptUsage, 'from_transcript',
                        classmethod(lambda cls, p: _usage(input=10_000, output=8_000)))

    out = strip_ansi(sl.render(json.loads(_EXAMPLE.read_text()), 50))

    assert 'tok ' not in out
    assert 'ctx ' in out
