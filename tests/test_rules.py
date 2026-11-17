"""inventory.py --rules · --triage-check · --terms (HT-20 · HT-22).

실행: python -m unittest discover -s tests
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))
import inventory  # noqa: E402

GLOSSARY = "| 표준어 | 쓰지 않을 말 | 뜻 |\n|---|---|---|\n| 결함 | 버그, 이슈 | x |\n| 리뷰 보류 | hold | y |\n| {템플릿} | {자리표시} | z |\n"


def harness():
    d = Path(tempfile.mkdtemp())
    (d / ".claude/rules").mkdir(parents=True)
    (d / ".claude/skills/pr").mkdir(parents=True)
    (d / "CLAUDE.md").write_text(
        "# 프로젝트\n"
        "- 커밋 전에 반드시 테스트를 실행한다\n"
        "- 답변은 적절히 짧게 써 주면 좋다\n"
        "- 2026-11-12 배포 건은 롤백 스크립트를 먼저 확인한다\n"
        "- 버그는 트래커에 등록한다\n"
        "| 표 | 행 |\n|---|---|\n| 표 안 문장은 규칙으로 뽑지 않는다 | x |\n"
        "```\n- 코드 블록 안 문장은 뽑지 않는다\n```\n"
        "줄글이어도 명령형이면 뽑는다\n"
        "그냥 설명하는 줄글\n", encoding="utf-8")
    (d / ".claude/rules/w.md").write_text(
        "---\npaths:\n  - \"docs/**\"\n---\n- WR-01 커밋 전에 테스트를 반드시 실행한다\n", encoding="utf-8")
    (d / ".claude/skills/pr/SKILL.md").write_text(
        "---\nname: pr\ndescription: PR 리뷰\n---\n# PR\n- PR-01 커밋 전에 테스트를 실행하지 않는다\n- PR-02 테스트 없는 PR 은 hold 한다 (`hold` 라벨)\n",
        encoding="utf-8")
    (d / ".claude/glossary.md").write_text(GLOSSARY, encoding="utf-8")
    return d


def items_for(d):
    rows = [inventory.analyze(k, s, p, d) for k, s, p in inventory.discover(d, False, None)]
    g = inventory.load_glossary(inventory.find_glossary(d))
    return inventory.rules_triage(rows, d, g)


class ExtractTest(unittest.TestCase):
    def test_skips_table_code_heading_and_plain_prose(self):
        texts = [t for _, t in inventory.extract_rules(harness() / "CLAUDE.md")]
        self.assertIn("줄글이어도 명령형이면 뽑는다", texts)
        self.assertFalse(any("표 안" in t or "코드 블록" in t or "그냥 설명" in t or t == "프로젝트" for t in texts))

    def test_line_numbers_count_frontmatter(self):
        self.assertEqual(inventory.extract_rules(harness() / ".claude/rules/w.md"), [(5, "WR-01 커밋 전에 테스트를 반드시 실행한다")])


class HintTest(unittest.TestCase):
    def setUp(self):
        self.items = items_for(harness())
        self.by = {i["text"][:10]: i for i in self.items}

    def hints(self, prefix):
        return " ".join(next(i for i in self.items if i["text"].startswith(prefix))["hints"])

    # 1.3.1: 충돌 판정은 /doctor prompt-audit 에 넘긴다. 스크립트는 충돌? 힌트를 달지 않는다
    def test_no_conflict_hint_on_any_row(self):
        self.assertEqual([i["row"] for i in self.items if any(h.startswith("충돌?") for h in i["hints"])], [])

    def test_same_polarity_pair_is_still_duplicate(self):
        self.assertIn("중복?", self.hints("커밋 전에 반드시"))

    def test_opposite_polarity_pair_is_not_relabeled_duplicate(self):
        positive = {i["row"] for i in self.items if "커밋 전에" in i["text"] and "않" not in i["text"]}
        pr01 = next(i for i in self.items if i["text"].startswith("PR-01"))
        self.assertEqual([h for h in pr01["hints"] if h.startswith("중복?") and h.split()[-1] in positive], [])

    def test_triage_header_has_no_conflict_count(self):
        d = harness()
        md = inventory.triage_markdown(items_for(d), None, "test", d)
        header = next(line for line in md.splitlines() if line.startswith("- 힌트"))
        self.assertNotIn("충돌?", header)

    def test_one_off_vague_and_terms(self):
        self.assertIn("일회성?(2026-11-12)", self.hints("2026-11-12"))
        self.assertIn("모호(적절히)", self.hints("답변은"))
        self.assertIn("용어(버그→결함)", self.hints("버그는"))

    def test_backtick_and_placeholder_rows_are_not_terms(self):
        g = inventory.load_glossary(inventory.find_glossary(harness()))
        self.assertEqual([s for s, _ in g], ["결함", "리뷰 보류"])
        self.assertEqual(inventory.term_hits("`hold` 라벨만 쓴다", g), [])
        self.assertEqual(inventory.term_hits("PR 을 hold 한다", g), [("hold", "리뷰 보류")])
        self.assertEqual(inventory.term_hits("household 비용", g), [])


class TriageCheckTest(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(SCRIPTS / "inventory.py"), *args],
                              capture_output=True, text=True, encoding="utf-8")

    def triage_file(self):
        d = harness()
        out = d / "triage.md"
        p = self.run_cli("--root", str(d), "--rules", "--out", str(out))
        self.assertEqual(p.returncode, 0, p.stderr)
        return out

    def fill(self, path, fn):
        lines = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("| R"):
                cells = line.split(" | ")
                cells[-3], cells[-2], cells[-1] = fn(cells[1])
                line = " | ".join(cells)
            lines.append(line)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def test_fresh_table_fails(self):
        p = self.run_cli("--triage-check", str(self.triage_file()))
        self.assertEqual(p.returncode, 1)
        self.assertIn("미확정", p.stdout)

    def test_proposal_with_question_mark_fails(self):
        f = self.triage_file()
        self.fill(f, lambda loc: ("기준", "뺄?", " |"))
        self.assertEqual(self.run_cli("--triage-check", str(f)).returncode, 1)

    def test_merge_without_note_fails(self):
        f = self.triage_file()
        self.fill(f, lambda loc: ("중복", "묶음", " |"))
        c = inventory.triage_check(f)
        self.assertTrue(c["need_note"])
        self.assertFalse(inventory.triage_ok(c))

    def test_all_decided_passes(self):
        f = self.triage_file()
        self.fill(f, lambda loc: ("기준 · 중복", "묶음", "R001 남김 |") if "w.md" in loc else ("기준", "유지", " |"))
        p = self.run_cli("--triage-check", str(f))
        self.assertEqual(p.returncode, 0, p.stdout)


class TermsCliTest(unittest.TestCase):
    def test_terms_exit_codes(self):
        d = harness()
        run = lambda f: subprocess.run([sys.executable, str(SCRIPTS / "inventory.py"), "--root", str(d), "--terms", f],
                                       capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(run("CLAUDE.md").returncode, 1)
        self.assertEqual(run(".claude/rules/w.md").returncode, 0)

    def test_no_glossary_skips(self):
        d = harness()
        (d / ".claude/glossary.md").unlink()
        p = subprocess.run([sys.executable, str(SCRIPTS / "inventory.py"), "--root", str(d), "--glossary", str(d / "none.md"),
                            "--terms", "CLAUDE.md"], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(p.returncode, 0)
        self.assertIn("용어집 없음", p.stdout)


if __name__ == "__main__":
    unittest.main()
