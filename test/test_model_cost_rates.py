import pytest

import statusline_command as sl



class TestModelCostRates:
    def test_opus_rates(self) -> None:
        # Opus 4.5 and later (incl. Opus 5) are the $5/$25 generation.
        m = sl.Model(id='claude-opus-4-7', display_name='Opus 4.7')
        assert m.cost_rates == (5.00, 25.00)

    def test_legacy_opus_rates(self) -> None:
        # Opus 4 / 4.1 stayed on the older, dearer $15/$75.
        m = sl.Model(id='claude-opus-4-1-20250805', display_name='Opus 4.1')
        assert m.cost_rates == (15.00, 75.00)

    def test_haiku_rates_via_id(self) -> None:
        m = sl.Model(id='claude-haiku-4-5-20251001', display_name='')
        assert m.cost_rates == (1.00, 5.00)

    def test_sonnet_rates(self) -> None:
        m = sl.Model(id='claude-sonnet-4-6')
        assert m.cost_rates == (3.00, 15.00)

    def test_unknown_model_default_rates(self) -> None:
        m = sl.Model(id='gpt-5')
        assert m.cost_rates == (3.00, 15.00)

    # ---------------------------------------------------------------------------
    # 4.2  display_name is preferred over id for matching
    # ---------------------------------------------------------------------------

    def test_display_name_preferred_over_id(self) -> None:
        # id says 'haiku' but display_name says 'Opus' → opus rates
        m = sl.Model(id='claude-haiku-3', display_name='Opus 4.1')
        assert m.cost_rates == (15.00, 75.00)

    def test_display_name_empty_falls_back_to_id(self) -> None:
        # display_name empty → id used for matching
        m = sl.Model(id='claude-haiku-4-5', display_name='')
        assert m.cost_rates == (1.00, 5.00)

    def test_case_insensitive_opus(self) -> None:
        m = sl.Model(id='CLAUDE-OPUS-4', display_name='')
        assert m.cost_rates == (15.00, 75.00)

    def test_case_insensitive_haiku(self) -> None:
        m = sl.Model(id='', display_name='HAIKU 4.5')
        assert m.cost_rates == (1.00, 5.00)


# ---------------------------------------------------------------------------
# 4.3  full rates table — model ids and display names must agree
#      (verified against platform.claude.com pricing, 2026-09-21)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(('name', 'rates'), [
    # Fable / Mythos
    ('claude-fable-5-1',              (10.00, 50.00)),
    ('Fable 5.1',                     (10.00, 50.00)),
    ('claude-mythos-5-1',             (10.00, 50.00)),
    ('Mythos 5.1',                    (10.00, 50.00)),
    # Opus: 4 and 4.1 are the old, dearer tier; 4.5+ and 5 are not
    ('claude-opus-4-20250514',        (15.00, 75.00)),
    ('claude-opus-4-1-20250805',      (15.00, 75.00)),
    ('Opus 4.1',                      (15.00, 75.00)),
    ('claude-opus-4-5',               ( 5.00, 25.00)),
    ('Opus 4.8',                      ( 5.00, 25.00)),
    ('claude-opus-5',                 ( 5.00, 25.00)),
    ('Opus 5 (1M context)',           ( 5.00, 25.00)),
    # Sonnet: 5 dropped to 2/10, earlier generations stay at 3/15
    ('claude-sonnet-5',               ( 2.00, 10.00)),
    ('Sonnet 5',                      ( 2.00, 10.00)),
    ('claude-sonnet-4-6',             ( 3.00, 15.00)),
    ('Sonnet 4.5',                    ( 3.00, 15.00)),
    # Haiku: 4.5 at 1/5, the retired 3.x at 0.80/4
    ('claude-haiku-4-5-20251001',     ( 1.00,  5.00)),
    ('Haiku 4.5',                     ( 1.00,  5.00)),
    ('claude-3-5-haiku-20241022',     ( 0.80,  4.00)),
    ('Haiku 3.5',                     ( 0.80,  4.00)),
    # unknown
    ('gpt-5',                         ( 3.00, 15.00)),
    ('',                              ( 3.00, 15.00)),
])
def test_rates_for_table(name: str, rates: tuple[float, float]) -> None:
    assert sl.TokenAccounting.rates_for(name) == rates


@pytest.mark.parametrize(('name', 'mult'), [
    ('claude-fable-5-1', 0.025),
    ('Fable 5.1',        0.025),
    ('Mythos 5.1',       0.025),
    ('claude-opus-5',    0.1),
    ('Sonnet 5',         0.1),
    ('',                 0.1),
])
def test_cache_read_mult(name: str, mult: float) -> None:
    assert sl.TokenAccounting.cache_read_mult(name) == mult
