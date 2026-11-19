"""inventory.py 줄 수 flag (HT-09) — 줄 수는 참고 표시이고, 줄이라는 지시가 아니다.

실행: python -m unittest discover -s tests
"""
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))
import inventory  # noqa: E402


def skill_harness(body_lines):
    """합성 하네스: {스킬 이름: 본문 줄 수} 대로 .claude/skills/{이름}/SKILL.md 를 만든다."""
    d = Path(tempfile.mkdtemp())
    for name, n in body_lines.items():
        (d / f".claude/skills/{name}").mkdir(parents=True)
        body = "\n".join(["# 제목"] + [f"- 본문 {i}" for i in range(2, n + 1)])
        (d / f".claude/skills/{name}/SKILL.md").write_text(
            f"---\nname: {name}\ndescription: 합성 스킬\n---\n{body}\n", encoding="utf-8")
    return d


def rows_by_name(d):
    rows = [inventory.analyze(k, s, p, d) for k, s, p in inventory.discover(d, False, None)]
    return {Path(r["path"]).parent.name: r for r in rows}


class LineCountFlagTest(unittest.TestCase):
    def setUp(self):
        self.rows = rows_by_name(skill_harness({"long": 45, "fit": 40}))

    def test_over_reference_line_count_is_marked_as_reference(self):
        row = self.rows["long"]
        self.assertEqual(row["body_lines"], 45)
        self.assertIn("줄 수 참고(45>40)", row["flags"])
        self.assertFalse(any(f.startswith("줄 초과") for f in row["flags"]))

    def test_within_reference_line_count_has_no_line_flag(self):
        row = self.rows["fit"]
        self.assertEqual(row["body_lines"], 40)
        self.assertFalse(any("줄" in f for f in row["flags"]))


if __name__ == "__main__":
    unittest.main()
