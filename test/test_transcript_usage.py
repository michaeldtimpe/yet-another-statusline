"""Tests for TranscriptUsage.from_transcript."""
import json
from pathlib import Path

import statusline_command as sl


def _assistant_line(msg_id: str, input_tokens: int = 0, cache_creation: int = 0, cache_read: int = 0, output_tokens: int = 0) -> str:
    return json.dumps({
        'type': 'assistant',
        'message': {
            'id': msg_id,
            'role': 'assistant',
            'usage': {
                'input_tokens': input_tokens,
                'cache_creation_input_tokens': cache_creation,
                'cache_read_input_tokens': cache_read,
                'output_tokens': output_tokens,
            },
        },
    })


def test_missing_path_returns_empty() -> None:
    """Missing path returns TranscriptUsage()."""
    result = sl.TranscriptUsage.from_transcript('/nonexistent/path.jsonl')
    assert result == sl.TranscriptUsage()


def test_two_distinct_assistant_messages_sum_correctly(tmp_path: Path) -> None:
    """Two distinct assistant messages with usage sum correctly."""
    p = tmp_path / 'transcript.jsonl'
    p.write_text(
        _assistant_line('a', input_tokens=10, output_tokens=20) + '\n' +
        _assistant_line('b', input_tokens=10, output_tokens=20) + '\n'
    )
    result = sl.TranscriptUsage.from_transcript(str(p))
    assert result.input_tokens == 20
    assert result.output_tokens == 40


def test_duplicate_message_id_counted_once(tmp_path: Path) -> None:
    """Duplicate message ids are counted only once."""
    p = tmp_path / 'transcript.jsonl'
    line = _assistant_line('a', input_tokens=10, output_tokens=20)
    p.write_text(line + '\n' + line + '\n')

    result = sl.TranscriptUsage.from_transcript(str(p))
    assert result.input_tokens == 10
    assert result.output_tokens == 20


def test_malformed_line_skipped(tmp_path: Path) -> None:
    """Malformed line interleaved with valid lines does not raise, valid line counted."""
    p = tmp_path / 'transcript.jsonl'
    p.write_text(
        'not valid json with "usage" and "assistant" keyword\n' +
        _assistant_line('a', input_tokens=5, output_tokens=10) + '\n'
    )
    result = sl.TranscriptUsage.from_transcript(str(p))
    assert result.input_tokens == 5
    assert result.output_tokens == 10


def _assistant_line_ttl(msg_id: str, cache_5m: int, cache_1h: int) -> str:
    """An assistant line carrying the cache_creation TTL split."""
    return json.dumps({
        'type': 'assistant',
        'message': {
            'id': msg_id,
            'role': 'assistant',
            'usage': {
                'input_tokens': 0,
                'cache_creation_input_tokens': cache_5m + cache_1h,
                'cache_read_input_tokens': 0,
                'output_tokens': 0,
                'cache_creation': {
                    'ephemeral_5m_input_tokens': cache_5m,
                    'ephemeral_1h_input_tokens': cache_1h,
                },
            },
        },
    })


def test_cache_creation_ttl_split_accumulates(tmp_path: Path) -> None:
    """The 1-hour subset is summed separately from the aggregate."""
    p = tmp_path / 'transcript.jsonl'
    p.write_text(
        _assistant_line_ttl('a', cache_5m=100, cache_1h=400) + '\n' +
        _assistant_line_ttl('b', cache_5m=0,   cache_1h=500) + '\n'
    )
    result = sl.TranscriptUsage.from_transcript(str(p))
    assert result.cache_creation_input_tokens == 1000
    assert result.cache_creation_1h_input_tokens == 900
    assert result.cache_write_1h == 900
    assert result.cache_write_5m == 100


def test_entry_without_cache_creation_object_counts_as_5m(tmp_path: Path) -> None:
    """An older entry with no TTL split contributes only 5-minute writes."""
    p = tmp_path / 'transcript.jsonl'
    p.write_text(
        _assistant_line('a', cache_creation=300) + '\n' +           # no cache_creation object
        _assistant_line_ttl('b', cache_5m=0, cache_1h=200) + '\n'
    )
    result = sl.TranscriptUsage.from_transcript(str(p))
    assert result.cache_creation_input_tokens == 500
    assert result.cache_write_1h == 200
    assert result.cache_write_5m == 300
    assert result.billed_in == 500          # billed_in still counts all writes


def test_null_cache_creation_object_tolerated(tmp_path: Path) -> None:
    """A null cache_creation reads as 'no TTL split', not a crash."""
    line = json.loads(_assistant_line('a', cache_creation=100))
    line['message']['usage']['cache_creation'] = None
    p = tmp_path / 'transcript.jsonl'
    p.write_text(json.dumps(line) + '\n')
    result = sl.TranscriptUsage.from_transcript(str(p))
    assert result.cache_creation_1h_input_tokens == 0
    assert result.cache_write_5m == 100


def test_1h_subset_clamped_to_aggregate(tmp_path: Path) -> None:
    """A 1h figure larger than the aggregate is clamped, never negative 5m."""
    line = json.loads(_assistant_line('a', cache_creation=50))
    line['message']['usage']['cache_creation'] = {'ephemeral_1h_input_tokens': 999}
    p = tmp_path / 'transcript.jsonl'
    p.write_text(json.dumps(line) + '\n')
    result = sl.TranscriptUsage.from_transcript(str(p))
    assert result.cache_write_1h == 50
    assert result.cache_write_5m == 0


def test_1h_clamped_on_direct_construction() -> None:
    """The clamp also holds for a hand-built usage (not from a transcript)."""
    u = sl.TranscriptUsage(cache_creation_input_tokens=10, cache_creation_1h_input_tokens=99)
    assert u.cache_write_1h == 10
    assert u.cache_write_5m == 0
