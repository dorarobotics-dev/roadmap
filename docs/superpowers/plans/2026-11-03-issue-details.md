# Detailed Requirement Background in the Tracking Issues — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every one of the 145 `fm_sync` issues in dorarobotics-dev gets four hand-written sections (Summary, Use case / Why, Proposed expected behavior, Proposed API / Design) that the sync never overwrites.

**Architecture:** The sync owns only a block between `<!-- fm:begin -->` and `<!-- fm:end -->` at the end of each issue body; everything above it is a prose area edited on GitHub. A new `fm_sync.py prose` command fills empty prose areas from draft markdown files. The drafts are written by 14 research agents (one per requirement row), checked by a script and reviewed by 3 reviewer agents.

**Tech Stack:** Python 3.11, openpyxl, `gh` CLI (REST + GraphQL), pytest. Spec: `roadmap/docs/superpowers/specs/2026-11-03-issue-details-design.md`.

---

## Conventions for every task

- Code lives in `/home/demo/Public/github_dorarobotics_dev/roadmap/tools/` (git repo `roadmap`, branch `main`, remote `origin` = github.com/dorarobotics-dev/roadmap).
- Run tests from `tools/` as:
  `PYTHONPATH= /home/demo/Public/github_dimos/.venv-exp/bin/python -m pytest -q tests`
  (`PYTHONPATH=` is required: ROS humble injects a pytest plugin that breaks collection.) Call this `$PYTEST` below.
- Run the CLI as `/home/demo/Public/github_dimos/.venv-exp/bin/python fm_sync.py …` from `tools/`. Call this `$FM` below. `gh` is logged in as `bobdingAI`.
- Every commit message ends with a blank line and `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Never push to dora-rs, octos-org or dorarobotics. Only `roadmap` is pushed, and only in the tasks that say so.
- Scratch work goes in `S=/tmp/claude-1000/-home-demo-Public-github-dorarobotics-dev/169d017b-df0c-474e-9b34-1188be017329/scratchpad/details-work`; drafts in `$S/drafts/`.

## File structure

| File | Change | Responsibility |
|---|---|---|
| `tools/fmsync/render.py` | modify | Managed block (`BEGIN`/`END`, `## Tracking`), `split`, `compose`, `LayoutError` |
| `tools/fmsync/plan.py` | modify | Compare only the managed block; keep the prose on update; migrate legacy bodies |
| `tools/fmsync/prose.py` | create | Read draft files, decide write/skip per issue, write prose |
| `tools/fm_sync.py` | modify | `prose <drafts-dir> [--apply] [--only]` subcommand |
| `tools/tests/fakes.py` | modify | `draft_section()` helper for tests |
| `tools/tests/test_render.py`, `test_plan.py`, `test_cli.py` | modify | New layout tests |
| `tools/tests/test_prose.py` | create | `prose` module tests |
| `README.md` | modify | Body layout, prose editing, `prose` command |
| `$S/dump_row.py`, `$S/check_drafts.py` | create (scratchpad) | Inputs for research agents; draft checker |

---

### Task 1: Managed block, `split` and `compose` in render.py

**Files:**
- Modify: `tools/fmsync/render.py`
- Test: `tools/tests/test_render.py`

- [ ] **Step 1: Write the failing tests**

In `tools/tests/test_render.py`, replace the first assertion of `test_markers_round_trip`:

```python
def test_markers_round_trip():
    body = render.requirement_body(Q)
    assert body.endswith("<!-- fm:R13 -->\n" + render.END)
    assert render.find_marker(body) == "R13"
    assert render.find_marker(render.feature_body(F, Q.name)) == "13.02"
    assert render.find_marker("no marker here") is None
    assert render.find_marker(render.BEGIN + render.END) is None  # begin/end are not issue markers
```

Append:

```python
def test_bodies_are_managed_blocks():
    for block in (render.requirement_body(Q), render.feature_body(F, Q.name)):
        assert block.startswith(render.BEGIN + "\n## Tracking\n")
        assert block.endswith(render.END)
    assert "### 国家要求（必须完成）" in render.requirement_body(Q)


def test_split_and_compose():
    block = render.feature_body(F, Q.name)
    assert render.split(block) == ("", block)
    body = render.compose("## Summary\n\nText.\n\n", block)
    assert body == "## Summary\n\nText.\n\n" + block
    assert render.split(body) == ("## Summary\n\nText.", block)
    assert render.split(body.replace("\n", "\r\n")) == ("## Summary\n\nText.", block)
    assert render.split("legacy <!-- fm:13.02 -->") == (None, "legacy <!-- fm:13.02 -->")
    assert render.compose(None, block) == block
    assert render.compose("  \n", block) == block


@pytest.mark.parametrize("make, message", [
    (lambda b: b.replace(render.END, ""), "found 1 and 0"),
    (lambda b: b.replace(render.BEGIN, ""), "found 0 and 1"),
    (lambda b: b + "\n" + b, "found 2 and 2"),
    (lambda b: render.END + "\n" + b.replace(render.END, render.BEGIN, 1).replace(render.BEGIN, "", 1),
     "before"),
    (lambda b: b + "\nlate text", "text after"),
    (lambda b: "x <!-- fm:13.03 -->\n\n" + b, "marker in the prose"),
])
def test_split_refuses_a_broken_layout(make, message):
    with pytest.raises(render.LayoutError, match=message):
        render.split(make(render.feature_body(F, Q.name)), "dora#7 (13.02)")
```

Add `import pytest` at the top of the file. (The fourth case builds `END … BEGIN`: it moves `END` before the only `BEGIN`.)

- [ ] **Step 2: Run the tests to verify they fail**

Run: `$PYTEST tests/test_render.py`
Expected: FAIL — `AttributeError: module 'fmsync.render' has no attribute 'END'` (and `BEGIN`, `split`, `compose`, `LayoutError`).

- [ ] **Step 3: Implement**

In `tools/fmsync/render.py`, after `STATUS_LABEL = …` add:

```python
BEGIN = "<!-- fm:begin -->"
END = "<!-- fm:end -->"


class LayoutError(ValueError):
    """An issue body whose managed block cannot be found safely."""
```

After `normalize` add:

```python
def _block(parts) -> str:
    """The sync-owned part of an issue body."""
    return "\n".join([BEGIN, "## Tracking", "", *parts, END])


def split(body, where="issue"):
    """(prose, block). (None, body) for a body from before the managed block existed."""
    text = (body or "").replace("\r\n", "\n")
    nb, ne = text.count(BEGIN), text.count(END)
    if nb == 0 and ne == 0:
        return None, text
    if nb != 1 or ne != 1:
        raise LayoutError(f"{where}: expected one {BEGIN} and one {END}, found {nb} and {ne}; fix the body by hand")
    i, e = text.index(BEGIN), text.index(END)
    if e < i:
        raise LayoutError(f"{where}: {END} before {BEGIN}; fix the body by hand")
    j = e + len(END)
    if text[j:].strip():
        raise LayoutError(f"{where}: text after {END}; move it above {BEGIN}")
    prose = text[:i].rstrip()
    if MARKER_RE.search(prose):
        raise LayoutError(f"{where}: an fm marker in the prose area; remove it by hand")
    return prose, text[i:j]


def compose(prose, block) -> str:
    prose = (prose or "").strip()
    return f"{prose}\n\n{block}" if prose else block
```

Change `requirement_body` and `feature_body` to return blocks, with `###` sub-headings under `## Tracking`:

```python
def requirement_body(q) -> str:
    parts = [f"Requirement group **{q.row}** of the v1.3 embodied-middleware feature map.", "",
             "### Acceptance (summary)", "", q.acceptance_en or "—"]
    for heading, text in (("国家要求（必须完成）", q.national_zh), ("扩展功能及参数依据", q.expansion_zh),
                          ("量化指标要求", q.acceptance_zh)):
        if text:
            parts += ["", f"### {heading}", "", text]
    notes = ROW_ESTIMATE_NOTES.get(q.row)
    if notes:
        parts += ["", "### Effort (feasibility report)", ""] + [f"- {n}" for n in notes]
    parts += ["", "Features are the sub-issues of this issue. Source: "
              "`docs/requirements/2026-10-26-feature-map-by-repo.xlsx` in this repo.", "", marker(q.key)]
    return _block(parts)
```

```python
def feature_body(f, requirement_name: str) -> str:
    lead = (f"Feature **{f.id}** — one PR into `{f.repo}`." if f.kind == "feature"
            else f"Deliverable **{f.id}** (not a PR to a code repo).")
    rows = [("Requirement", f"{f.row} · {requirement_name} (parent issue)"),
            ("Package / location", f.location), ("Status", f.status),
            ("Existing basis", f.basis), ("Notes", f.notes)]
    table = ["| | |", "|---|---|"] + [f"| {k} | {_cell(v)} |" for k, v in rows]
    return _block([lead, "", *table, "", marker(f.key)])
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `$PYTEST tests/test_render.py`
Expected: all pass. Then run `$PYTEST` — `test_plan.py` and the others still pass (no behaviour has changed for them yet beyond body text; if a test compares a literal old body string, update the literal to the new block).

- [ ] **Step 5: Commit**

```bash
cd /home/demo/Public/github_dorarobotics_dev/roadmap
git add tools/fmsync/render.py tools/tests/test_render.py
git commit -m "feat(fmsync): sync-owned block in issue bodies, with split and compose

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Plan compares only the block and keeps the prose

**Files:**
- Modify: `tools/fmsync/plan.py:81-95` (`_issue_actions`)
- Test: `tools/tests/test_plan.py`

- [ ] **Step 1: Write the failing tests**

Append to `tools/tests/test_plan.py`:

```python
def _replace(st, key, body):
    old = st.issues[key]
    st.issues[key] = issue(key, old.repo, old.title, body, old.labels, old.number)
    return old


def test_prose_is_kept_when_the_block_changes():
    st = synced_state()
    old = st.issues["13.02"]
    _replace(st, "13.02", render.compose("## Summary\n\nHand text.", old.body.replace("| ref |", "| old |")))
    [up] = [a for a in plan.build(REQS, FEATS, st)[0] if a.op == "update_issue"]
    assert up.body == render.compose("## Summary\n\nHand text.", render.feature_body(F02, Q13.name))


def test_prose_only_edit_plans_nothing():
    st = synced_state()
    _replace(st, "13.02", render.compose("## Summary\n\nNew words.", st.issues["13.02"].body))
    assert plan.build(REQS, FEATS, st)[0] == []


def test_legacy_body_is_moved_to_the_new_layout():
    st = synced_state()
    _replace(st, "13.02", "Feature **13.02** — one PR into `dora`.\n\n| | |\n\n<!-- fm:13.02 -->")
    [up] = [a for a in plan.build(REQS, FEATS, st)[0] if a.op == "update_issue"]
    assert up.body == render.feature_body(F02, Q13.name)
    _replace(st, "13.02", up.body)
    assert plan.build(REQS, FEATS, st)[0] == []


def test_broken_layout_names_the_issue():
    st = synced_state()
    old = _replace(st, "13.02", st.issues["13.02"].body + "\nlate text")
    with pytest.raises(render.LayoutError, match=re.escape(f"dora#{old.number} (13.02)")):
        plan.build(REQS, FEATS, st)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `$PYTEST tests/test_plan.py`
Expected: FAIL — `test_prose_is_kept_when_the_block_changes` (body lacks the prose), `test_prose_only_edit_plans_nothing` (an update is planned), `test_broken_layout_names_the_issue` (no error raised). `test_legacy_body_is_moved_to_the_new_layout` may already pass.

- [ ] **Step 3: Implement**

In `tools/fmsync/plan.py`, replace the `else:` branch of `_issue_actions`:

```python
    else:
        if existing.repo != repo:
            raise PlanError(f"{key} is in {existing.repo}, the workbook says {repo}; move it by hand")
        prose, block = render.split(existing.body, f"{existing.repo}#{existing.number} ({key})")
        have = {name.lower() for name in existing.labels}
        missing = [name for name in labels if name.lower() not in have]
        if (render.normalize(existing.title) != render.normalize(title)
                or render.normalize(block) != render.normalize(body) or missing):
            out.append(Action("update_issue", key, repo=repo, title=title, body=render.compose(prose, body),
                              labels=tuple(sorted(set(existing.labels) | set(missing)))))
```

(`body` here is the rendered block; a legacy body has `prose is None`, so `compose` yields the block alone.)

- [ ] **Step 4: Run the tests to verify they pass**

Run: `$PYTEST`
Expected: all pass (61 existing + the new ones).

- [ ] **Step 5: Commit**

```bash
git add tools/fmsync/plan.py tools/tests/test_plan.py
git commit -m "feat(fmsync): compare only the managed block; keep hand-written prose

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: `prose` module — read drafts, decide, write

**Files:**
- Create: `tools/fmsync/prose.py`
- Modify: `tools/tests/fakes.py` (add `draft_section`)
- Test: `tools/tests/test_prose.py`

- [ ] **Step 1: Add the test helper**

Append to `tools/tests/fakes.py`:

```python
def draft_section(key, extra=""):
    """One `# ID` section of a draft file, with the four headings and a code fence holding `#` lines."""
    return (f"# {key}\n\n## Summary\n\nSummary of {key}.\n\n## Use case / Why\n\nA base stops.\n\n"
            "## Proposed expected behavior\n\nIt works.\n\n## Proposed API / Design\n\n"
            "```yaml\n# inputs\n## not a heading\n```\n" + (extra + "\n" if extra else "") + "\n")
```

- [ ] **Step 2: Write the failing tests**

Create `tools/tests/test_prose.py`:

```python
import pytest

from fakes import FakeGh, draft_section
from fmsync import plan, prose, render
from test_plan import F02, FEATS, Q13, REQS, issue, synced_state

KNOWN = {q.key for q in REQS} | {f.key for f in FEATS}


def write(tmp_path, text, name="13.md"):
    (tmp_path / name).write_text(text, encoding="utf-8")
    return tmp_path


def test_read_drafts_ignores_headings_in_code_fences(tmp_path):
    d = prose.read_drafts(write(tmp_path, draft_section("R13") + draft_section("13.02")), KNOWN)
    assert set(d) == {"R13", "13.02"}
    assert d["13.02"].startswith("## Summary\n\nSummary of 13.02.")
    assert "# inputs" in d["13.02"] and d["13.02"].endswith("```")


@pytest.mark.parametrize("text, message", [
    (draft_section("13.99"), "13.99 is not in the workbook"),
    (draft_section("13.02") + draft_section("13.02"), "13.02 also in 13.md"),
    (draft_section("13.02").replace("## Use case / Why", "## Why"), "headings"),
    (draft_section("13.02") + "\n## Extra\n", "headings"),
    (draft_section("13.02").replace("## Summary", "Lead.\n\n## Summary"), "must start with ## Summary"),
    (draft_section("13.02", "<!-- fm:end -->"), "fm marker text"),
    ("Intro.\n" + draft_section("13.02"), "before the first"),
    (draft_section("13.02") + "```\n", "unclosed"),
])
def test_read_drafts_refuses(tmp_path, text, message):
    with pytest.raises(prose.ProseError, match=message):
        prose.read_drafts(write(tmp_path, text), KNOWN)


def test_read_drafts_refuses_an_empty_directory(tmp_path):
    with pytest.raises(prose.ProseError, match="no .md draft files"):
        prose.read_drafts(tmp_path, KNOWN)


def test_read_drafts_refuses_an_id_in_two_files(tmp_path):
    write(tmp_path, draft_section("13.02"), "a.md")
    write(tmp_path, draft_section("13.02"), "b.md")
    with pytest.raises(prose.ProseError, match="13.02 also in a.md"):
        prose.read_drafts(tmp_path, KNOWN)


def test_build_writes_only_empty_prose_areas():
    st = synced_state()
    mine = st.issues["13.03"]
    st.issues["13.03"] = issue("13.03", "dora", mine.title, render.compose("## Summary\n\nMine.", mine.body),
                               mine.labels, mine.number)
    req = st.issues["R13"]
    st.issues["R13"] = issue("R13", "roadmap", req.title, "old <!-- fm:R13 -->", req.labels, req.number)
    drafts = {"RF": "## Summary\n\nA.", "R13": "x", "13.02": "## Summary\n\nB.", "13.03": "y"}
    acts = {a.key: a for a in prose.build(drafts, st)}
    assert acts["13.02"].op == "write"
    assert acts["13.02"].body == render.compose("## Summary\n\nB.", st.issues["13.02"].body)
    assert acts["RF"].op == "write"
    assert (acts["13.03"].op, acts["13.03"].reason) == ("skip", "already has prose")
    assert (acts["R13"].op, acts["R13"].reason) == ("skip", "old layout; run sync first")
    assert [a.key for a in prose.build(drafts, st, only={"13.02"})] == ["13.02"]


def test_build_skips_a_key_without_an_issue():
    [a] = prose.build({"13.02": "## Summary\n\nB."}, plan.State())
    assert (a.op, a.reason) == ("skip", "no issue yet; run sync first")


def test_execute_keeps_title_and_labels():
    g = FakeGh()
    s = g.create_issue("dora", "T", render.feature_body(F02, Q13.name), ("row:13", "bug"), "13.02")
    st = plan.State(issues={"13.02": s})
    prose.execute(g, st, prose.build({"13.02": "## Summary\n\nB."}, st), log=lambda m: None)
    new = g.issues[("dora", s.number)]
    assert new.title == "T" and new.labels == ("row:13", "bug")
    assert new.body == render.compose("## Summary\n\nB.", render.feature_body(F02, Q13.name))
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `$PYTEST tests/test_prose.py`
Expected: FAIL — `ImportError: cannot import name 'prose' from 'fmsync'`.

- [ ] **Step 4: Implement**

Create `tools/fmsync/prose.py`:

```python
"""Hand-written issue prose from draft files. Fills only empty prose areas; never rewrites prose."""
import pathlib
import re
from dataclasses import dataclass

from . import render

HEADINGS = ("Summary", "Use case / Why", "Proposed expected behavior", "Proposed API / Design")
ID_RE = re.compile(r"^# (\S+)\s*$")
H2_RE = re.compile(r"^## (.+?)\s*$")


class ProseError(ValueError):
    pass


@dataclass(frozen=True)
class ProseAction:
    op: str          # "write" or "skip"
    key: str
    reason: str = ""
    body: str = ""


def _is_fence(line) -> bool:
    return line.lstrip().startswith("```")


def _sections(path):
    """[(key, lines)] for the `# ID` sections of one file. Headings inside ``` fences do not count."""
    sections, fence = [], False
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if _is_fence(line):
            fence = not fence
        m = None if fence else ID_RE.match(line)
        if m:
            sections.append((m.group(1), []))
        elif sections:
            sections[-1][1].append(line)
        elif line.strip():
            raise ProseError(f"{path.name}:{n}: text before the first `# ID` heading")
    if fence:
        raise ProseError(f"{path.name}: unclosed ``` fence")
    return sections


def _headings(lines):
    out, fence = [], False
    for line in lines:
        if _is_fence(line):
            fence = not fence
        elif not fence:
            m = H2_RE.match(line)
            if m:
                out.append(m.group(1))
    return out


def read_drafts(directory, known) -> dict:
    """{key: prose} from every *.md in directory. Refuses anything that does not fit the layout."""
    files = sorted(pathlib.Path(directory).glob("*.md"))
    if not files:
        raise ProseError(f"{directory}: no .md draft files")
    drafts, where = {}, {}
    for path in files:
        for key, lines in _sections(path):
            loc = f"{path.name} # {key}"
            if key not in known:
                raise ProseError(f"{loc}: {key} is not in the workbook")
            if key in drafts:
                raise ProseError(f"{loc}: {key} also in {where[key]}")
            heads = _headings(lines)
            if heads != list(HEADINGS):
                raise ProseError(f"{loc}: headings {heads}, expected {list(HEADINGS)}")
            text = "\n".join(lines).strip()
            if not text.startswith("## Summary"):
                raise ProseError(f"{loc}: must start with ## Summary")
            if "<!-- fm" in text:
                raise ProseError(f"{loc}: contains fm marker text")
            drafts[key], where[key] = text, path.name
    return drafts


def build(drafts, state, only=None) -> list:
    out = []
    for key in sorted(drafts):
        if only and key not in only:
            continue
        s = state.issues.get(key)
        if s is None:
            out.append(ProseAction("skip", key, "no issue yet; run sync first"))
            continue
        prose, block = render.split(s.body, f"{s.repo}#{s.number} ({key})")
        if prose is None:
            out.append(ProseAction("skip", key, "old layout; run sync first"))
        elif prose.strip():
            out.append(ProseAction("skip", key, "already has prose"))
        else:
            out.append(ProseAction("write", key, s.url, render.compose(drafts[key], block)))
    return out


def execute(gh, state, actions, log=print) -> None:
    for a in actions:
        if a.op == "write":
            s = state.issues[a.key]
            gh.update_issue(s.repo, s.number, s.title, a.body, s.labels)
            log(f"wrote {a.key} {s.url}")
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `$PYTEST`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add tools/fmsync/prose.py tools/tests/fakes.py tools/tests/test_prose.py
git commit -m "feat(fmsync): prose module fills empty prose areas from draft files

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: `fm_sync.py prose` subcommand

**Files:**
- Modify: `tools/fm_sync.py`
- Test: `tools/tests/test_cli.py`

- [ ] **Step 1: Write the failing tests**

Append to `tools/tests/test_cli.py` (add `from fakes import FakeGh, draft_section` in place of the existing `from fakes import FakeGh`):

```python
def test_prose_dry_run_apply_and_skip(tmp_path):
    g = FakeGh()
    run(["setup", "--apply"], g)
    run(["sync", "--apply", "--only", "F"], g)
    (tmp_path / "F.md").write_text(draft_section("RF") + draft_section("F.01"), encoding="utf-8")
    code, out = run(["prose", str(tmp_path)], g)
    assert code == 0 and out[0].startswith("WARNING no draft for 143:")
    assert out[-2] == "prose: write 2, skip 0" and out[-1] == "dry run: nothing changed (add --apply)"
    assert all(s.body.startswith("<!-- fm:begin -->") for s in g.issues.values())
    assert run(["prose", str(tmp_path), "--apply"], g)[0] == 0
    rf = next(s for s in g.issues.values() if s.key == "RF")
    assert rf.body.startswith("## Summary\n\nSummary of RF.")
    assert run(["prose", str(tmp_path)], g)[1][-2] == "prose: write 0, skip 2"
    assert run(["sync", "--only", "F"], g)[1][-2] == ("plan: create_issue 0, update_issue 0, comment 0, "
                                                       "add_item 0, set_field 0, add_sub_issue 0")


def test_prose_refuses_bad_drafts_and_needs_a_directory(tmp_path):
    (tmp_path / "F.md").write_text(draft_section("F.99"), encoding="utf-8")
    code, out = run(["prose", str(tmp_path)], FakeGh())
    assert code == 1 and out[-1] == "ERROR F.md # F.99: F.99 is not in the workbook"
    code, out = run(["prose"], FakeGh())
    assert code == 2 and out[-1] == "prose needs a drafts directory"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `$PYTEST tests/test_cli.py`
Expected: FAIL — argparse `invalid choice: 'prose'` (SystemExit 2).

- [ ] **Step 3: Implement**

In `tools/fm_sync.py`:

1. Change the import line to `from fmsync import plan, workbook, writeback  # noqa: E402` → `from fmsync import plan, prose as pr, workbook, writeback  # noqa: E402`.
2. Replace the argument setup:

```python
    p.add_argument("command", choices=["setup", "sync", "writeback", "prose"])
    p.add_argument("drafts", nargs="?", help="prose: directory of draft *.md files")
    p.add_argument("--apply", action="store_true", help="change GitHub (or the workbook, for writeback)")
    p.add_argument("--only", default="",
                   help="comma-separated rows (F, 13, ...) or IDs (F.04, R13, ...); prose takes IDs only")
```

3. Right after `only = {x.strip() for x in a.only.split(",") if x.strip()} or None`, insert:

```python
    if a.command == "prose":
        return _prose(a, gh, state, reqs, feats, only, out)
```

4. Add before `main`:

```python
def _prose(a, gh, state, reqs, feats, only, out) -> int:
    if not a.drafts:
        out("prose needs a drafts directory")
        return 2
    known = {q.key for q in reqs} | {f.key for f in feats}
    try:
        drafts = pr.read_drafts(a.drafts, known)
        actions = pr.build(drafts, state, only)
    except ValueError as e:
        out(f"ERROR {e}")
        return 1
    missing = sorted(known - set(drafts))
    if missing and not only:
        out(f"WARNING no draft for {len(missing)}: {', '.join(missing)}")
    for x in actions:
        out(f"{x.op:6} {x.key:7} {x.reason}")
    counts = Counter(x.op for x in actions)
    out(f"prose: write {counts.get('write', 0)}, skip {counts.get('skip', 0)}")
    if not a.apply:
        out("dry run: nothing changed (add --apply)")
        return 0
    pr.execute(gh, state, actions, out)
    return 0
```

Note the `prose` check of `a.drafts` happens after `load_state`; with `FakeGh()` that is harmless. With the real `Gh` it costs one read of the issues, which is acceptable.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `$PYTEST`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add tools/fm_sync.py tools/tests/test_cli.py
git commit -m "feat(fm_sync): prose subcommand

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: README

**Files:**
- Modify: `README.md` (section `## Sync`)

- [ ] **Step 1: Edit**

In the command block add, after the `writeback` line:

```
    python fm_sync.py prose DIR        # dry run: fill empty prose areas from DIR/*.md
    python fm_sync.py prose DIR --apply [--only R13,13.02]
```

Replace the bullet starting `- **The workbook wins.**` with:

```markdown
- **Issue bodies have two parts.** The sync owns the block between
  `<!-- fm:begin -->` and `<!-- fm:end -->` at the end (the `## Tracking`
  table and the marker) and rewrites it from the workbook. Everything above
  `<!-- fm:begin -->` — Summary, Use case / Why, Proposed expected behavior,
  Proposed API / Design — is edited on GitHub and never touched by `sync`.
  Do not add text below `<!-- fm:end -->` or copy the markers into the prose;
  the sync stops with an error naming the issue.
- **Titles and labels follow the workbook.** Title edits made on GitHub are
  overwritten by the next `sync`.
- **`prose DIR`** posts first versions of the prose from draft files: each
  `DIR/*.md` holds `# <ID>` sections (`# R13`, `# 13.02`), each with exactly
  the four `##` headings above, in order. It writes only to issues whose prose
  area is empty, so it never overwrites hand edits.
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: issue body layout and the prose command

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Migrate the 145 issues to the new layout

- [ ] **Step 1: Dry run**

Run (from `tools/`): `$FM sync | tail -3`
Expected: `plan: create_issue 0, update_issue 145, comment 0, add_item 0, set_field 0, add_sub_issue 0` and `dry run: nothing changed (add --apply)`. Any other count: stop and investigate before applying.

- [ ] **Step 2: Apply**

Run: `$FM sync --apply | tail -2`
Expected: the last lines are `updated … https://github.com/dorarobotics-dev/…` lines; no traceback.

- [ ] **Step 3: Verify**

Run: `$FM sync | tail -2`
Expected: `plan: create_issue 0, update_issue 0, comment 0, add_item 0, set_field 0, add_sub_issue 0`.

Run: `gh issue view 1 -R dorarobotics-dev/roadmap --json body -q .body | head -3`
Expected: first line `<!-- fm:begin -->`, then `## Tracking`.

- [ ] **Step 4: Push roadmap**

```bash
cd /home/demo/Public/github_dorarobotics_dev/roadmap && git push origin main && git status -sb | head -1
```
Expected: `## main...origin/main`.

---

### Task 7: Research tooling (scratchpad)

**Files:**
- Create: `$S/dump_row.py`
- Create: `$S/check_drafts.py`

- [ ] **Step 1: Write `$S/dump_row.py`**

```python
"""Print one requirement row and its features as markdown: the input for a research agent."""
import pathlib
import sys

TOOLS = pathlib.Path("/home/demo/Public/github_dorarobotics_dev/roadmap/tools")
sys.path.insert(0, str(TOOLS))
import fm_sync  # noqa: E402
from fmsync import workbook  # noqa: E402
from fmsync.data import EXPERIMENT  # noqa: E402

row = sys.argv[1]
q = next(q for q in workbook.read_requirements(fm_sync.MAP, fm_sync.SOURCE) if q.row == row)
print(f"# R{q.row} {q.name}\n")
for heading, text in (("Acceptance (English summary)", q.acceptance_en), ("国家要求", q.national_zh),
                      ("扩展功能及参数依据", q.expansion_zh), ("量化指标要求", q.acceptance_zh)):
    print(f"## {heading}\n\n{text or '—'}\n")
print("## Features\n")
for f in workbook.read_features(fm_sync.MAP):
    if f.row == row:
        print(f"- **{f.id}** [{f.kind}] {f.title}\n  repo: {f.repo} · location: {f.location or '—'} · "
              f"status: {f.status} · basis: {f.basis or '—'} · notes: {f.notes or '—'}")
        if f.id in EXPERIMENT:
            status, delivered, missing = EXPERIMENT[f.id]
            print(f"  experiment ({status}): delivered {delivered}; not delivered: {missing}")
```

Run: `PYTHONPATH= /home/demo/Public/github_dimos/.venv-exp/bin/python $S/dump_row.py 13 | head -20`
Expected: `# R13 感知类算子 · Perception operators`, the four sections, then feature lines starting `- **13.01**`.

- [ ] **Step 2: Write `$S/check_drafts.py`**

```python
"""Check research drafts: structure (fmsync.prose), coverage per row, citations, length, excluded terms."""
import pathlib
import re
import subprocess
import sys

TOOLS = pathlib.Path("/home/demo/Public/github_dorarobotics_dev/roadmap/tools")
sys.path.insert(0, str(TOOLS))
import fm_sync  # noqa: E402
from fmsync import prose, workbook  # noqa: E402

BASE = pathlib.Path("/home/demo/Public/github_dorarobotics_dev")
TAG = "maintenance-freeze-2026-11-03"
DEFAULT_REF = {"roadmap": "HEAD", "dora": TAG, "DORA_NAV": TAG, "dora-moveit2": TAG,
               "dora-studio": TAG, "dora-hub": TAG, "octos": TAG}
CITE = re.compile(r"`(" + "|".join(sorted(map(re.escape, DEFAULT_REF), key=len, reverse=True))
                  + r")(?:@([\w./-]+))?:([^`\s]+)`")
EXCLUDED = re.compile(r"(?i)thingsboard|d1 ?max|jiuwen|cruzr|\bPOI\b")
PROPOSED = "*Proposed — confirm in the design review before implementing.*"


def exists(repo, ref, path) -> bool:
    path = re.sub(r"(:\d+(-\d+)?|#L\d+(-L?\d+)?)$", "", path).rstrip("/")
    r = subprocess.run(["git", "-C", str(BASE / repo), "cat-file", "-e", f"{ref}:{path}"],
                       capture_output=True)
    return r.returncode == 0


def main(directory) -> int:
    reqs = workbook.read_requirements(fm_sync.MAP, fm_sync.SOURCE)
    feats = workbook.read_features(fm_sync.MAP)
    known = {q.key for q in reqs} | {f.key for f in feats}
    try:
        drafts = prose.read_drafts(directory, known)
    except prose.ProseError as e:
        print(f"STRUCTURE {e}")
        return 1
    problems = []
    for path in sorted(pathlib.Path(directory).glob("*.md")):
        row = path.stem
        expected = {f"R{row}"} | {f.key for f in feats if f.row == row}
        got = {k for k, _ in prose._sections(path)}
        if got != expected:
            problems.append(f"{path.name}: missing {sorted(expected - got)}, extra {sorted(got - expected)}")
    for key, text in sorted(drafts.items()):
        words = len(text.split())
        limit = 900 if key.startswith("R") else 600
        if not 250 <= words <= limit:
            problems.append(f"{key}: {words} words (expected 250–{limit})")
        if not key.startswith("R") and PROPOSED not in text:
            problems.append(f"{key}: API / Design does not end with the 'Proposed — confirm …' line")
        for m in EXCLUDED.finditer(text):
            problems.append(f"{key}: excluded term {m.group(0)!r}")
        for repo, ref, path in CITE.findall(text):
            if not exists(repo, ref or DEFAULT_REF[repo], path):
                problems.append(f"{key}: cited path not found: {repo}@{ref or DEFAULT_REF[repo]}:{path}")
    for p in problems:
        print(p)
    print(f"{len(drafts)} sections, {len(problems)} problems")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
```

- [ ] **Step 3: Self-test the checker**

```bash
mkdir -p $S/selftest && cd $S/selftest && rm -f *.md
printf '# RF\n\n## Summary\n\nx\n\n## Use case / Why\n\n`dora:no/such/file.rs` ThingsBoard\n\n## Proposed expected behavior\n\nx\n\n## Proposed API / Design\n\nx\n' > F.md
PYTHONPATH= /home/demo/Public/github_dimos/.venv-exp/bin/python $S/check_drafts.py $S/selftest
```
Expected (exit 1): a `F.md: missing [...F.01...]` line, `RF: … words (expected 250–900)`, `RF: excluded term 'ThingsBoard'`, `RF: cited path not found: dora@maintenance-freeze-2026-11-03:no/such/file.rs`, and `1 sections, 4 problems`. Then `rm -r $S/selftest`.

---

### Task 8: Research — 14 agents in parallel

- [ ] **Step 1: Dispatch**

Dispatch 14 agents in one message (Agent tool, `general-purpose`), one per row in `F 13 14 15 16 17 18 19 20 21 22 23 24 25`. Each gets this brief with `{ROW}` replaced by its row:

````text
You are writing the first version of the hand-written part of GitHub issues for requirement row {ROW}
of the embodied-middleware v1.3 feature map. Readers are developers who will implement each feature.

Inputs (read them; do not guess):
1. Row data: run
   PYTHONPATH= /home/demo/Public/github_dimos/.venv-exp/bin/python \
     /tmp/claude-1000/-home-demo-Public-github-dorarobotics-dev/169d017b-df0c-474e-9b34-1188be017329/scratchpad/details-work/dump_row.py {ROW}
   It prints the requirement (Chinese text and English acceptance summary) and every feature and
   deliverable of the row: ID, kind, title, repo, location, status, basis, notes, and experiment results.
2. Earlier designs (read what is relevant to the row):
   /home/demo/Public/github_dorarobotics_dev/roadmap/docs/superpowers/specs/2026-10-20-operator-contract-and-data-processing-design.md
   /home/demo/Public/github_dorarobotics_dev/roadmap/docs/superpowers/specs/2026-10-20-coordinate-transformation-design.md
   /home/demo/Public/github_dorarobotics_dev/roadmap/docs/superpowers/specs/2026-11-02-contract-core-into-dora-design.md
   and their plans in roadmap/docs/superpowers/plans/; the experiment report:
   git -C /home/demo/Public/github_dorarobotics_dev/dora show exp/contract-core:docs/contract-core/feasibility.md
3. Code: local repos under /home/demo/Public/github_dorarobotics_dev/ (dora, DORA_NAV, dora-moveit2,
   dora-studio, dora-hub, octos). Read the code at each feature's location and what it builds on.
   Read with `git -C <repo> show <ref>:<path>` / `git -C <repo> ls-tree -r <ref>` where <ref> is
   maintenance-freeze-2026-11-03 (the base all work starts from) or exp/contract-core for experiment work.
   Read only. Do not edit, commit, build, or run dora up/start/stop/destroy.

Output: write exactly one file,
/tmp/claude-1000/-home-demo-Public-github-dorarobotics-dev/169d017b-df0c-474e-9b34-1188be017329/scratchpad/details-work/drafts/{ROW}.md
It holds one `# <ID>` section for the requirement (`# R{ROW}`) and one for EVERY feature and deliverable
the dump lists, nothing else. Each section has exactly these four `##` headings, in this order, and no
other `#`/`##` headings (use `###` or lists inside; `#` lines inside ``` code fences are fine):

## Summary
## Use case / Why
## Proposed expected behavior
## Proposed API / Design

Rules:
- English. 250–600 words per feature section; 250–900 for the requirement section.
- Summary: 1–3 sentences.
- Use case / Why: a real scenario in this stack — a mobile base navigating with DORA_NAV, an arm with
  dora-moveit2, a sensor pipeline into perception, an agent calling the robot through octos — naming who
  is affected, what workflow it unlocks and what is painful or impossible today. Not "we need function X".
- Proposed expected behavior: concrete, observable outcomes after the feature lands. Numbers ONLY from the
  requirement's acceptance text (量化指标要求 / acceptance summary); never invent thresholds.
- Proposed API / Design: the interface — function/class signatures, dataflow YAML with ports and message
  types, CLI commands or config keys; the ROS 2 equivalent it mirrors, where one exists; the existing code
  it builds on, cited as `repo:path` in backticks (e.g. `dora:libraries/core/src/descriptor/mod.rs`), or
  `repo@exp/contract-core:path` for code that exists only on the experiment branch. Every cited path must
  exist at that ref (default ref: maintenance-freeze-2026-11-03; for roadmap: HEAD). For a feature whose
  location is new code, say so and cite what it builds on. End the section with this exact line:
  *Proposed — confirm in the design review before implementing.*
- Experiment features (the dump shows an "experiment" line): say what exp/contract-core already delivers
  and what is left, consistent with that line.
- Deliverables (kind delivery: records, reports, docs): describe the artefact, who consumes it and what it
  must contain; under API / Design give the artefact's structure (files, fields, sections). Still end with
  the Proposed line.
- Requirement section (R{ROW}): Summary, Use case and Expected behavior from the requirement text and
  acceptance; API / Design is a map of how the row's features fit together and in what order to build them
  (no Proposed line needed).
- Do not write the text `<!-- fm` anywhere. Nothing outside the workbook's features: no POI,
  ThingsBoard, D1Max, jiuwensymbiosis, Cruzr.

Before finishing, run the checker and fix every problem it reports for your file:
mkdir -p /tmp/.../details-work/one-{ROW} && cp <your file> /tmp/.../details-work/one-{ROW}/ && \
PYTHONPATH= /home/demo/Public/github_dimos/.venv-exp/bin/python \
  /tmp/claude-1000/-home-demo-Public-github-dorarobotics-dev/169d017b-df0c-474e-9b34-1188be017329/scratchpad/details-work/check_drafts.py \
  /tmp/.../details-work/one-{ROW}
(use the full scratchpad path in place of /tmp/...). It must print `0 problems`. Remove the one-{ROW} dir.

Report: number of sections, word-count range, any feature where the code or requirement did not support
a concrete API (say what you assumed), and the 3 claims you are least sure of.
````

- [ ] **Step 2: Collect**

When all 14 report, run:
`PYTHONPATH= /home/demo/Public/github_dimos/.venv-exp/bin/python $S/check_drafts.py $S/drafts`
Expected: `145 sections, 0 problems`. For a row with problems, send its agent the checker output (SendMessage) and re-run until clean.

---

### Task 9: Independent review

- [ ] **Step 1: Dispatch 3 reviewers in one message**

Groups: `F 13 14 15 16`, `17 18 19 20 21`, `22 23 24 25`. Each reviewer (general-purpose) gets:

````text
Review the draft issue text in
/tmp/claude-1000/-home-demo-Public-github-dorarobotics-dev/169d017b-df0c-474e-9b34-1188be017329/scratchpad/details-work/drafts/{ROW}.md
for rows {ROWS}. Do not edit the drafts. For each row, get the facts with
PYTHONPATH= /home/demo/Public/github_dimos/.venv-exp/bin/python \
  /tmp/claude-1000/-home-demo-Public-github-dorarobotics-dev/169d017b-df0c-474e-9b34-1188be017329/scratchpad/details-work/dump_row.py <row>
and check claims against the code in /home/demo/Public/github_dorarobotics_dev/<repo> at
maintenance-freeze-2026-11-03 (or exp/contract-core where cited) using git show / git ls-tree / git grep.
Find, per section:
1. Invented APIs: a function, class, CLI command, config key or message type described as EXISTING that
   does not exist (proposed new ones are fine if labelled as proposed).
2. Invented numbers: any threshold or count not in the requirement's acceptance text.
3. Wrong ROS 2 equivalents.
4. A use case or expected behavior that does not fit the feature's title and location.
5. Experiment sections that contradict the dump's experiment line.
6. Vague text ("handle errors appropriately", "improve performance") where a concrete statement is needed.
Report a list: `<ID> | <problem> | <evidence: path/line or quote> | <suggested fix>`. Only report what you
verified. If a row is clean say so.
````

- [ ] **Step 2: Fix**

For each finding, send it to the row's research agent (SendMessage) to fix in its draft. After all fixes, run `check_drafts.py $S/drafts` again — expected `145 sections, 0 problems`. Re-send a reviewer only the sections that changed, if a fix was substantial (new API or behavior text).

---

### Task 10: Post the prose and verify

- [ ] **Step 1: Dry run**

Run (from `tools/`): `$FM prose $S/drafts | tail -2`
Expected: `prose: write 145, skip 0` and the dry-run line, with no `WARNING no draft` line at the top (check `$FM prose $S/drafts | head -1`).

- [ ] **Step 2: Apply**

Run: `$FM prose $S/drafts --apply | tail -1`
Expected: a `wrote … https://github.com/dorarobotics-dev/…` line.

- [ ] **Step 3: Verify**

Run: `$FM sync | tail -2` → `plan: create_issue 0, update_issue 0, comment 0, add_item 0, set_field 0, add_sub_issue 0`.
Run: `$FM prose $S/drafts | tail -2` → `prose: write 0, skip 145`.
Open on GitHub and read: one requirement (`roadmap` R13), one feature (`dora` 16.03), one experiment feature (`dora` 13.02), one deliverable (a `roadmap` delivery issue). Each shows the four sections above `## Tracking`, renders cleanly (code fences, tables), and the Tracking table is unchanged.

---

### Task 11: Handoff note

- [ ] **Step 1:** In `/home/demo/Public/github_dorarobotics_dev/.claude-handoff/HANDOFF.md`, under the Tracking bullet, add one line: issue bodies now have a hand-edited prose area above `<!-- fm:begin -->`; first versions were posted 2026-11-03 with `fm_sync.py prose`; the drafts are not kept in the repo.
- [ ] **Step 2:** Push roadmap if anything is unpushed: `cd /home/demo/Public/github_dorarobotics_dev/roadmap && git push origin main`.
