"""Tests for LoadedSkills.from_transcript."""
import json
from pathlib import Path

import statusline_command as sl


def _skill_line(skill_name: str) -> str:
    return json.dumps({
        'type': 'tool_use',
        'name': 'Skill',
        'input': {'skill': skill_name},
    })


def _read_skill_line(skill_name: str) -> str:
    return json.dumps({
        'type': 'tool_use',
        'name': 'Read',
        'input': {'file_path': f'/home/x/.claude/skills/{skill_name}/SKILL.md'},
    })


def test_missing_file_returns_empty() -> None:
    """Missing file returns empty LoadedSkills."""
    result = sl.LoadedSkills.from_transcript('')
    assert result == sl.LoadedSkills(names=[])


def test_skill_tool_call_extracts_name(tmp_path: Path) -> None:
    """Skill tool call line extracts the skill name."""
    p = tmp_path / 'transcript.jsonl'
    p.write_text(_skill_line('python-style') + '\n')

    result = sl.LoadedSkills.from_transcript(str(p))
    assert 'python-style' in result.names


def test_read_skill_md_extracts_name(tmp_path: Path) -> None:
    """Read of .../skills/<name>/SKILL.md extracts the skill name."""
    p = tmp_path / 'transcript.jsonl'
    p.write_text(_read_skill_line('tdd') + '\n')

    result = sl.LoadedSkills.from_transcript(str(p))
    assert 'tdd' in result.names


def test_duplicates_collapsed_order_preserved(tmp_path: Path) -> None:
    """Duplicates collapsed; insertion order preserved."""
    p = tmp_path / 'transcript.jsonl'
    p.write_text(
        _skill_line('tdd') + '\n' +
        _skill_line('python-style') + '\n' +
        _skill_line('tdd') + '\n'  # duplicate
    )

    result = sl.LoadedSkills.from_transcript(str(p))
    assert result.names.count('tdd') == 1
    assert result.names.index('tdd') < result.names.index('python-style')
