#!/usr/bin/env python3
"""harness-tidy inventory — 하네스 목록(L0)과 대상 주변 후보(L1)를 스크립트로 뽑는다.

LLM 이 본문을 읽지 않고 파일 메타데이터만 본다. 표준 라이브러리만 쓴다.

사용:
  python inventory.py                          # L0: 프로젝트 하네스 목록
  python inventory.py --include-user           # ~/.claude 까지 포함
  python inventory.py --changed-since main     # main 이후 바뀐 파일만 (증분)
  python inventory.py --near .claude/skills/deck-script/SKILL.md   # L1: 대상 주변 후보
  python inventory.py --out docs/reports/2026-11-03-harness-tidy/inventory.md
  python inventory.py --json                   # 기계 처리용
  python inventory.py --rules --include-user --out docs/reports/{날짜}-harness-tidy/rules-triage.md   # triage: 규칙 한 줄 단위 표
  python inventory.py --triage-check docs/reports/{날짜}-harness-tidy/rules-triage.md   # 태그 · 결정이 모두 확정됐는지 (exit 0/1)
  python inventory.py --terms .claude/skills/x/SKILL.md   # 용어집(glossary.md) 위반 lint (exit 0/1)
"""
import argparse
import datetime
import fnmatch
import json
import re
import subprocess
import sys
from pathlib import Path

LIMITS = {"skill": 40, "command": 40, "agent": 40, "prompt": 40, "claude-md": 50, "rule": 30}
VERSION_FILE = Path(__file__).resolve().parent.parent / "VERSION"
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".claude/worktrees"}
ID_RE = re.compile(r"^\s*-\s*([A-Z]{1,6})-(\d{2,3})\b", re.M)
REF_RE = re.compile(r"(?<![\w`])@([~\w./\\-]+\.\w+)")
QUOTE_RE = re.compile(r"[「“\"]([^」”\"\n]{2,30})[」”\"]")
PATHLIKE_RE = re.compile(r"[\w.\-*]+/[\w.\-*/]+|[\w\-]+\.(?:js|ts|py|md|json|ps1|docx|pptx)\b")
ID_CELL_RE = re.compile(r"^[A-Z]{1,6}-\d{2,3}(\s*[,·]\s*[A-Z]{1,6}-\d{2,3})*$")
CHANGE_KINDS = ("유지", "수정", "묶음", "이동", "뺄")

# --- triage (HT-20) · 용어집 (HT-22) ---
TRIAGE_TAGS = ("기준", "일회성", "중복", "충돌", "모호")
LIST_RE = re.compile(r"^\s*(?:>\s*)?(?:[-*+]|\d+[.)])\s+(.*\S)\s*$")
IMPERATIVE_RE = re.compile(
    r"(한다[.)]?$|하라|해라|할 것|않는다|말 것|마라|금지|하세요|해야|하지 마|않도록|"
    r"\bMUST\b|\bNEVER\b|\bALWAYS\b|\bdo not\b|\bdon't\b)", re.I)
NEG_RE = re.compile(r"(않|말 것|마라|금지|하지 마|못한다|\bnever\b|\bdon't\b|\bdo not\b|\bnot\b)", re.I)
ONE_OFF_RE = re.compile(
    r"(\d{4}-\d{2}-\d{2}|(?<![\w/])\d{1,2}/\d{1,2}(?![\w/])|이번 ?(?:주|달|PR|작업|세션|배포)|오늘|방금|어제|"
    r"이 PR|(?<![\w&])#\d{2,}\b|\bv\d+\.\d+)")
VAGUE_RE = re.compile(r"(적절히|적당히|가능하면|가급적|하면 좋다|좋겠다|알아서|필요시|필요하면|웬만하면|등등|"
                      r"\bappropriately\b|\bif possible\b|\bas needed\b)", re.I)
NEG_STRIP_RE = re.compile(r"(하지 않|지 않|않|말 것|마라|금지|하지 마|못|\bnever\b|\bdon't\b|\bdo not\b|\bnot\b)", re.I)
RULE_ID_RE = re.compile(r"\b([A-Z]{1,6}-\d{2,3})\b")
NORM_STRIP_RE = re.compile(r"\b[A-Z]{1,6}-\d{2,3}\b|\((?:lint|judge)\)|[\s\W_]+", re.I)


def read(p):
    try:
        return p.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return p.read_text(encoding="utf-8", errors="replace")


def split_frontmatter(text):
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end < 0:
        return {}, text
    fm_raw, body = text[3:end], text[end + 4:]
    fm, key = {}, None
    for line in fm_raw.splitlines():
        if re.match(r"^\s+-\s+", line) and key:
            fm.setdefault(key, [])
            if isinstance(fm[key], list):
                fm[key].append(line.strip()[2:].strip().strip("'\""))
            continue
        m = re.match(r"^([\w-]+)\s*:\s*(.*)$", line)
        if m:
            key, val = m.group(1), m.group(2).strip().strip("'\"")
            fm[key] = val if val else []
    return fm, body.lstrip("\n")


def strip_code(text):
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    return re.sub(r"`[^`\n]*`", "", text)


def walk(base, pattern):
    if not base.exists():
        return []
    out = []
    for p in base.glob(pattern):
        rel = p.relative_to(base).as_posix()
        if any(f"/{d}/" in f"/{rel}/" for d in SKIP_DIRS):
            continue
        if p.is_file():
            out.append(p)
    return sorted(out)


def discover(root, include_user, memory, extra=()):
    found = []  # (kind, scope, path)
    def add(kind, scope, paths):
        found.extend((kind, scope, p) for p in paths)

    for name in ("CLAUDE.md", "CLAUDE.local.md", "AGENTS.md"):
        add("claude-md", "project", walk(root, f"**/{name}"))
    add("claude-md", "project", walk(root / ".claude", "CLAUDE.md"))
    add("rule", "project", walk(root / ".claude/rules", "**/*.md"))
    add("skill", "project", walk(root / ".claude/skills", "*/SKILL.md"))
    add("command", "project", walk(root / ".claude/commands", "**/*.md"))
    add("agent", "project", walk(root / ".claude/agents", "**/*.md"))
    add("style", "project", walk(root / ".claude/output-styles", "**/*.md"))
    if include_user:
        home = Path.home() / ".claude"
        add("claude-md", "user", walk(home, "CLAUDE.md"))
        add("rule", "user", walk(home / "rules", "**/*.md"))
        add("skill", "user", walk(home / "skills", "*/SKILL.md"))
        add("command", "user", walk(home / "commands", "**/*.md"))
        add("agent", "user", walk(home / "agents", "**/*.md"))
        add("style", "user", walk(home / "output-styles", "**/*.md"))
    for pat in extra or ():
        add("prompt", "project", [p for p in walk(root, pat) if p.suffix == ".md"])
    if memory:
        mp = Path(memory).expanduser()
        if mp.exists():
            add("memory", "user", [mp])
    seen, uniq = set(), []
    for k, s, p in found:
        rp = p.resolve()
        if rp not in seen:
            seen.add(rp)
            uniq.append((k, s, p))
    return uniq


def settings_summary(root, include_user):
    files = [root / ".claude/settings.json", root / ".claude/settings.local.json"]
    if include_user:
        files.append(Path.home() / ".claude/settings.json")
    rows = []
    for f in files:
        if not f.exists():
            continue
        try:
            data = json.loads(read(f))
        except json.JSONDecodeError as e:
            rows.append({"path": str(f), "error": f"JSON 오류: {e}"})
            continue
        hooks = data.get("hooks", {}) or {}
        n_hooks = sum(len(h.get("hooks", [])) for evs in hooks.values() for h in (evs or []))
        perm = data.get("permissions", {}) or {}
        rows.append({
            "path": str(f),
            "hooks": {ev: len(v or []) for ev, v in hooks.items()},
            "hook_commands": n_hooks,
            "allow": len(perm.get("allow", []) or []),
            "deny": len(perm.get("deny", []) or []),
            "outputStyle": data.get("outputStyle", ""),
            "agent": data.get("agent", ""),
        })
    mcp = root / ".mcp.json"
    if mcp.exists():
        try:
            servers = list((json.loads(read(mcp)).get("mcpServers") or {}).keys())
        except json.JSONDecodeError:
            servers = ["(JSON 오류)"]
        rows.append({"path": str(mcp), "mcp_servers": servers})
    return rows


def analyze(kind, scope, path, root):
    text = read(path)
    fm, body = split_frontmatter(text)
    lines = text.splitlines()
    body_lines = body.splitlines()
    nonempty = [l for l in body_lines if l.strip()]
    long_lines = [l for l in nonempty if len(l) > 100 and not l.lstrip().startswith(("|", "```"))]
    ids = ID_RE.findall(body)
    refs = []
    for ref in REF_RE.findall(strip_code(body)):
        target = (path.parent / ref).expanduser() if not ref.startswith("~") else Path(ref).expanduser()
        if not target.exists() and not (root / ref).exists():
            refs.append(ref)
    flags = []
    limit = LIMITS.get(kind)
    if limit and len(body_lines) > limit:
        flags.append(f"줄 초과({len(body_lines)}>{limit})")
    if kind == "agent" and not fm.get("tools"):
        flags.append("tools 생략=전부 상속")
    if kind == "command":
        flags.append("skill 이전 후보")
    if kind in ("skill", "agent") and not fm.get("description"):
        flags.append("description 없음")
    if refs:
        flags.append("끊긴 @참조: " + ", ".join(refs[:3]))
    if kind == "memory" and (len(lines) > 200 or len(text.encode("utf-8")) > 25_000):
        flags.append("MEMORY 한도 근접/초과")
    name = fm.get("name") or (path.parent.name if kind == "skill" else path.stem)
    try:
        shown = path.relative_to(root).as_posix()
    except ValueError:
        shown = str(path).replace(str(Path.home()), "~")
    return {
        "kind": kind, "scope": scope, "path": shown, "abs": str(path.resolve()), "name": name,
        "lines": len(lines), "body_lines": len(body_lines),
        "desc_chars": len(fm.get("description", "")) if isinstance(fm.get("description"), str) else 0,
        "paths": fm.get("paths") if isinstance(fm.get("paths"), list) else ([fm["paths"]] if fm.get("paths") else []),
        "tools": fm.get("tools", ""), "skills": fm.get("skills") if isinstance(fm.get("skills"), list) else [],
        "ids": len(ids), "id_prefixes": sorted({p for p, _ in ids}),
        "prose": round(len(long_lines) / len(nonempty), 2) if nonempty else 0.0,
        "flags": flags,
    }


def name_conflicts(rows):
    by = {}
    for r in rows:
        if r["kind"] in ("skill", "command", "agent"):
            by.setdefault((r["kind"] if r["kind"] == "agent" else "skill", r["name"]), []).append(r["path"])
    return {f"{k[0]}:{k[1]}": v for k, v in by.items() if len(v) > 1}


def changed_files(root, ref):
    def run(args):
        try:
            return subprocess.run(args, cwd=root, capture_output=True, text=True, encoding="utf-8").stdout.splitlines()
        except FileNotFoundError:
            return []
    names = set(run(["git", "diff", "--name-only", f"{ref}...HEAD"]))
    names |= set(run(["git", "diff", "--name-only"]))
    names |= set(run(["git", "ls-files", "--others", "--exclude-standard"]))
    return {(root / n).resolve() for n in names if n}


def near(target, rows, root):
    tpath = (root / target) if not Path(target).is_absolute() else Path(target)
    text = read(tpath)
    _, body = split_frontmatter(text)
    terms = {t.strip() for t in QUOTE_RE.findall(body) if len(t.strip()) >= 2}
    pathlike = set(PATHLIKE_RE.findall(body))
    stem = tpath.parent.name if tpath.name == "SKILL.md" else tpath.stem
    tabs = str(tpath.resolve())
    hits = []
    for r in rows:
        if r["abs"] == tabs:
            continue
        other = read(Path(r["abs"]))
        matched = sorted(t for t in terms if t in other)
        mentions = stem in other
        glob_hit = [g for g in r["paths"] for p in pathlike if fnmatch.fnmatch(p, g) or fnmatch.fnmatch(p, g.rstrip("/*") + "/*")]
        if matched or mentions or glob_hit:
            lines = []
            for i, line in enumerate(other.splitlines(), 1):
                if any(t in line for t in matched[:10]):
                    lines.append(i)
            hits.append({
                "path": r["path"], "kind": r["kind"],
                "shared_terms": len(matched), "examples": matched[:5], "lines": lines[:10],
                "mentions_target": mentions, "paths_overlap": sorted(set(glob_hit))[:3],
            })
    hits.sort(key=lambda h: (-(h["shared_terms"] + 5 * bool(h["paths_overlap"])), h["path"]))
    return {"target": target, "terms": len(terms), "candidates": hits}


def coverage(evals_dir):
    """mapping.md 행 대비 evals.json 케이스 커버리지 (HT-10 · HT-18).
    rc.2 형식: 'Eval 케이스' 칸의 id 를 evals.json id 와 대조.
    rc.1 이전 형식(칸 없음): 행의 새 ID 가 evals.json expected_output 의 [ID] 에 있는지로 대조."""
    d = Path(evals_dir)
    mp, ep = d / "mapping.md", d / "evals.json"
    if not mp.exists():
        return {"error": f"{mp} 없음"}
    cases = {}
    if ep.exists():
        try:
            for e in json.loads(read(ep)).get("evals", []):
                cases[str(e.get("id"))] = e.get("expected_output", "")
        except json.JSONDecodeError as e:
            return {"error": f"evals.json JSON 오류: {e}"}
    tagged = set(re.findall(r"\[([A-Z]{1,6}-\d{2,3}|M\d{2,3})\]", " ".join(cases.values())))
    header, rows = None, []
    for line in read(mp).splitlines():
        if not line.strip().startswith("|"):
            if header is not None:
                break  # 첫 표만 매핑표다 (뒤따르는 표는 다른 기록)
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if header is None:
            header = cells
            continue
        if set("".join(cells)) <= set("-: "):
            continue
        rows.append(dict(zip(header, cells)))
    col = next((h for h in (header or []) if "Eval" in h), None)
    idcol = next((h for h in (header or []) if "새 ID" in h), None)
    rowcol = next((h for h in (header or []) if h == "행"), None)
    kindcol = next((h for h in (header or []) if "변경 유형" in h), None)
    result = {"mapping_rows": len(rows), "covered": 0, "excused": 0, "missing": [], "broken_ids": [],
              "no_id": [], "bad_kind": [], "mode": "rc.2" if col else "rc.1-fallback"}
    for r in rows:
        label = r.get(rowcol) or r.get(idcol) or "?"
        kind = r.get(kindcol, "")
        rid = r.get(idcol, "") if idcol else ""
        if idcol and not (ID_CELL_RE.match(rid) or rid.startswith("없음(사유")):
            result["no_id"].append(f"{label} ({kind})")
        if kindcol and kind not in CHANGE_KINDS:
            result["bad_kind"].append(f"{label} ({kind})")
        if col:
            val = r.get(col, "")
            if val.startswith("없음"):
                result["excused"] += 1
                continue
            ids = [x.strip() for x in re.split(r"[,\s]+", val) if x.strip()]
            if not ids:
                result["missing"].append(f"{label} ({kind})")
                continue
            bad = [i for i in ids if i not in cases]
            if bad:
                result["broken_ids"].append(f"{label}: {', '.join(bad)}")
            else:
                result["covered"] += 1
        else:
            if rid and rid not in ("—", "-") and rid in tagged:
                result["covered"] += 1
            else:
                result["missing"].append(f"{label} ({kind})")
    n = result["mapping_rows"]
    result["coverage_pct"] = round(100 * (result["covered"] + result["excused"]) / n, 1) if n else 0.0
    return result


def coverage_ok(c):
    """넘김(HT-13) 가능 여부: 커버리지 100% · 깨진 id 0 · ID 없음 0 · 변경 유형 오류 0."""
    return (c.get("coverage_pct") == 100.0 and not c.get("broken_ids")
            and not c.get("no_id") and not c.get("bad_kind"))


# --- triage (HT-20): 규칙 한 줄 단위 표 ---
def body_lines_with_numbers(text):
    """(파일 기준 줄 번호, 줄) — frontmatter · 코드 블록 · HTML 주석을 건너뛴다. 줄 번호는 파일 첫 줄 = 1."""
    lines = text.splitlines()
    start = 0
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                start = i + 1
                break
    in_code = in_comment = False
    for i in range(start, len(lines)):
        line = lines[i]
        s = line.strip()
        if s.startswith("```") or s.startswith("~~~"):
            in_code = not in_code
            continue
        if in_code:
            continue
        if in_comment or s.startswith("<!--"):
            in_comment = "-->" not in s
            continue
        yield i + 1, line


def is_imperative(text):
    """명령형 · 규범 문장: IMPERATIVE_RE 이거나 '~ㄴ다 · ~는다'(한다 · 쓴다 · 뽑는다)로 끝난다. 있다 · 없다 · 이다는 아니다."""
    if IMPERATIVE_RE.search(text):
        return True
    t = re.sub(r"[\s.)」\]]+$", "", re.sub(r"\s*\([^)]*\)\s*$", "", text))
    if len(t) < 2 or not t.endswith("다"):
        return False
    c = t[-2]
    return t.endswith("는다") or ("가" <= c <= "힣" and (ord(c) - 0xAC00) % 28 == 4)


def extract_rules(path):
    """규칙 후보 줄: 목록 항목 · 명령형으로 끝나는 줄글. 제목 · 표 · 빈 줄 · 아주 짧은 줄은 뺀다."""
    out = []
    for no, line in body_lines_with_numbers(read(path)):
        s = line.strip()
        if not s or s.startswith(("#", "|")):
            continue
        m = LIST_RE.match(line)
        text = m.group(1) if m else s
        if len(NORM_STRIP_RE.sub("", text)) < 6:
            continue
        if m or is_imperative(text):
            out.append((no, text))
    return out


def _bigrams(text):
    t = NORM_STRIP_RE.sub("", text).lower()
    return {t[i:i + 2] for i in range(len(t) - 1)}


def similarity(a, b):
    """문자 2-gram Jaccard 와 포함도(짧은 쪽 기준 × 0.85) 중 큰 값. 0~1."""
    if not a or not b:
        return 0.0
    inter = len(a & b)
    jac = inter / len(a | b)
    small = min(len(a), len(b))
    contain = inter / small * 0.85 if small >= 6 else 0.0
    return max(jac, contain)


def find_glossary(root, explicit=None):
    if explicit:
        p = Path(explicit).expanduser()
        return p if p.exists() else None
    for p in (Path(root) / ".claude/glossary.md", Path.home() / ".claude/glossary.md"):
        if p.exists():
            return p
    return None


def load_glossary(path):
    """첫 표: | 표준어 | 쓰지 않을 말 | … | → [(표준어, [변형…])]. 변형은 , · / 로 나눈다."""
    if not path:
        return []
    entries, header = [], None
    for line in read(Path(path)).splitlines():
        s = line.strip()
        if not s.startswith("|"):
            if header is not None and entries:
                break
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if header is None:
            header = cells
            continue
        if set("".join(cells)) <= set("-: "):
            continue
        if len(cells) >= 2 and cells[0] and not cells[0].startswith("{"):
            variants = [v.strip().strip("`「」\"") for v in re.split(r"[,·/]", cells[1]) if v.strip()]
            variants = [v for v in variants if v and v != cells[0] and v not in ("-", "—")]
            if variants:
                entries.append((cells[0], variants))
    return entries


def term_hits(text, glossary):
    """줄 하나에서 쓰지 않을 말을 찾는다 → [(변형, 표준어)]. 백틱 안은 검사하지 않는다."""
    plain = re.sub(r"`[^`\n]*`", "", text)
    hits = []
    for std, variants in glossary:
        for v in variants:
            if re.search(r"[A-Za-z]", v):
                found = re.search(rf"(?<![A-Za-z]){re.escape(v)}(?![A-Za-z])", plain, re.I)
            else:
                found = v in plain.replace(std, "")  # 표준어 안에 든 변형은 위반이 아니다
            if found:
                hits.append((v, std))
    return hits


def rules_triage(rows, root, glossary=(), dup=0.55, max_pairs=3):
    """rows(analyze 결과)에서 규칙 후보를 뽑아 R001… 행과 힌트를 만든다."""
    items = []
    for r in rows:
        for no, text in extract_rules(Path(r["abs"])):
            items.append({"row": "", "path": r["path"], "scope": r["scope"], "kind": r["kind"], "line": no,
                          "text": text, "ids": RULE_ID_RE.findall(text)[:2], "hints": []})
    for n, it in enumerate(items, 1):
        it["row"] = f"R{n:03d}"
    # 중복 = 같은 극성으로 비슷함. 행마다 유사도 상위 max_pairs 개만 남긴다
    # 극성이 다른 쌍은 힌트를 달지 않는다 — 충돌 판정은 /doctor prompt-audit 에 넘긴다 (1.3.1, modes.md triage)
    grams = [_bigrams(NEG_STRIP_RE.sub("", it["text"])) for it in items]
    neg = [bool(NEG_RE.search(it["text"])) for it in items]
    pairs = {i: [] for i in range(len(items))}
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            if neg[i] != neg[j]:
                continue
            sim = similarity(grams[i], grams[j])
            if sim < dup:
                continue
            pairs[i].append((sim, j))
            pairs[j].append((sim, i))
    for i, ps in pairs.items():
        for sim, j in sorted(ps, key=lambda x: -x[0])[:max_pairs]:
            items[i]["hints"].append(f"중복? {items[j]['row']}")
    for it in items:
        m = ONE_OFF_RE.search(it["text"])
        if m:
            it["hints"].append(f"일회성?({m.group(0)})")
        m = VAGUE_RE.search(it["text"])
        if m:
            it["hints"].append(f"모호({m.group(0)})")
        for v, std in term_hits(it["text"], glossary):
            it["hints"].append(f"용어({v}→{std})")
    return items


def _cell(text):
    return text.replace("|", "\\|")


def triage_markdown(items, glossary_path, version, root):
    files = {}
    for it in items:
        f = files.setdefault((it["path"], it["scope"], it["kind"]), [0, 0])
        f[0] += 1
        f[1] += bool(it["hints"])
    count = lambda p: sum(1 for it in items if any(h.startswith(p) for h in it["hints"]))
    try:
        gshown = Path(glossary_path).resolve().relative_to(Path(root).resolve()).as_posix() if glossary_path else "없음"
    except ValueError:
        gshown = str(glossary_path).replace(str(Path.home()), "~")
    out = [
        f"# 규칙 전수 표 (triage, HT-20) — harness-tidy {version}", "",
        f"- 생성: {datetime.date.today().isoformat()} · 파일 {len(files)}개 · 규칙 후보 {len(items)}줄 · 용어집 {gshown}",
        f"- 힌트(스크립트 추정): 중복? {count('중복?')} · 일회성? {count('일회성?')} · 모호 {count('모호')} · 용어 {count('용어')}",
        "- 충돌 태그는 스크립트가 달지 않는다: `/doctor prompt-audit {범위}` 의 Group 2 지적(지시 파일 간 모순)을 해당 행에 옮긴다 (modes.md triage)",
        "- 태그: " + " · ".join(TRIAGE_TAGS) + " (여러 개는 ·) / 결정: " + " · ".join(CHANGE_KINDS)
        + " (묶음 · 이동은 비고에 상대 행 · 옮길 곳)",
        "- Claude 는 태그 · 결정을 제안하며 끝에 ? 를 붙인다. 사용자가 확정하면 ? 를 지운다. 규칙이 아닌 줄은 태그 칸에 `규칙 아님`, 결정 `유지`",
        "- 줄 번호는 스크립트가 파일을 직접 센 값이다. 대상별 검토 문서로 옮길 때 Grep 도구로 다시 확인한다 (HT-03)",
        "- 확인: `python scripts/inventory.py --triage-check {이 파일}` — 미확정 0 일 때 exit 0", "",
        "## 파일별", "", "| 파일 | 범위 | 종류 | 규칙 후보 | 힌트 있음 |", "|---|---|---|---|---|",
    ]
    for (p, s, k), (n, h) in sorted(files.items(), key=lambda x: -x[1][0]):
        out.append(f"| {p} | {s} | {k} | {n} | {h} |")
    out += ["", "## 규칙", "", "| 행 | 파일:줄 | 기존 ID | 원문 | 힌트 | 태그 | 결정 | 비고 |", "|---|---|---|---|---|---|---|---|"]
    for it in items:
        out.append(f"| {it['row']} | {it['path']}:{it['line']} | {' · '.join(it['ids'])} | 「{_cell(it['text'])}」 | "
                   f"{' · '.join(it['hints'])} |  |  |  |")
    return "\n".join(out) + "\n"


def _first_table_with(text, needle):
    """머리글에 needle 칸이 있는 첫 표의 행들. 셀 안의 \\| 는 나누지 않는다."""
    tables, cur = [], []
    for line in text.splitlines() + [""]:
        if line.strip().startswith("|"):
            cur.append(line.strip())
        elif cur:
            tables.append(cur)
            cur = []
    for t in tables:
        split = lambda s: [c.strip() for c in re.split(r"(?<!\\)\|", s.strip("|"))]
        header = split(t[0])
        if needle not in header:
            continue
        return [dict(zip(header, split(s))) for s in t[1:] if not set(s) <= set("|-: ")]
    return []


def triage_check(path):
    """태그 · 결정이 모두 확정됐는지 (HT-20). 미확정(빈칸 · ? 남음 · 목록 밖 값)과 비고 누락을 센다."""
    p = Path(path)
    if not p.exists():
        return {"error": f"{p} 없음"}
    rows = _first_table_with(read(p), "결정")
    res = {"rows": len(rows), "undecided": [], "bad_tag": [], "need_note": [],
           "decisions": {k: 0 for k in CHANGE_KINDS}, "tags": {t: 0 for t in TRIAGE_TAGS + ("규칙 아님",)}}
    for r in rows:
        label = r.get("행", "?")
        dec, tag, note = r.get("결정", ""), r.get("태그", ""), r.get("비고", "")
        if dec not in CHANGE_KINDS:
            res["undecided"].append(f"{label} (결정: {dec or '빈칸'})")
        else:
            res["decisions"][dec] += 1
        tags = [t.strip() for t in re.split(r"[,·]", tag) if t.strip()]
        if not tags or any(t not in res["tags"] for t in tags):
            res["bad_tag"].append(f"{label} (태그: {tag or '빈칸'})")
        else:
            for t in tags:
                res["tags"][t] += 1
        if dec in ("묶음", "이동") and not note:
            res["need_note"].append(f"{label} ({dec}: 비고에 상대 행 · 옮길 곳)")
    if not rows:
        res["error"] = "결정 칸이 있는 표를 찾지 못했다"
    return res


def triage_ok(c):
    return not c.get("error") and not c["undecided"] and not c["bad_tag"] and not c["need_note"]


def terms_check(path, glossary):
    """용어집 위반 (HT-22): 파일:줄 · 변형 → 표준어. 코드 블록 · frontmatter · 용어집 표 자신은 건너뛴다."""
    hits = []
    for no, line in body_lines_with_numbers(read(Path(path))):
        for v, std in term_hits(line, glossary):
            hits.append({"line": no, "found": v, "use": std, "text": line.strip()})
    return hits


def to_markdown(rows, settings, conflicts, near_result, changed_only):
    out = ["# 하네스 인벤토리 (L0)", ""]
    if changed_only:
        out += [f"- 증분: {changed_only} 이후 바뀐 파일만", ""]
    out += ["| 종류 | 범위 | 경로 | 본문 줄 | ID | 긴 줄 비율 | paths · tools · skills | 표시 |", "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        extra = []
        if r["paths"]:
            extra.append("paths: " + ", ".join(r["paths"][:2]))
        if r["tools"]:
            extra.append(f"tools: {r['tools']}")
        if r["skills"]:
            extra.append("skills: " + ", ".join(r["skills"][:3]))
        ids = f"{r['ids']} ({'/'.join(r['id_prefixes'])})" if r["ids"] else "0"
        out.append(f"| {r['kind']} | {r['scope']} | {r['path']} | {r['body_lines']} | {ids} | {r['prose']} | {' · '.join(extra)} | {' · '.join(r['flags'])} |")
    if conflicts:
        out += ["", "## 이름 충돌 (같은 이름은 우선순위 높은 쪽만 쓰인다)", ""]
        out += [f"- {k}: {', '.join(v)}" for k, v in conflicts.items()]
    if settings:
        out += ["", "## 실행 · 설정 계층 (목록만)", ""]
        for s in settings:
            out.append(f"- `{s['path']}`: " + ", ".join(f"{k}={v}" for k, v in s.items() if k != "path"))
    if near_result:
        out += ["", f"# 대상 주변 후보 (L1): {near_result['target']}", "",
                f"- 대상에서 뽑은 인용 표현 {near_result['terms']}개로 하네스를 grep 했다. Claude 는 아래 후보만 읽는다.", "",
                "| 경로 | 종류 | 겹친 표현 수 | 예 | 줄 | 대상 이름 언급 | paths 겹침 |", "|---|---|---|---|---|---|---|"]
        for h in near_result["candidates"]:
            out.append(f"| {h['path']} | {h['kind']} | {h['shared_terms']} | {' · '.join(h['examples'])} | {', '.join(map(str, h['lines']))} | {'O' if h['mentions_target'] else ''} | {', '.join(h['paths_overlap'])} |")
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser(description="harness-tidy inventory (L0 목록 · L1 대상 주변)")
    ap.add_argument("--root", default=".", help="프로젝트 루트 (기본: 현재 폴더)")
    ap.add_argument("--include-user", action="store_true", help="~/.claude 사용자 범위 포함")
    ap.add_argument("--memory", help="auto memory MEMORY.md 경로 (선택)")
    ap.add_argument("--changed-since", metavar="REF", help="git REF 이후 바뀐 파일만 표시")
    ap.add_argument("--near", metavar="TARGET", help="L1: 이 대상 파일과 겹치는 후보만 추림")
    ap.add_argument("--out", help="결과 파일 경로 (기본: 표준 출력)")
    ap.add_argument("--json", action="store_true", help="JSON 으로 출력")
    ap.add_argument("--extra", action="append", metavar="GLOB", help='표준 위치 밖 지시 파일 (예: "harness/**/*.md"), 여러 번 지정 가능')
    ap.add_argument("--file", metavar="PATH", help="파일 하나의 전체 · 본문 줄 수만 출력 (wc -l 대신, OS 무관)")
    ap.add_argument("--version", action="store_true", help="harness-tidy 판 출력")
    ap.add_argument("--coverage", metavar="DIR", help="evals/{대상} 의 mapping.md 대비 evals.json 커버리지 확인")
    ap.add_argument("--rules", action="store_true", help="triage(HT-20): 하네스 전체 규칙을 한 줄 단위 표로 (중복 · 일회성 · 모호 · 용어 힌트, 충돌은 /doctor prompt-audit)")
    ap.add_argument("--dup-threshold", type=float, default=0.55, help="--rules 중복 후보 유사도 (기본 0.55)")
    ap.add_argument("--triage-check", metavar="FILE", help="triage 표의 태그 · 결정이 모두 확정됐는지 (미확정이면 exit 1)")
    ap.add_argument("--terms", metavar="FILE", help="용어집 위반 lint (HT-22, 위반이면 exit 1)")
    ap.add_argument("--glossary", metavar="PATH", help="용어집 경로 (기본: .claude/glossary.md → ~/.claude/glossary.md)")
    a = ap.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if a.version:
        print(VERSION_FILE.read_text(encoding="utf-8").strip() if VERSION_FILE.exists() else "unknown")
        return
    if a.coverage:
        c = coverage(a.coverage)
        if a.json or "error" in c:
            print(json.dumps(c, ensure_ascii=False, indent=2))
        else:
            print(f"커버리지 {c['coverage_pct']}%  (매핑 {c['mapping_rows']}행 · 케이스 {c['covered']} · 사유 {c['excused']} · 누락 {len(c['missing'])} · 깨진 id {len(c['broken_ids'])})  [{c['mode']}]")
            print(f"새 ID  ID 없음 {len(c['no_id'])} · 변경 유형 오류 {len(c['bad_kind'])}  (새 ID 칸: ID 또는 '없음(사유: …)' · 유형: {' · '.join(CHANGE_KINDS)})")
            for m in c["missing"]:
                print(f"  누락  {m}")
            for b in c["broken_ids"]:
                print(f"  깨짐  {b}")
            for m in c["no_id"]:
                print(f"  ID 없음  {m}")
            for m in c["bad_kind"]:
                print(f"  유형 오류  {m}")
        sys.exit(0 if coverage_ok(c) else 1)
    if a.triage_check:
        c = triage_check(a.triage_check)
        if a.json or c.get("error"):
            print(json.dumps(c, ensure_ascii=False, indent=2))
        else:
            n_open = len(c["undecided"]) + len(c["bad_tag"]) + len(c["need_note"])
            print(f"triage {c['rows']}행 · 미확정 {n_open}  (결정 미확정 {len(c['undecided'])} · 태그 미확정 {len(c['bad_tag'])} · 비고 누락 {len(c['need_note'])})")
            print("결정  " + " · ".join(f"{k} {v}" for k, v in c["decisions"].items()))
            print("태그  " + " · ".join(f"{k} {v}" for k, v in c["tags"].items()))
            for m in (c["undecided"] + c["bad_tag"] + c["need_note"])[:30]:
                print(f"  미확정  {m}")
        sys.exit(0 if triage_ok(c) else 1)
    if a.terms:
        g = find_glossary(a.root, a.glossary)
        if not g:
            print("용어집 없음 — 검사 생략 (.claude/glossary.md 또는 ~/.claude/glossary.md, templates/glossary.md 참고)")
            return
        hits = terms_check(Path(a.root) / a.terms, load_glossary(g))
        if a.json:
            print(json.dumps({"glossary": str(g), "hits": hits}, ensure_ascii=False, indent=2))
        else:
            print(f"용어 위반 {len(hits)}건  (용어집 {g})")
            for h in hits:
                print(f"  {a.terms}:{h['line']}  {h['found']} → {h['use']}  「{h['text'][:60]}」")
        sys.exit(1 if hits else 0)
    if a.file:
        fp = Path(a.root) / a.file
        text = read(fp)
        _, body = split_frontmatter(text)
        print(f"{fp.as_posix()}\t전체 {len(text.splitlines())}줄\t본문 {len(body.splitlines())}줄")
        return

    root = Path(a.root).resolve()
    found = discover(root, a.include_user, a.memory, a.extra)
    rows = [analyze(k, s, p, root) for k, s, p in found]
    conflicts = name_conflicts(rows)
    near_result = near(a.near, rows, root) if a.near else None
    shown = rows
    if a.changed_since:
        ch = changed_files(root, a.changed_since)
        shown = [r for r in rows if Path(r["abs"]) in ch]
    settings = settings_summary(root, a.include_user)

    if a.rules:
        g = find_glossary(root, a.glossary)
        items = rules_triage(shown, root, load_glossary(g), dup=a.dup_threshold)
        version = VERSION_FILE.read_text(encoding="utf-8").strip() if VERSION_FILE.exists() else "unknown"
        result = (json.dumps({"glossary": str(g) if g else None, "rules": items}, ensure_ascii=False, indent=2)
                  if a.json else triage_markdown(items, g, version, root))
        if a.out:
            Path(a.out).parent.mkdir(parents=True, exist_ok=True)
            Path(a.out).write_text(result, encoding="utf-8")
            print(f"wrote {a.out} ({len(items)} rules from {len({i['path'] for i in items})} files)")
        else:
            print(result)
        return

    if a.json:
        result = json.dumps({"rows": shown, "conflicts": conflicts, "settings": settings, "near": near_result}, ensure_ascii=False, indent=2)
    else:
        result = to_markdown(shown, settings, conflicts, near_result, a.changed_since)
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(result, encoding="utf-8")
        print(f"wrote {a.out} ({len(shown)} files)")
    else:
        print(result)


if __name__ == "__main__":
    main()
