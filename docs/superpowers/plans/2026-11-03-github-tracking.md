# GitHub Tracking for the v1.3 Feature Map — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every requirement group and PR-sized feature of the v1.3 feature map is a GitHub issue in the org `dorarobotics-dev`, linked as sub-issues and tracked in one org project, kept in step with the workbook by a re-runnable script.

**Architecture:** A new repo `dorarobotics-dev/roadmap` holds the workbooks, the superpowers docs and a Python package `tools/fmsync`. The package reads the workbook into records (`workbook.py`), compares them with GitHub state found by hidden markers (`plan.py`, pure), and applies the resulting actions through `gh api` (`github.py`, `apply.py`). Six forks of the upstream code repos receive the feature issues; the requirement and delivery issues live in `roadmap`.

**Tech Stack:** Python 3.11 (`~/Public/github_dimos/.venv-exp`, has openpyxl 3.1.5 and pytest 9.2), `gh` 2.4 (`gh api` REST + GraphQL; no `gh project` command), git, LibreOffice (`soffice`) for workbook recalculation.

**Spec:** `docs/superpowers/specs/2026-11-03-github-tracking-design.md`.

---

## Ground rules for every task

- Paths: `W=/home/demo/Public/github_dorarobotics_dev` (not a git repo), `R=$W/roadmap` (the new tracking repo, created in Task 1), `VENV=/home/demo/Public/github_dimos/.venv-exp`.
- GitHub account: `gh auth status` must show `bobdingAI` (admin of `dorarobotics-dev`). If it shows another account, stop and report.
- Only `dorarobotics-dev` is ever written to. Never push or write to `dora-rs`, `octos-org` or `dorarobotics`. In the code-repo copies under `$W`, only the new `dev` remote may have a push URL.
- Run pytest as `cd $R/tools && PYTHONPATH= $VENV/bin/python -m pytest tests -q` (ROS on this machine injects a pytest plugin otherwise).
- Workbook recalculation after any openpyxl save: `$VENV/bin/python /home/demo/.claude/skills/synced/d6864d6a-bc5f-4c46-b8d4-c94b7fcf1b33_af86715d-ddd4-4f91-a212-c09a3aa18791/xlsx/scripts/recalc.py <file>`; it must report `"status": "success"` and `"total_errors": 0`.
- Commits in `$R` end with:
  ```
  Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
  ```
- Tasks 10–14 change GitHub. Each prints a dry run first; the controller shows it to the user before the `--apply` step if anything differs from the counts given in the task.

## Decisions made while planning (not in the spec)

1. **Views by API.** GitHub's GraphQL API now has `createProjectV2View` and `updateProjectV2View` (name, layout, filter). So all 17 views are created by `fm_sync.py setup`. Group-by cannot be set through the API: two table views (Overview by Row, By repo by Target repo) get their grouping by hand (Task 14). Task 1 updates spec §3 accordingly.
2. **Experiment status.** Items the experiment delivered fully (F.02, 13.02, 13.17) start as "Done (experiment)"; items delivered in part (F.01, F.03, F.04, F.06, F.07, 13.01) start as "In progress". Every one of them gets a comment quoting the feasibility report's Delivered / Not delivered columns.
3. **Feature body links its requirement by text.** The parent link is the sub-issue relation itself (shown by GitHub on both issues); the body names the requirement, because its URL does not exist when the body is first rendered.
4. **Added features (spec §2).** Eight rows are added to the workbook, all in row F:

   | ID | Sheet | Feature | Source |
   |---|---|---|---|
   | F.13 | dora | Rebase `exp/contract-core` onto `maintenance-freeze-2026-11-03` | handoff open item 1 |
   | F.14 | octos | Plan F.08–F.10 against upstream main, not the diverged local clone | handoff open item 2 |
   | F.15 | dora | Enforce a type's required metadata keys | feasibility "did not fit" 3 |
   | F.16 | dora | Typed header send API that refuses shadowing | did not fit 4 |
   | F.17 | dora | Daemon injects the frames files from the dataflow `frames:` key | did not fit 6 and 7 |
   | F.18 | dora | Unparameterised type side means its declared default | did not fit 19 |
   | F.19 | dora | `child_frame` field on ports | did not fit 20 |
   | F.20 | dora | Expose `Node.id` in Python | did not fit 21 |

   Counts after the additions: dora 60, DORA_NAV 30, dora-moveit2 12, dora-studio 4, octos 4, dora-hub 5, delivery 16 = **131 features**, plus **14 requirements** = **145 issues**.
5. **Estimates.** The `Estimate (days)` field is set only where the feasibility report gives one figure for one ID, and on R13 (40) and R16 (21). Figures shared by several IDs go into the requirement body as text, never split.
6. **Project visibility.** The project is created with GitHub's default (private to the org). Making it public is a one-click choice left to the user.

## File structure

All under `$R` (`~/Public/github_dorarobotics_dev/roadmap`):

| File | Responsibility |
|---|---|
| `README.md` | What the repo is; how to run the sync |
| `docs/requirements/*.xlsx`, `docs/superpowers/**` | Moved here from `$W/docs` |
| `tools/workbook_edits.py` | One-off: F.05 correction, F.03 note, F.13–F.20 (Task 2) |
| `tools/fm_sync.py` | CLI: `setup`, `sync`, `writeback`; dry run unless `--apply` |
| `tools/fmsync/__init__.py` | Empty package marker |
| `tools/fmsync/model.py` | `ROWS`, `SHEET_REPO`, `Requirement`, `Feature` |
| `tools/fmsync/workbook.py` | Read and check the two workbooks |
| `tools/fmsync/data.py` | Org, repos, project, fields, labels, views, experiment status, estimates |
| `tools/fmsync/render.py` | Titles, bodies, labels, markers, experiment comments |
| `tools/fmsync/plan.py` | `IssueState`, `State`, `Action`, `build()` — pure |
| `tools/fmsync/github.py` | `Gh`: thin wrappers over `gh api`, owner guard, rate-limit retry |
| `tools/fmsync/apply.py` | `setup()`, `load_state()`, `execute()` |
| `tools/fmsync/writeback.py` | Write issue URLs into the workbook's `Issue / PR` column |
| `tools/tests/conftest.py` | Puts `tools/` on `sys.path` |
| `tools/tests/fakes.py` | `FakeGh`, an in-memory stand-in for `Gh` |
| `tools/tests/test_*.py` | One test file per module, plus the CLI |

---

### Task 1: Create the local `roadmap` repo and move the docs into it

**Files:**
- Create: `$R/README.md`, `$R/.gitignore`
- Move: `$W/docs` → `$R/docs`
- Modify: `$R/docs/superpowers/specs/2026-11-03-github-tracking-design.md` (§3 views)

- [ ] **Step 1: Create the repo and move the docs**

```bash
W=/home/demo/Public/github_dorarobotics_dev; R=$W/roadmap
mkdir "$R" && git -C "$R" init -q -b main
mv "$W/docs" "$R/docs"
ls "$R/docs/requirements" "$R/docs/superpowers"
```
Expected: three `.xlsx` files; `handoffs plans specs`.

- [ ] **Step 2: Write `.gitignore`**

```
__pycache__/
.pytest_cache/
*.pyc
~$*.xlsx
.~lock.*#
```

- [ ] **Step 3: Write `README.md`**

```markdown
# roadmap

Requirements and feature tracking for the v1.3 embodied-middleware work on dora
(`dorarobotics-dev`). The workbook is the source of truth; issues and the org
project "Embodied middleware v1.3" are generated from it.

| Path | What |
|---|---|
| `docs/requirements/具身智能本体中间件_扩展功能_v1.3_withoutbudget.xlsx` | Original requirement (rows 13–25, functions and delivery sheets) |
| `docs/requirements/2026-10-26-feature-map-by-repo.xlsx` | Feature map: one sheet per target repo, one row per PR. **Source of truth.** |
| `docs/requirements/2026-10-26-feature-map-v1.3.xlsx` | Feature map by workbook row (earlier view) |
| `docs/superpowers/` | Specs, plans and handoffs |
| `tools/fm_sync.py` | Sync script |

## Sync

    cd tools
    python fm_sync.py setup            # dry run: labels, project, fields, views
    python fm_sync.py setup --apply
    python fm_sync.py sync             # dry run: issues, project items, fields, sub-issues
    python fm_sync.py sync --apply [--only F,13.02]
    python fm_sync.py writeback --apply  # issue URLs into the workbook's Issue / PR column

Edit the workbook, then run `sync`. The script never deletes or closes issues and
sets Status only when an issue first enters the project. Requires `gh` logged in
with write access to `dorarobotics-dev`, and Python with openpyxl.

## Acceptance

The general acceptance rule (统一验收要求) is in the `delivery` sheet of the v1.3
workbook; each requirement issue quotes its own row's criteria.
```

- [ ] **Step 4: Update spec §3 (views are created by the API)**

In `$R/docs/superpowers/specs/2026-11-03-github-tracking-design.md`, replace the line starting `- Views (made by hand in the UI` and the line after it with:

```markdown
- Views, created by `fm_sync.py setup` through `createProjectV2View`/`updateProjectV2View` (name, layout,
  filter): Overview (table), 14 per-row boards (filter on Row; board columns default to Status), By repo
  (table), Delivery (table, filter Kind = delivery or requirement). Group-by cannot be set through the API:
  Overview (group by Row) and By repo (group by Target repo; "Repo" is a reserved field name) are grouped by hand once.
- Items the experiment delivered in part start as "In progress" (fully delivered: "Done (experiment)").
```

Also in §4 "Bootstrap", replace `create the project and its fields (the script can do the labels, project and fields;` with `create the project, its fields and views (the script does labels, project, fields and views;`.

- [ ] **Step 5: Commit**

```bash
cd $R && git add -A && git commit -q -m "docs: requirements workbooks and superpowers docs for v1.3 tracking

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" && git log --oneline -1
```

---

### Task 2: Apply the workbook corrections and additions

**Files:**
- Create: `$R/tools/workbook_edits.py`
- Modify: `$R/docs/requirements/2026-10-26-feature-map-by-repo.xlsx`

- [ ] **Step 1: Write `tools/workbook_edits.py`**

```python
#!/usr/bin/env python3
"""One-off edits to the feature map decided on 2026-11-03 (spec §2, plan decision 4).

Safe to run twice: corrections compare before writing, and rows are appended only
when their ID is not already present.
"""
import pathlib
import sys

import openpyxl

MAP = pathlib.Path(__file__).resolve().parents[1] / "docs/requirements/2026-10-26-feature-map-by-repo.xlsx"
FOUNDATION = "基础 · Foundation"
F03_NOTE = "Frame, rate and max-age remain (feasibility report, F.03)."

# sheet, ID, feature, package / location, status, existing basis, notes
ADDED = [
    ("dora", "F.13", "Rebase exp/contract-core onto maintenance-freeze-2026-11-03",
     "whole repo (branch exp/contract-core)", "built, to move",
     "26 experiment commits on 1016eab0a; the freeze tag is 107 commits newer and touches 18 files (~1.9k lines) in the contract areas",
     "Open item 1 of the 2026-11-03 handoff"),
    ("octos", "F.14", "Plan the octos work (F.08–F.10) against upstream main, not the diverged local clone",
     "crates/octos-dora-mcp", "basis exists",
     "The fork starts at upstream main 19ca7995; the local clone diverged on 2026-04-24 with 267 commits of its own",
     "Open item 2 of the 2026-11-03 handoff"),
    ("dora", "F.15", "Enforce a type's required metadata keys in dora validate (optionally on send in debug builds)",
     "libraries/core types, binaries/cli validate.rs", "new",
     "TypeDef.metadata in the std type files is parsed but read nowhere",
     "feasibility.md, did not fit item 3"),
    ("dora", "F.16", "Typed header send API (send_output_with_header) in Rust, Python and C that writes the header keys last and refuses shadowing",
     "apis/rust/node, apis/python/node, apis/c/node", "basis exists",
     "Header::write and dora.header exist; dora metadata is an open map the node owns",
     "feasibility.md, did not fit item 4"),
    ("dora", "F.17", "Daemon injects the frame dictionary and extrinsics paths from the dataflow frames: key, replacing DORA_FRAMES/DORA_EXTRINSICS and the validator's launch-dir mirror",
     "binaries/daemon spawn, libraries/core", "new",
     "Node manifests refuse DORA_* env (ENV_DENY_PREFIX); the validator mirrors the daemon's working-directory rule",
     "feasibility.md, did not fit items 6 and 7"),
    ("dora", "F.18", "Type check treats an unparameterised side as its declared default (or warns), e.g. PointCloud = PointCloud[fields=xyz]",
     "libraries/core/src/types.rs", "basis exists",
     "params_agree treats an empty side as a wildcard",
     "feasibility.md, did not fit item 19"),
    ("dora", "F.19", "child_frame field on ports, so dora validate checks both sides of a pose's dynamic edge and the runtime can be as strict",
     "libraries/message descriptor, libraries/core frames_check.rs", "new",
     "output_frames/input_frames exist; no descriptor field declares a port's child_frame",
     "feasibility.md, did not fit item 20"),
    ("dora", "F.20", "Expose Node.id in the Python node API",
     "apis/python/node/src/lib.rs", "basis exists",
     "Rust Node::id() exists but is not a #[pymethods] method; dora sets no DORA_NODE_ID",
     "feasibility.md, did not fit item 21"),
]


def row_of(ws, fid):
    for row in ws.iter_rows(min_row=2):
        if row[0].value == fid:
            return row
    raise SystemExit(f"{ws.title}: {fid} not found")


def main(path=MAP):
    wb = openpyxl.load_workbook(path)
    changed = []

    f05 = row_of(wb["dora"], "F.05")
    if f05[5].value != "basis exists":
        f05[5].value = "basis exists"
        f05[6].value = ("dora master has action and service patterns (goal_id, request_id); "
                        "the client-API helpers still need upstream design discussion")
        changed.append("F.05 status")

    f03 = row_of(wb["dora"], "F.03")
    notes = f03[9].value or ""
    if F03_NOTE not in notes:
        f03[9].value = (notes + " " + F03_NOTE).strip()
        changed.append("F.03 notes")

    for sheet, fid, feature, location, status, basis, note in ADDED:
        ws = wb[sheet]
        if any(r[0].value == fid for r in ws.iter_rows(min_row=2)):
            continue
        ws.append([fid, "F", FOUNDATION, feature, location, status, basis, None, None, note])
        changed.append(fid)

    if changed:
        wb.save(path)
    print("changed:", ", ".join(changed) or "nothing")


if __name__ == "__main__":
    main(*(sys.argv[1:2]))
```

- [ ] **Step 2: Run it, then run it again**

```bash
cd $R/tools && $VENV/bin/python workbook_edits.py && $VENV/bin/python workbook_edits.py
```
Expected: first `changed: F.05 status, F.03 notes, F.13, F.14, F.15, F.16, F.17, F.18, F.19, F.20`; second `changed: nothing`.

- [ ] **Step 3: Recalculate and check counts**

```bash
$VENV/bin/python /home/demo/.claude/skills/synced/d6864d6a-bc5f-4c46-b8d4-c94b7fcf1b33_af86715d-ddd4-4f91-a212-c09a3aa18791/xlsx/scripts/recalc.py $R/docs/requirements/2026-10-26-feature-map-by-repo.xlsx
$VENV/bin/python -c "
import openpyxl
wb=openpyxl.load_workbook('$R/docs/requirements/2026-10-26-feature-map-by-repo.xlsx',data_only=True)
print([(r[0],r[3]) for r in wb['Summary'].iter_rows(min_row=2,values_only=True)])"
```
Expected: recalc `success`, 0 errors; Summary features dora 60, DORA_NAV 30, dora-moveit2 12, dora-studio 4, octos 4, dora-hub 5, delivery 16, Total 131.

- [ ] **Step 4: Commit**

```bash
cd $R && git add tools/workbook_edits.py docs/requirements/2026-10-26-feature-map-by-repo.xlsx && git commit -q -m "feat(workbook): F.05 correction, F.03 note, F.13-F.20 from the contract-core experiment

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Records and workbook reader

**Files:**
- Create: `$R/tools/fmsync/__init__.py` (empty), `$R/tools/fmsync/model.py`, `$R/tools/fmsync/workbook.py`
- Create: `$R/tools/tests/conftest.py`, `$R/tools/tests/test_workbook.py`

- [ ] **Step 1: Write `tools/tests/conftest.py`**

```python
import pathlib
import sys

TOOLS = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
REQ = TOOLS.parent / "docs" / "requirements"
MAP = REQ / "2026-10-26-feature-map-by-repo.xlsx"
SOURCE = REQ / "具身智能本体中间件_扩展功能_v1.3_withoutbudget.xlsx"
```

- [ ] **Step 2: Write the failing tests `tools/tests/test_workbook.py`**

```python
import shutil
from collections import Counter

import openpyxl
import pytest

from conftest import MAP, SOURCE
from fmsync import workbook
from fmsync.model import ROWS


def test_features_per_repo():
    feats = workbook.read_features(MAP)
    assert Counter(f.repo for f in feats) == {
        "dora": 60, "DORA_NAV": 30, "dora-moveit2": 12, "dora-studio": 4,
        "octos": 4, "dora-hub": 5, "roadmap": 16}
    assert len({f.id for f in feats}) == 131


def test_feature_fields():
    f = {x.id: x for x in workbook.read_features(MAP)}
    assert f["F.04"].repo == "dora" and f["F.04"].row == "F" and f["F.04"].kind == "feature"
    assert f["F.04"].status == "built, to move"
    assert f["F.05"].status == "basis exists"
    assert f["13.02"].row == "13"
    assert f["F.12"].kind == "delivery" and f["F.12"].repo == "roadmap"
    assert f["F.20"].title == "Expose Node.id in the Python node API"


def test_requirements():
    reqs = workbook.read_requirements(MAP, SOURCE)
    assert [q.row for q in reqs] == list(ROWS)
    q = {x.row: x for x in reqs}
    assert q["13"].name == "感知类算子 · Perception operators"
    assert q["13"].national_zh.startswith("覆盖多模态传感器融合")
    assert q["13"].expansion_zh.startswith("在既有导航与操作算子集的基础上扩展感知类算子")
    assert q["13"].acceptance_zh.startswith("融合算子接入不少于两类传感器")
    assert q["13"].acceptance_en.startswith("Fusion:")
    assert q["F"].national_zh == "" and q["F"].acceptance_zh == ""
    assert q["F"].key == "RF" and q["25"].key == "R25"


def _doctored(tmp_path, sheet, cell, value):
    path = tmp_path / "map.xlsx"
    shutil.copy(MAP, path)
    wb = openpyxl.load_workbook(path)
    wb[sheet][cell] = value
    wb.save(path)
    return path


@pytest.mark.parametrize("sheet,cell,value,message", [
    ("dora", "A3", "F.01", "duplicate ID F.01"),
    ("dora", "B2", "99", "unknown row 99"),
    ("dora", "F2", "maybe", "unknown status 'maybe'"),
    ("dora", "D2", None, "empty feature"),
    ("dora", "A2", "13.01", "13.01 is not in row F"),
    ("octos", "A1", "Id", "unexpected header"),
])
def test_bad_workbook_is_refused(tmp_path, sheet, cell, value, message):
    with pytest.raises(workbook.WorkbookError, match=message):
        workbook.read_features(_doctored(tmp_path, sheet, cell, value))
```

- [ ] **Step 3: Run them to verify they fail**

Run: `cd $R/tools && PYTHONPATH= $VENV/bin/python -m pytest tests/test_workbook.py -q`
Expected: collection error, `ModuleNotFoundError: No module named 'fmsync'`.

- [ ] **Step 4: Write `tools/fmsync/__init__.py` (empty) and `tools/fmsync/model.py`**

```python
"""Records read from the feature-map workbooks."""
from dataclasses import dataclass

ROWS = ("F", "13", "14", "15", "16", "17", "18", "19", "20", "21", "22", "23", "24", "25")

# workbook sheet -> GitHub repo in the org
SHEET_REPO = {
    "dora": "dora", "DORA_NAV": "DORA_NAV", "dora-moveit2": "dora-moveit2",
    "dora-studio": "dora-studio", "octos": "octos", "dora-hub": "dora-hub",
    "delivery": "roadmap",
}


@dataclass(frozen=True)
class Requirement:
    row: str
    name: str            # "感知类算子 · Perception operators"
    acceptance_en: str   # Rows sheet, condensed English
    national_zh: str     # v1.3 functions sheet: 国家要求 ("" for F)
    expansion_zh: str    # v1.3 functions sheet: 扩展功能及参数依据
    acceptance_zh: str   # v1.3 delivery sheet: 量化指标要求

    @property
    def key(self) -> str:
        return f"R{self.row}"


@dataclass(frozen=True)
class Feature:
    id: str
    row: str
    repo: str
    kind: str            # "feature" or "delivery"
    title: str
    location: str
    status: str          # "new", "basis exists", "built, to move"
    basis: str
    owner: str
    issue: str
    notes: str

    @property
    def key(self) -> str:
        return self.id
```

- [ ] **Step 5: Write `tools/fmsync/workbook.py`**

```python
"""Read and check the feature map and the original v1.3 requirement workbook."""
import openpyxl

from .model import ROWS, SHEET_REPO, Feature, Requirement

HEADER = ("ID", "Row", "Requirement", "Feature (one PR)", "Package / location", "Status",
          "Existing basis", "Owner", "Issue / PR", "Notes")
STATUSES = ("new", "basis exists", "built, to move")


class WorkbookError(ValueError):
    pass


def _s(value) -> str:
    return "" if value is None else str(value).strip()


def _row(value) -> str:
    s = _s(value)
    return s[:-2] if s.endswith(".0") else s


def read_features(path) -> list[Feature]:
    wb = openpyxl.load_workbook(path, read_only=True)
    out, seen = [], set()
    for sheet, repo in SHEET_REPO.items():
        rows = list(wb[sheet].iter_rows(values_only=True))
        header = tuple(_s(c) for c in rows[0][:len(HEADER)])
        if header != HEADER:
            raise WorkbookError(f"{sheet}: unexpected header {header}")
        for n, r in enumerate(rows[1:], start=2):
            if not any(c is not None for c in r):
                continue
            fid, row, title, status = _s(r[0]), _row(r[1]), _s(r[3]), _s(r[5])
            where = f"{sheet}!row {n}"
            if not fid:
                raise WorkbookError(f"{where}: empty ID")
            if fid in seen:
                raise WorkbookError(f"{where}: duplicate ID {fid}")
            if row not in ROWS:
                raise WorkbookError(f"{where}: unknown row {row}")
            if not fid.startswith(row + "."):
                raise WorkbookError(f"{where}: {fid} is not in row {row}")
            if not title:
                raise WorkbookError(f"{where}: empty feature")
            if status not in STATUSES:
                raise WorkbookError(f"{where}: unknown status {status!r}")
            seen.add(fid)
            out.append(Feature(fid, row, repo, "delivery" if sheet == "delivery" else "feature",
                               title, _s(r[4]), status, _s(r[6]), _s(r[7]), _s(r[8]), _s(r[9])))
    return out


def read_requirements(map_path, source_path) -> list[Requirement]:
    rows = list(openpyxl.load_workbook(map_path, read_only=True)["Rows"].iter_rows(values_only=True))[1:]
    src = openpyxl.load_workbook(source_path, read_only=True)
    functions = {}
    for r in list(src["functions"].iter_rows(values_only=True))[1:]:
        if r[0] is not None:
            functions[_row(r[0])] = (_s(r[6]), _s(r[7]))
    delivery = {}
    for r in list(src["delivery"].iter_rows(values_only=True))[1:]:
        head = _s(r[0]).split(" ", 1)[0]
        if head in ROWS:
            delivery[head] = _s(r[2])
    out = []
    for r in rows:
        if r[0] is None:
            continue
        row = _row(r[0])
        national, expansion = functions.get(row, ("", ""))
        out.append(Requirement(row, _s(r[1]), _s(r[2]), national, expansion, delivery.get(row, "")))
    if [q.row for q in out] != list(ROWS):
        raise WorkbookError(f"Rows sheet must list {', '.join(ROWS)} in order, got {[q.row for q in out]}")
    return out
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `cd $R/tools && PYTHONPATH= $VENV/bin/python -m pytest tests/test_workbook.py -q`
Expected: `9 passed`.

- [ ] **Step 7: Commit**

```bash
cd $R && git add tools && git commit -q -m "feat(fmsync): read and check the feature-map workbooks

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Static data and rendering

**Files:**
- Create: `$R/tools/fmsync/data.py`, `$R/tools/fmsync/render.py`
- Create: `$R/tools/tests/test_render.py`

- [ ] **Step 1: Write `tools/fmsync/data.py`**

```python
"""Fixed facts: the org, its repos, the project's fields and views, experiment status, estimates."""
ORG = "dorarobotics-dev"
REPOS = ("roadmap", "dora", "DORA_NAV", "dora-moveit2", "dora-studio", "octos", "dora-hub")
PROJECT_TITLE = "Embodied middleware v1.3"

ROW_NAMES = {
    "F": "F 基础 Foundation",
    "13": "13 感知类算子 Perception",
    "14": "14 控制类算子 Control",
    "15": "15 认知类算子 Cognition",
    "16": "16 数据处理类算子 Data processing",
    "17": "17 基础模型移植 Foundation models",
    "18": "18 云端适配对接 Cloud platform",
    "19": "19 核心驱动开发 Core drivers",
    "20": "20 边缘计算框架 Edge compute",
    "21": "21 安全适配 Security",
    "22": "22 仿真平台适配 Simulation",
    "23": "23 诊断工具适配 Diagnostics",
    "24": "24 SDK封装 SDK",
    "25": "25 采集系统 Motion capture",
}
STATUS_OPTIONS = ("Todo", "In progress", "In review", "Done (experiment)", "Done")
KIND_OPTIONS = ("requirement", "feature", "delivery")
BASIS_OPTIONS = ("new", "basis exists", "built, to move")

# project field name -> (data type, single-select options)
FIELDS = {
    "Row": ("SINGLE_SELECT", tuple(ROW_NAMES.values())),
    "Target repo": ("SINGLE_SELECT", REPOS),  # "Repo" is a reserved field name on GitHub
    "Kind": ("SINGLE_SELECT", KIND_OPTIONS),
    "Basis": ("SINGLE_SELECT", BASIS_OPTIONS),
    "Feature ID": ("TEXT", ()),
    "Estimate (days)": ("NUMBER", ()),
}

# view name, layout, filter ("" = none)
VIEWS = (
    [("Overview", "TABLE_LAYOUT", "")]
    + [(f"Row {row}", "BOARD_LAYOUT", f'row:"{name}"') for row, name in ROW_NAMES.items()]
    + [("By repo", "TABLE_LAYOUT", ""),
       ("Delivery", "TABLE_LAYOUT", "kind:delivery,requirement")]
)

LABELS = {
    **{f"row:{row}": ("0E8A16" if row == "F" else "1D76DB", name) for row, name in ROW_NAMES.items()},
    "status:new": ("D93F0B", "Feature map: nothing exists yet"),
    "status:basis-exists": ("FBCA04", "Feature map: code exists to wrap or fix"),
    "status:built-to-move": ("0E8A16", "Feature map: a working reference exists; the PR ports it"),
    "kind:requirement": ("5319E7", "A requirement group (workbook row)"),
    "kind:feature": ("C5DEF5", "One PR-sized feature"),
    "kind:delivery": ("BFD4F2", "A deliverable, not a PR to a code repo"),
}

# Contract-core experiment, from dora/docs/contract-core/feasibility.md ("What this slice delivered").
# ID -> (project Status, delivered, not delivered)
EXPERIMENT = {
    "F.01": ("In progress", "partly: the spec, deviations and this report are the material",
             "the proposal to dora maintainers is not written or sent"),
    "F.02": ("Done (experiment)", "fully, in the local copy: `dora_send_output_with_params`, C example",
             "not upstreamed; C input-side metadata read not added"),
    "F.03": ("In progress", "partly: frames declared per port (`input_frames`/`output_frames`, dataflow `frames:`)",
             "frame, rate and max-age in `dora-node.yml` itself"),
    "F.04": ("In progress",
             "partly: frame match, unknown and rejected frames, transform route, dynamic edges and pose wiring, "
             "the pose's parent frame when declared (check 4 in part, item 20), launch calibration and frame "
             "dictionary pinned, the first failing route per node reported; schema match is dora's existing type check",
             "declared validity handling; the pose's `child_frame`"),
    "F.06": ("In progress",
             "partly: degraded-forwarding tests and a 15-mutation sweep (every suite run per mutation) for the "
             "header, its Python binding, transform library, validator and frame-transform node",
             "a reusable kit for node authors"),
    "F.07": ("In progress", "partly: `robots/mickrobot-sim` (frames, extrinsics) in DORA_NAV",
             "the reference robots (agibot-d1-max, agibot-x2, aegis-ultra)"),
    "13.01": ("In progress", "fully for the Rust core and Python binding", "the C++ binding"),
    "13.02": ("Done (experiment)", "fully: `nodes/frame-transform`, static or pose-composed, run live", "none"),
    "13.17": ("Done (experiment)",
              "fully for the MuJoCo mobile base: every output (pointcloud, cloud, image, imu, Odometry, "
              "odom_pose, gnss) carries the header; `cloud` and `odom_pose` are typed",
              "typed image output"),
}
EXPERIMENT_EVIDENCE = (
    "Evidence: branch `exp/contract-core` in [dora](https://github.com/dorarobotics-dev/dora/tree/exp/contract-core) "
    "(26 commits on `1016eab0a`) and [DORA_NAV](https://github.com/dorarobotics-dev/DORA_NAV/tree/exp/contract-core) "
    "(14 commits on `a9257f5`); report "
    "[`docs/contract-core/feasibility.md`](https://github.com/dorarobotics-dev/dora/blob/exp/contract-core/docs/contract-core/feasibility.md). "
    "Rust 800 and Python 254 tests pass, `dora validate` 5/5, mutation sweep 15/15 caught, live run 579/579 clouds ok."
)

# Engineer-days from feasibility.md "Effort for later slices": only figures given for one ID.
ESTIMATES = {
    "13.01": 2, "13.03": 3, "13.04": 4, "13.06": 5, "13.08": 2, "13.09": 4, "13.10": 3, "13.12": 3,
    "13.13": 3, "13.14": 2, "13.16": 1,
    "F.05": 3, "24.01": 10, "24.03": 2, "21.01": 8, "F.08": 3, "F.09": 1, "F.10": 2, "24.02": 6,
    "24.05": 3, "24.06": 3,
    "16.01": 3, "16.02": 3, "16.03": 3, "16.04": 5, "16.05": 3,
    "19.03": 2, "14.13": 6, "19.01": 2, "14.15": 3, "14.11": 1, "14.03": 2, "14.06": 5, "14.07": 4,
    "14.14": 2,
}
REQ_ESTIMATES = {"13": 40, "16": 21}
# Figures the report gives for several IDs together, quoted in the requirement body.
ROW_ESTIMATE_NOTES = {
    "13": ["Row total 40 engineer-days (13.02 and 13.17 done in the experiment).",
           "13.05 / 19.07 time-align node: 5 days together.",
           "13.07, 13.11 RealSense/Orbbec and YOLO headers (dora-hub patches): 3 days together."],
    "14": ["Rows 14 and 19 together: 55 engineer-days (16 for headers alone).",
           "14.12 / 19.09 control and state schemas: 3 days together.",
           "14.01, 14.02 map save/load and relocalization: 4 days together.",
           "14.04, 14.05, 14.08 planner and controller wrapping: 3 days together.",
           "14.09 IK wrapping and 14.10 limit layer: 6 days together."],
    "16": ["Row total 21 engineer-days, including 2 for contract runtime helpers in Python and 2 for test "
           "mapping and the three data-processing mutations."],
    "19": ["Rows 14 and 19 together: 55 engineer-days (16 for headers alone).",
           "19.02, 19.05, 19.08 localization, arm integration, chassis configs: 6 days together.",
           "19.04 multi-waypoint missions and 19.06 arm task status: 6 days together.",
           "13.05 / 19.07 time-align node: 5 days together."],
    "21": ["Agent path (F.05, F.08–F.10, 21.01, 24.x): 41 engineer-days, plus 12–15 for security."],
    "24": ["Agent path (F.05, F.08–F.10, 21.01, 24.x): 41 engineer-days, plus 12–15 for security."],
}
```

- [ ] **Step 2: Write the failing tests `tools/tests/test_render.py`**

```python
from fmsync import render
from fmsync.model import Feature, Requirement

Q = Requirement("13", "感知类算子 · Perception operators", "Fusion: two sensors.", "覆盖多模态", "扩展感知", "融合算子")
F = Feature("13.02", "13", "dora", "feature", "frame_transform node", "nodes/frame-transform",
            "built, to move", "Reference op", "", "", "a | b")
D = Feature("13.15", "13", "roadmap", "delivery", "Fusion record", "", "new", "", "", "", "")


def test_markers_round_trip():
    body = render.requirement_body(Q)
    assert body.endswith("<!-- fm:R13 -->")
    assert render.find_marker(body) == "R13"
    assert render.find_marker(render.feature_body(F, Q.name)) == "13.02"
    assert render.find_marker("no marker here") is None


def test_requirement_title_and_body():
    assert render.requirement_title(Q) == "[R13] 感知类算子 · Perception operators"
    body = render.requirement_body(Q)
    for text in ("Fusion: two sensors.", "## 国家要求（必须完成）", "覆盖多模态", "## 扩展功能及参数依据",
                 "## 量化指标要求", "融合算子", "## Effort (feasibility report)", "Row total 40"):
        assert text in body


def test_requirement_f_has_no_empty_chinese_sections():
    body = render.requirement_body(Requirement("F", "基础 · Foundation", "Prerequisites.", "", "", ""))
    assert "国家要求" not in body and "量化指标要求" not in body


def test_feature_title_body_and_labels():
    assert render.feature_title(F) == "[13.02] frame_transform node"
    body = render.feature_body(F, Q.name)
    assert "one PR into `dora`" in body
    assert "| Package / location | nodes/frame-transform |" in body
    assert "a \\| b" in body
    assert "13 · 感知类算子 · Perception operators (parent issue)" in body
    assert render.labels_for_feature(F) == ("row:13", "kind:feature", "status:built-to-move")
    assert render.labels_for_requirement(Q) == ("row:13", "kind:requirement")
    assert "Deliverable **13.15**" in render.feature_body(D, Q.name)


def test_experiment_comment():
    text = render.experiment_comment("13.02")
    assert text.startswith("**Experiment (Done (experiment)).**")
    assert "nodes/frame-transform" in text and "feasibility.md" in text


def test_normalize_ignores_crlf_and_trailing_space():
    assert render.normalize("a \r\nb\n") == render.normalize("a\nb")
```

- [ ] **Step 3: Run them to verify they fail**

Run: `cd $R/tools && PYTHONPATH= $VENV/bin/python -m pytest tests/test_render.py -q`
Expected: `ImportError: cannot import name 'render'`.

- [ ] **Step 4: Write `tools/fmsync/render.py`**

```python
"""Issue titles, bodies, labels and markers. Pure functions of the records."""
import re

from .data import EXPERIMENT, EXPERIMENT_EVIDENCE, ROW_ESTIMATE_NOTES

MARKER_RE = re.compile(r"<!-- fm:([A-Z0-9.]+) -->")
STATUS_LABEL = {"new": "status:new", "basis exists": "status:basis-exists",
                "built, to move": "status:built-to-move"}


def marker(key: str) -> str:
    return f"<!-- fm:{key} -->"


def find_marker(body):
    m = MARKER_RE.search(body or "")
    return m.group(1) if m else None


def normalize(text) -> str:
    lines = (text or "").replace("\r\n", "\n").strip().split("\n")
    return "\n".join(line.rstrip() for line in lines)


def requirement_title(q) -> str:
    return f"[R{q.row}] {q.name}"


def requirement_body(q) -> str:
    parts = [f"Requirement group **{q.row}** of the v1.3 embodied-middleware feature map.", "",
             "## Acceptance (summary)", "", q.acceptance_en or "—"]
    for heading, text in (("国家要求（必须完成）", q.national_zh), ("扩展功能及参数依据", q.expansion_zh),
                          ("量化指标要求", q.acceptance_zh)):
        if text:
            parts += ["", f"## {heading}", "", text]
    notes = ROW_ESTIMATE_NOTES.get(q.row)
    if notes:
        parts += ["", "## Effort (feasibility report)", ""] + [f"- {n}" for n in notes]
    parts += ["", "Features are the sub-issues of this issue. Source: "
              "`docs/requirements/2026-10-26-feature-map-by-repo.xlsx` in this repo.", "", marker(q.key)]
    return "\n".join(parts)


def feature_title(f) -> str:
    return f"[{f.id}] {f.title}"


def _cell(value) -> str:
    return (value or "—").replace("|", "\\|").replace("\n", " ")


def feature_body(f, requirement_name: str) -> str:
    lead = (f"Feature **{f.id}** — one PR into `{f.repo}`." if f.kind == "feature"
            else f"Deliverable **{f.id}** (not a PR to a code repo).")
    rows = [("Requirement", f"{f.row} · {requirement_name} (parent issue)"),
            ("Package / location", f.location), ("Status", f.status),
            ("Existing basis", f.basis), ("Notes", f.notes)]
    table = ["| | |", "|---|---|"] + [f"| {k} | {_cell(v)} |" for k, v in rows]
    return "\n".join([lead, "", *table, "", marker(f.key)])


def labels_for_requirement(q) -> tuple:
    return (f"row:{q.row}", "kind:requirement")


def labels_for_feature(f) -> tuple:
    return (f"row:{f.row}", f"kind:{f.kind}", STATUS_LABEL[f.status])


def experiment_comment(fid: str) -> str:
    status, delivered, missing = EXPERIMENT[fid]
    return "\n".join([f"**Experiment ({status}).** Delivered on `exp/contract-core`: {delivered}.", "",
                      f"Not delivered: {missing}.", "", EXPERIMENT_EVIDENCE])
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd $R/tools && PYTHONPATH= $VENV/bin/python -m pytest tests -q`
Expected: `15 passed`.

- [ ] **Step 6: Commit**

```bash
cd $R && git add tools && git commit -q -m "feat(fmsync): project data and issue rendering

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Plan — workbook vs GitHub state

**Files:**
- Create: `$R/tools/fmsync/plan.py`, `$R/tools/tests/test_plan.py`

- [ ] **Step 1: Write the failing tests `tools/tests/test_plan.py`**

```python
from collections import Counter

import pytest

from fmsync import plan, render
from fmsync.model import Feature, Requirement

Q13 = Requirement("13", "感知类算子 · Perception operators", "Fusion.", "国", "扩", "验")
QF = Requirement("F", "基础 · Foundation", "Prerequisites.", "", "", "")
F02 = Feature("13.02", "13", "dora", "feature", "frame_transform node", "nodes/frame-transform",
              "built, to move", "ref", "", "", "")
F03 = Feature("13.03", "13", "dora", "feature", "Perception schemas", "libraries/core/types",
              "new", "", "", "", "")
REQS, FEATS = [QF, Q13], [F02, F03]


def issue(key, repo, title, body, labels, n=1):
    return plan.IssueState(key, repo, n, 1000 + n, f"I_{n}", f"https://github.com/o/{repo}/issues/{n}",
                           title, body, tuple(labels))


def synced_state():
    """State as it is right after a full apply of REQS and FEATS."""
    st = plan.State()
    for n, q in enumerate(REQS, 1):
        st.issues[q.key] = issue(q.key, "roadmap", render.requirement_title(q), render.requirement_body(q),
                                 render.labels_for_requirement(q), n)
    for n, f in enumerate(FEATS, 10):
        st.issues[f.key] = issue(f.key, "dora", render.feature_title(f), render.feature_body(f, Q13.name),
                                 render.labels_for_feature(f), n)
    for a in plan.build(REQS, FEATS, plan.State())[0]:
        if a.op == "add_item":
            st.items[a.key] = {}
            st.item_ids[a.key] = "PVTI_" + a.key
        elif a.op == "set_field":
            st.items[a.key][a.field] = a.value
        elif a.op == "add_sub_issue":
            st.sub_issues.setdefault(a.parent, set()).add(a.key)
    return st


def test_empty_state_creates_everything():
    actions, warnings = plan.build(REQS, FEATS, plan.State())
    ops = Counter(a.op for a in actions)
    assert ops["create_issue"] == 4 and ops["add_item"] == 4 and ops["add_sub_issue"] == 2
    assert ops["comment"] == 1  # 13.02 is an experiment item
    assert warnings == []
    first = [a.key for a in actions if a.op == "create_issue"]
    assert first == ["RF", "R13", "13.02", "13.03"]  # each requirement before its features


def test_status_on_create_only():
    actions, _ = plan.build(REQS, FEATS, plan.State())
    status = {a.key: a.value for a in actions if a.op == "set_field" and a.field == "Status"}
    assert status == {"RF": "Todo", "R13": "Todo", "13.02": "Done (experiment)", "13.03": "Todo"}
    st = synced_state()
    st.items["13.03"]["Status"] = "In progress"  # moved by a person
    actions, _ = plan.build(REQS, FEATS, st)
    assert actions == []


def test_fields():
    actions, _ = plan.build(REQS, FEATS, plan.State())
    f = {(a.key, a.field): a.value for a in actions if a.op == "set_field"}
    assert f[("13.02", "Row")] == "13 感知类算子 Perception"
    assert f[("13.02", "Target repo")] == "dora" and f[("13.02", "Kind")] == "feature"
    assert f[("13.02", "Basis")] == "built, to move" and f[("13.02", "Feature ID")] == "13.02"
    assert f[("13.03", "Estimate (days)")] == 3 and f[("R13", "Estimate (days)")] == 40
    assert ("RF", "Estimate (days)") not in f and ("R13", "Basis") not in f


def test_synced_state_plans_nothing():
    assert plan.build(REQS, FEATS, synced_state()) == ([], [])


def test_changed_body_is_updated_and_labels_kept():
    st = synced_state()
    old = st.issues["13.03"]
    st.issues["13.03"] = plan.IssueState(old.key, old.repo, old.number, old.id, old.node_id, old.url,
                                         old.title, "old body", ("bug", "row:13"))
    actions, _ = plan.build(REQS, FEATS, st)
    assert [a.op for a in actions] == ["update_issue"]
    assert set(actions[0].labels) == {"bug", "row:13", "kind:feature", "status:new"}


def test_crlf_body_is_not_a_change():
    st = synced_state()
    old = st.issues["R13"]
    st.issues["R13"] = plan.IssueState(old.key, old.repo, old.number, old.id, old.node_id, old.url,
                                       old.title, old.body.replace("\n", "\r\n") + "\r\n", old.labels)
    assert plan.build(REQS, FEATS, st)[0] == []


def test_removed_feature_is_reported_not_touched():
    st = synced_state()
    actions, warnings = plan.build(REQS, [F02], st)
    assert actions == []
    assert warnings == ["13.03: https://github.com/o/dora/issues/11 is not in the workbook; left as it is"]


def test_only_selects_row_or_id_and_pulls_in_the_parent():
    actions, _ = plan.build(REQS, FEATS, plan.State(), only={"13.03"})
    assert [a.key for a in actions if a.op == "create_issue"] == ["R13", "13.03"]
    actions, _ = plan.build(REQS, FEATS, plan.State(), only={"F"})
    assert [a.key for a in actions if a.op == "create_issue"] == ["RF"]


def test_issue_in_wrong_repo_is_an_error():
    st = synced_state()
    old = st.issues["13.03"]
    st.issues["13.03"] = plan.IssueState(old.key, "DORA_NAV", old.number, old.id, old.node_id, old.url,
                                         old.title, old.body, old.labels)
    with pytest.raises(plan.PlanError, match="13.03 is in DORA_NAV, the workbook says dora"):
        plan.build(REQS, FEATS, st)
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd $R/tools && PYTHONPATH= $VENV/bin/python -m pytest tests/test_plan.py -q`
Expected: `ImportError: cannot import name 'plan'`.

- [ ] **Step 3: Write `tools/fmsync/plan.py`**

```python
"""Compare the workbook with GitHub and list the actions that make GitHub match. Pure."""
from dataclasses import dataclass, field

from . import render
from .data import ESTIMATES, EXPERIMENT, REQ_ESTIMATES, ROW_NAMES


class PlanError(ValueError):
    pass


@dataclass(frozen=True)
class IssueState:
    key: str
    repo: str
    number: int
    id: int          # REST id (sub-issue API)
    node_id: str     # GraphQL id (project API)
    url: str
    title: str
    body: str
    labels: tuple


@dataclass
class State:
    issues: dict = field(default_factory=dict)      # key -> IssueState
    items: dict = field(default_factory=dict)       # key -> {field name: value}; present = in the project
    item_ids: dict = field(default_factory=dict)    # key -> project item id
    sub_issues: dict = field(default_factory=dict)  # requirement key -> set of child keys


@dataclass(frozen=True)
class Action:
    op: str          # create_issue, update_issue, comment, add_item, set_field, add_sub_issue
    key: str
    repo: str = ""
    title: str = ""
    body: str = ""
    labels: tuple = ()
    field: str = ""
    value: object = None
    parent: str = ""


def _selected(only, row, key) -> bool:
    return only is None or row in only or key in only


def build(requirements, features, state, only=None):
    actions, warnings = [], []
    names = {q.row: q.name for q in requirements}
    feature_rows = {f.row for f in features if _selected(only, f.row, f.key)}
    for q in requirements:
        if _selected(only, q.row, q.key) or q.row in feature_rows:
            fields = {"Row": ROW_NAMES[q.row], "Target repo": "roadmap", "Kind": "requirement", "Feature ID": q.key}
            if q.row in REQ_ESTIMATES:
                fields["Estimate (days)"] = REQ_ESTIMATES[q.row]
            actions += _issue_actions(state, q.key, "roadmap", render.requirement_title(q),
                                      render.requirement_body(q), render.labels_for_requirement(q),
                                      fields, "Todo", None, None)
        for f in features:
            if f.row != q.row or not _selected(only, f.row, f.key):
                continue
            fields = {"Row": ROW_NAMES[f.row], "Target repo": f.repo, "Kind": f.kind, "Basis": f.status,
                      "Feature ID": f.id}
            if f.id in ESTIMATES:
                fields["Estimate (days)"] = ESTIMATES[f.id]
            experiment = f.id in EXPERIMENT
            actions += _issue_actions(state, f.key, f.repo, render.feature_title(f),
                                      render.feature_body(f, names[f.row]), render.labels_for_feature(f),
                                      fields, EXPERIMENT[f.id][0] if experiment else "Todo", q.key,
                                      render.experiment_comment(f.id) if experiment else None)
    wanted = {q.key for q in requirements} | {f.key for f in features}
    for key in sorted(set(state.issues) - wanted):
        warnings.append(f"{key}: {state.issues[key].url} is not in the workbook; left as it is")
    return actions, warnings


def _issue_actions(state, key, repo, title, body, labels, fields, status, parent, comment):
    out = []
    existing = state.issues.get(key)
    if existing is None:
        out.append(Action("create_issue", key, repo=repo, title=title, body=body, labels=tuple(labels)))
        if comment:
            out.append(Action("comment", key, repo=repo, body=comment))
    else:
        if existing.repo != repo:
            raise PlanError(f"{key} is in {existing.repo}, the workbook says {repo}; move it by hand")
        missing = set(labels) - set(existing.labels)
        if (render.normalize(existing.title) != render.normalize(title)
                or render.normalize(existing.body) != render.normalize(body) or missing):
            out.append(Action("update_issue", key, repo=repo, title=title, body=body,
                              labels=tuple(sorted(set(existing.labels) | set(labels)))))
    current = state.items.get(key)
    if current is None:
        out.append(Action("add_item", key))
        out.append(Action("set_field", key, field="Status", value=status))
        current = {}
    for name, value in fields.items():
        if current.get(name) != value:
            out.append(Action("set_field", key, field=name, value=value))
    if parent and key not in state.sub_issues.get(parent, set()):
        out.append(Action("add_sub_issue", key, parent=parent))
    return out
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd $R/tools && PYTHONPATH= $VENV/bin/python -m pytest tests -q`
Expected: `24 passed`.

- [ ] **Step 5: Commit**

```bash
cd $R && git add tools && git commit -q -m "feat(fmsync): plan the actions that bring GitHub in line with the workbook

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: GitHub wrapper

**Files:**
- Create: `$R/tools/fmsync/github.py`, `$R/tools/tests/test_github.py`

- [ ] **Step 1: Write the failing tests `tools/tests/test_github.py`**

```python
import json

import pytest

from fmsync.github import Gh, GhError


class Runner:
    """Records gh calls and answers them from a list of canned outputs (str or exception)."""

    def __init__(self, *answers):
        self.answers, self.calls = list(answers), []

    def __call__(self, args, stdin=None):
        self.calls.append((args, json.loads(stdin) if stdin else None))
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer


def gh(*answers):
    r = Runner(*answers)
    return Gh(runner=r, sleep=lambda s: None), r


def test_create_issue_posts_json_and_returns_state():
    g, r = gh(json.dumps({"number": 7, "id": 77, "node_id": "I_7", "html_url": "u7"}))
    s = g.create_issue("dora", "[F.04] t", "body <!-- fm:F.04 -->", ("row:F",), "F.04")
    args, body = r.calls[0]
    assert args == ["api", "-X", "POST", "repos/dorarobotics-dev/dora/issues", "--input", "-"]
    assert body == {"title": "[F.04] t", "body": "body <!-- fm:F.04 -->", "labels": ["row:F"]}
    assert (s.key, s.repo, s.number, s.id, s.node_id, s.url) == ("F.04", "dora", 7, 77, "I_7", "u7")


def test_list_marked_issues_skips_unmarked():
    lines = "\n".join(json.dumps(x) for x in [
        {"number": 1, "id": 11, "node_id": "I_1", "html_url": "u1", "title": "a", "body": "x <!-- fm:R13 -->",
         "labels": ["row:13"]},
        {"number": 2, "id": 12, "node_id": "I_2", "html_url": "u2", "title": "b", "body": None, "labels": []},
    ])
    g, r = gh(lines + "\n")
    issues = g.list_marked_issues("roadmap")
    assert [i.key for i in issues] == ["R13"] and issues[0].labels == ("row:13",)
    assert r.calls[0][0][:3] == ["api", "--paginate", "repos/dorarobotics-dev/roadmap/issues?state=all&per_page=100"]


def test_owner_guard():
    g, _ = gh()
    with pytest.raises(GhError, match="outside dorarobotics-dev"):
        g.api("repos/dora-rs/dora/issues", method="POST", body={})


def test_graphql_errors_raise():
    g, _ = gh(json.dumps({"errors": [{"message": "nope"}]}))
    with pytest.raises(GhError, match="nope"):
        g.graphql("query { viewer { login } }")


def test_rate_limit_is_retried():
    g, r = gh(GhError("HTTP 403: You have exceeded a secondary rate limit"), json.dumps({"data": {"x": 1}}))
    assert g.graphql("query { x }") == {"x": 1}
    assert len(r.calls) == 2


def test_other_errors_are_not_retried():
    g, r = gh(GhError("HTTP 422: Validation Failed"))
    with pytest.raises(GhError, match="422"):
        g.graphql("query { x }")
    assert len(r.calls) == 1


def test_set_field_value_shapes():
    ok = json.dumps({"data": {"updateProjectV2ItemFieldValue": {"projectV2Item": {"id": "PVTI"}}}})
    g, r = gh(ok, ok, ok)
    g.set_field("P", "PVTI", {"id": "F1", "type": "SINGLE_SELECT", "options": {"dora": "O1"}}, "dora")
    g.set_field("P", "PVTI", {"id": "F2", "type": "TEXT", "options": {}}, "F.04")
    g.set_field("P", "PVTI", {"id": "F3", "type": "NUMBER", "options": {}}, 3)
    values = [c[1]["variables"]["value"] for c in r.calls]
    assert values == [{"singleSelectOptionId": "O1"}, {"text": "F.04"}, {"number": 3.0}]


def test_unknown_option_is_an_error():
    g, _ = gh()
    with pytest.raises(GhError, match="no option 'x' in field Repo"):
        g.set_field("P", "I", {"id": "F", "name": "Repo", "type": "SINGLE_SELECT", "options": {}}, "x")
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd $R/tools && PYTHONPATH= $VENV/bin/python -m pytest tests/test_github.py -q`
Expected: `ModuleNotFoundError: No module named 'fmsync.github'`.

- [ ] **Step 3: Write `tools/fmsync/github.py`**

```python
"""Thin wrappers over `gh api` (REST and GraphQL) for the org dorarobotics-dev only."""
import json
import subprocess
import time

from .data import ORG
from .plan import IssueState
from .render import find_marker

RETRYABLE = ("rate limit", "HTTP 429", "HTTP 502", "HTTP 503")
CREATE_PAUSE_S = 1.0


class GhError(RuntimeError):
    pass


def _run(args, stdin=None) -> str:
    p = subprocess.run(["gh", *args], input=stdin, capture_output=True, text=True)
    if p.returncode != 0:
        raise GhError(f"gh {' '.join(args[:4])}: {p.stderr.strip() or p.stdout.strip()}")
    return p.stdout


class Gh:
    def __init__(self, runner=_run, sleep=time.sleep):
        self._runner, self._sleep = runner, sleep

    # -- transport -----------------------------------------------------------------------------
    def _call(self, args, stdin=None) -> str:
        for attempt in range(5):
            try:
                return self._runner(args, stdin)
            except GhError as e:
                if attempt == 4 or not any(s in str(e) for s in RETRYABLE):
                    raise
                self._sleep(60 * (attempt + 1))
        raise AssertionError("unreachable")

    def api(self, path, method="GET", body=None, paginate=False, jq=None) -> str:
        if path.startswith(("repos/", "orgs/")) and not path.startswith((f"repos/{ORG}/", f"orgs/{ORG}/")):
            raise GhError(f"refusing {method} {path}: outside {ORG}")
        args = ["api"] + (["--paginate"] if paginate else []) + (["-X", method] if method != "GET" else [])
        args.append(path)
        if jq:
            args += ["--jq", jq]
        if body is not None:
            args += ["--input", "-"]
        return self._call(args, json.dumps(body) if body is not None else None)

    def graphql(self, query, **variables) -> dict:
        out = json.loads(self._call(["api", "graphql", "--input", "-"],
                                    json.dumps({"query": query, "variables": variables})))
        if out.get("errors"):
            raise GhError("; ".join(e.get("message", str(e)) for e in out["errors"]))
        return out["data"]

    # -- issues --------------------------------------------------------------------------------
    def list_marked_issues(self, repo) -> list:
        out = self.api(f"repos/{ORG}/{repo}/issues?state=all&per_page=100", paginate=True,
                       jq=".[] | select(.pull_request == null) | "
                          "{number, id, node_id, html_url, title, body, labels: [.labels[].name]}")
        issues = []
        for line in out.splitlines():
            if not line.strip():
                continue
            d = json.loads(line)
            key = find_marker(d.get("body"))
            if key:
                issues.append(IssueState(key, repo, d["number"], d["id"], d["node_id"], d["html_url"],
                                         d["title"], d.get("body") or "", tuple(d["labels"])))
        return issues

    def create_issue(self, repo, title, body, labels, key) -> IssueState:
        d = json.loads(self.api(f"repos/{ORG}/{repo}/issues", "POST",
                                {"title": title, "body": body, "labels": list(labels)}))
        self._sleep(CREATE_PAUSE_S)
        return IssueState(key, repo, d["number"], d["id"], d["node_id"], d["html_url"], title, body, tuple(labels))

    def update_issue(self, repo, number, title, body, labels) -> None:
        self.api(f"repos/{ORG}/{repo}/issues/{number}", "PATCH",
                 {"title": title, "body": body, "labels": list(labels)})

    def comment(self, repo, number, body) -> None:
        self.api(f"repos/{ORG}/{repo}/issues/{number}/comments", "POST", {"body": body})
        self._sleep(CREATE_PAUSE_S)

    def sub_issue_ids(self, repo, number) -> list:
        out = self.api(f"repos/{ORG}/{repo}/issues/{number}/sub_issues?per_page=100", paginate=True, jq=".[].id")
        return [int(x) for x in out.split()]

    def add_sub_issue(self, repo, number, child_id) -> None:
        self.api(f"repos/{ORG}/{repo}/issues/{number}/sub_issues", "POST", {"sub_issue_id": child_id})

    def labels(self, repo) -> set:
        return set(self.api(f"repos/{ORG}/{repo}/labels?per_page=100", paginate=True, jq=".[].name").splitlines())

    def create_label(self, repo, name, color, description) -> None:
        self.api(f"repos/{ORG}/{repo}/labels", "POST", {"name": name, "color": color, "description": description})

    # -- project -------------------------------------------------------------------------------
    def find_project(self, title):
        d = self.graphql("query($org:String!){organization(login:$org){id projectsV2(first:50)"
                         "{nodes{id number title url}}}}", org=ORG)
        for p in d["organization"]["projectsV2"]["nodes"]:
            if p["title"] == title:
                return p
        return None

    def create_project(self, title) -> dict:
        org = self.graphql("query($org:String!){organization(login:$org){id}}", org=ORG)["organization"]["id"]
        d = self.graphql("mutation($o:ID!,$t:String!){createProjectV2(input:{ownerId:$o,title:$t})"
                         "{projectV2{id number title url}}}", o=org, t=title)
        return d["createProjectV2"]["projectV2"]

    def project_fields(self, project_id) -> dict:
        d = self.graphql("query($id:ID!){node(id:$id){... on ProjectV2{fields(first:50){nodes{"
                         "... on ProjectV2FieldCommon{id name dataType} "
                         "... on ProjectV2SingleSelectField{options{id name}}}}}}}", id=project_id)
        return {f["name"]: {"id": f["id"], "name": f["name"], "type": f["dataType"],
                            "options": {o["name"]: o["id"] for o in f.get("options", [])}}
                for f in d["node"]["fields"]["nodes"] if f}

    def create_field(self, project_id, name, data_type, options=()) -> None:
        inp = {"projectId": project_id, "name": name, "dataType": data_type}
        if options:
            inp["singleSelectOptions"] = [{"name": o, "color": "GRAY", "description": ""} for o in options]
        self.graphql("mutation($i:CreateProjectV2FieldInput!){createProjectV2Field(input:$i)"
                     "{projectV2Field{... on ProjectV2FieldCommon{id}}}}", i=inp)

    def set_status_options(self, field_id, options) -> None:
        colors = ("GRAY", "BLUE", "YELLOW", "PURPLE", "GREEN")
        self.graphql("mutation($i:UpdateProjectV2FieldInput!){updateProjectV2Field(input:$i)"
                     "{projectV2Field{... on ProjectV2FieldCommon{id}}}}",
                     i={"fieldId": field_id, "singleSelectOptions": [
                         {"name": o, "color": colors[n % len(colors)], "description": ""}
                         for n, o in enumerate(options)]})

    def project_items(self, project_id) -> dict:
        items, after = {}, None
        while True:
            d = self.graphql(
                "query($id:ID!,$after:String){node(id:$id){... on ProjectV2{items(first:100,after:$after){"
                "pageInfo{hasNextPage endCursor} nodes{id content{... on Issue{id}} fieldValues(first:20){nodes{"
                "... on ProjectV2ItemFieldSingleSelectValue{name field{... on ProjectV2FieldCommon{name}}} "
                "... on ProjectV2ItemFieldTextValue{text field{... on ProjectV2FieldCommon{name}}} "
                "... on ProjectV2ItemFieldNumberValue{number field{... on ProjectV2FieldCommon{name}}}}}}}}}}",
                id=project_id, after=after)
            page = d["node"]["items"]
            for n in page["nodes"]:
                if not n.get("content"):
                    continue
                fields = {}
                for v in n["fieldValues"]["nodes"]:
                    if v and "field" in v:
                        fields[v["field"]["name"]] = v.get("name", v.get("text", v.get("number")))
                items[n["content"]["id"]] = {"item_id": n["id"], "fields": fields}
            if not page["pageInfo"]["hasNextPage"]:
                return items
            after = page["pageInfo"]["endCursor"]

    def add_item(self, project_id, content_id) -> str:
        d = self.graphql("mutation($p:ID!,$c:ID!){addProjectV2ItemById(input:{projectId:$p,contentId:$c})"
                         "{item{id}}}", p=project_id, c=content_id)
        return d["addProjectV2ItemById"]["item"]["id"]

    def set_field(self, project_id, item_id, field, value) -> None:
        if field["type"] == "SINGLE_SELECT":
            if value not in field["options"]:
                raise GhError(f"no option {value!r} in field {field.get('name', field['id'])}")
            v = {"singleSelectOptionId": field["options"][value]}
        elif field["type"] == "NUMBER":
            v = {"number": float(value)}
        else:
            v = {"text": str(value)}
        self.graphql("mutation($p:ID!,$i:ID!,$f:ID!,$value:ProjectV2FieldValue!){updateProjectV2ItemFieldValue("
                     "input:{projectId:$p,itemId:$i,fieldId:$f,value:$value}){projectV2Item{id}}}",
                     p=project_id, i=item_id, f=field["id"], value=v)

    def views(self, project_id) -> dict:
        d = self.graphql("query($id:ID!){node(id:$id){... on ProjectV2{views(first:50){nodes{id name}}}}}",
                         id=project_id)
        return {v["name"]: v["id"] for v in d["node"]["views"]["nodes"]}

    def create_view(self, project_id, name, layout) -> str:
        d = self.graphql("mutation($p:ID!,$n:String!,$l:ProjectV2ViewLayout!){createProjectV2View("
                         "input:{projectId:$p,name:$n,layout:$l}){projectV2View{id}}}", p=project_id, n=name, l=layout)
        return d["createProjectV2View"]["projectV2View"]["id"]

    def update_view(self, view_id, name=None, filter=None) -> None:
        inp = {"viewId": view_id}
        if name is not None:
            inp["name"] = name
        if filter is not None:
            inp["filter"] = filter
        self.graphql("mutation($i:UpdateProjectV2ViewInput!){updateProjectV2View(input:$i){projectV2View{id}}}",
                     i=inp)
```

Note: `fmsync.github` imports `IssueState` from `plan.py` (Task 5). If a mutation's payload field name differs from the live schema (`projectV2View` in `createProjectV2View`), Task 11's dry run will not reveal it; Task 11 Step 3 runs the first apply and prints the error. Fix the selection set to the name the error gives, re-run the unit tests, and commit the fix.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd $R/tools && PYTHONPATH= $VENV/bin/python -m pytest tests -q`
Expected: `32 passed`.

- [ ] **Step 5: Commit**

```bash
cd $R && git add tools && git commit -q -m "feat(fmsync): gh api wrapper with owner guard and rate-limit retry

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Setup, state loading and execution (with an in-memory GitHub)

**Files:**
- Create: `$R/tools/fmsync/apply.py`, `$R/tools/tests/fakes.py`, `$R/tools/tests/test_apply.py`

- [ ] **Step 1: Write `tools/tests/fakes.py`**

```python
"""In-memory stand-in for fmsync.github.Gh, with the same method names and return shapes."""
import itertools

from fmsync.plan import IssueState
from fmsync.render import find_marker


class FakeGh:
    def __init__(self):
        self.ids = itertools.count(1)
        self.issues = {}          # (repo, number) -> IssueState
        self.comments = []        # (repo, number, body)
        self.subs = {}            # (repo, number) -> [child REST id]
        self.repo_labels = {}     # repo -> set
        self.project = None
        self.fields = {}          # name -> {"id","name","type","options"}
        self.items = {}           # content node id -> {"item_id", "fields"}
        self.view_ids = {}        # name -> id
        self.view_filters = {}    # id -> filter
        self.calls = []

    # issues
    def list_marked_issues(self, repo):
        return [s for (r, _), s in sorted(self.issues.items()) if r == repo and find_marker(s.body)]

    def create_issue(self, repo, title, body, labels, key):
        n = next(self.ids)
        s = IssueState(key, repo, n, 1000 + n, f"I_{n}", f"https://github.com/dorarobotics-dev/{repo}/issues/{n}",
                       title, body, tuple(labels))
        self.issues[(repo, n)] = s
        self.calls.append(("create_issue", key))
        return s

    def update_issue(self, repo, number, title, body, labels):
        old = self.issues[(repo, number)]
        self.issues[(repo, number)] = IssueState(old.key, repo, number, old.id, old.node_id, old.url,
                                                 title, body, tuple(labels))
        self.calls.append(("update_issue", old.key))

    def comment(self, repo, number, body):
        self.comments.append((repo, number, body))

    def sub_issue_ids(self, repo, number):
        return list(self.subs.get((repo, number), []))

    def add_sub_issue(self, repo, number, child_id):
        self.subs.setdefault((repo, number), []).append(child_id)

    def labels(self, repo):
        return set(self.repo_labels.get(repo, set()))

    def create_label(self, repo, name, color, description):
        self.repo_labels.setdefault(repo, set()).add(name)

    # project
    def find_project(self, title):
        return self.project if self.project and self.project["title"] == title else None

    def create_project(self, title):
        self.project = {"id": "PVT_1", "number": 1, "title": title, "url": "https://github.com/orgs/x/projects/1"}
        self.fields = {"Title": {"id": "F_T", "name": "Title", "type": "TITLE", "options": {}},
                       "Status": {"id": "F_S", "name": "Status", "type": "SINGLE_SELECT",
                                  "options": {"Todo": "s1", "In Progress": "s2", "Done": "s3"}}}
        self.view_ids = {"View 1": "V_0"}
        return self.project

    def project_fields(self, project_id):
        return {k: dict(v, options=dict(v["options"])) for k, v in self.fields.items()}

    def create_field(self, project_id, name, data_type, options=()):
        self.fields[name] = {"id": f"F_{name}", "name": name, "type": data_type,
                             "options": {o: f"{name}:{o}" for o in options}}

    def set_status_options(self, field_id, options):
        self.fields["Status"]["options"] = {o: f"Status:{o}" for o in options}

    def project_items(self, project_id):
        return {k: {"item_id": v["item_id"], "fields": dict(v["fields"])} for k, v in self.items.items()}

    def add_item(self, project_id, content_id):
        self.items[content_id] = {"item_id": f"PVTI_{content_id}", "fields": {}}
        return f"PVTI_{content_id}"

    def set_field(self, project_id, item_id, field, value):
        for item in self.items.values():
            if item["item_id"] == item_id:
                if field["type"] == "SINGLE_SELECT":
                    assert value in field["options"], (field["name"], value)
                item["fields"][field["name"]] = float(value) if field["type"] == "NUMBER" else value
                return
        raise KeyError(item_id)

    def views(self, project_id):
        return dict(self.view_ids)

    def create_view(self, project_id, name, layout):
        vid = f"V_{len(self.view_ids)}"
        self.view_ids[name] = vid
        return vid

    def update_view(self, view_id, name=None, filter=None):
        if name is not None:
            old = next(k for k, v in self.view_ids.items() if v == view_id)
            self.view_ids[name] = self.view_ids.pop(old)
        if filter is not None:
            self.view_filters[view_id] = filter
```

- [ ] **Step 2: Write the failing tests `tools/tests/test_apply.py`**

```python
from conftest import MAP, SOURCE
from fakes import FakeGh
from fmsync import apply, plan, workbook
from fmsync.data import FIELDS, LABELS, PROJECT_TITLE, REPOS, STATUS_OPTIONS, VIEWS


def test_setup_dry_run_changes_nothing():
    g = FakeGh()
    log = []
    apply.setup(g, apply=False, log=log.append)
    assert g.project is None and g.repo_labels == {}
    assert f"project {PROJECT_TITLE!r}" in log
    assert sum(1 for line in log if line.startswith("label ")) == len(REPOS) * len(LABELS)


def test_setup_apply_creates_everything_and_is_idempotent():
    g = FakeGh()
    apply.setup(g, apply=True, log=lambda s: None)
    assert all(g.repo_labels[r] == set(LABELS) for r in REPOS)
    assert list(g.fields["Status"]["options"]) == list(STATUS_OPTIONS)
    assert set(FIELDS) <= set(g.fields)
    assert list(g.view_ids) == [name for name, _, _ in VIEWS]
    assert g.view_filters[g.view_ids["Row 13"]] == 'row:"13 感知类算子 Perception"'
    log = []
    apply.setup(g, apply=True, log=log.append)
    assert log == []


def test_full_sync_then_nothing_to_do():
    g = FakeGh()
    apply.setup(g, apply=True, log=lambda s: None)
    reqs, feats = workbook.read_requirements(MAP, SOURCE), workbook.read_features(MAP)
    state = apply.load_state(g, g.project)
    actions, warnings = plan.build(reqs, feats, state)
    assert warnings == []
    apply.execute(g, g.project, actions, state, log=lambda s: None)
    assert len(g.issues) == 14 + 131
    assert len(g.comments) == 9
    roadmap_r13 = next(s for s in g.issues.values() if s.key == "R13")
    assert len(g.subs[("roadmap", roadmap_r13.number)]) == sum(1 for f in feats if f.row == "13")
    again, _ = plan.build(reqs, feats, apply.load_state(g, g.project))
    assert again == []


def test_load_state_refuses_a_marker_on_two_issues():
    g = FakeGh()
    g.create_issue("roadmap", "a", "x <!-- fm:R13 -->", (), "R13")
    g.create_issue("dora", "b", "y <!-- fm:R13 -->", (), "R13")
    try:
        apply.load_state(g, None)
    except ValueError as e:
        assert "R13" in str(e)
    else:
        raise AssertionError("expected ValueError")
```

- [ ] **Step 3: Run them to verify they fail**

Run: `cd $R/tools && PYTHONPATH= $VENV/bin/python -m pytest tests/test_apply.py -q`
Expected: `ImportError: cannot import name 'apply'`.

- [ ] **Step 4: Write `tools/fmsync/apply.py`**

```python
"""Create the project scaffolding, read GitHub state, and carry out planned actions."""
from .data import FIELDS, LABELS, PROJECT_TITLE, REPOS, STATUS_OPTIONS, VIEWS
from .plan import State


def setup(gh, apply, log=print):
    """Labels in every repo; the project with its Status options, fields and views. Returns the project."""
    for repo in REPOS:
        have = gh.labels(repo)
        for name, (color, description) in LABELS.items():
            if name not in have:
                log(f"label {repo} {name}")
                if apply:
                    gh.create_label(repo, name, color, description)
    project = gh.find_project(PROJECT_TITLE)
    if project is None:
        log(f"project {PROJECT_TITLE!r}")
        if not apply:
            log("fields and views follow once the project exists")
            return None
        project = gh.create_project(PROJECT_TITLE)
    fields = gh.project_fields(project["id"])
    if list(fields["Status"]["options"]) != list(STATUS_OPTIONS):
        log("Status options: " + ", ".join(STATUS_OPTIONS))
        if apply:
            gh.set_status_options(fields["Status"]["id"], STATUS_OPTIONS)
    for name, (data_type, options) in FIELDS.items():
        if name not in fields:
            log(f"field {name} ({data_type})")
            if apply:
                gh.create_field(project["id"], name, data_type, options)
        elif options and list(fields[name]["options"]) != list(options):
            raise ValueError(f"field {name} exists with options {list(fields[name]['options'])}; fix it by hand")
    views = gh.views(project["id"])
    if "Overview" not in views and "View 1" in views:
        log("view View 1 -> Overview")
        if apply:
            gh.update_view(views["View 1"], name="Overview")
        views["Overview"] = views.pop("View 1")
    for name, layout, view_filter in VIEWS:
        if name not in views:
            log(f"view {name} ({layout}) {view_filter}".rstrip())
            if apply:
                view_id = gh.create_view(project["id"], name, layout)
                if view_filter:
                    gh.update_view(view_id, filter=view_filter)
    return project


def load_state(gh, project, repos=REPOS) -> State:
    state = State()
    for repo in repos:
        for s in gh.list_marked_issues(repo):
            if s.key in state.issues:
                raise ValueError(f"marker {s.key} is on two issues: {state.issues[s.key].url} and {s.url}")
            state.issues[s.key] = s
    by_node = {s.node_id: k for k, s in state.issues.items()}
    by_id = {s.id: k for k, s in state.issues.items()}
    if project:
        for node_id, item in gh.project_items(project["id"]).items():
            key = by_node.get(node_id)
            if key:
                state.items[key] = item["fields"]
                state.item_ids[key] = item["item_id"]
    for key, s in state.issues.items():
        if key.startswith("R"):
            state.sub_issues[key] = {by_id[i] for i in gh.sub_issue_ids(s.repo, s.number) if i in by_id}
    return state


def execute(gh, project, actions, state, log=print) -> dict:
    issues, item_ids = dict(state.issues), dict(state.item_ids)
    fields = gh.project_fields(project["id"])
    for a in actions:
        if a.op == "create_issue":
            issues[a.key] = gh.create_issue(a.repo, a.title, a.body, a.labels, a.key)
            log(f"created {a.key} {issues[a.key].url}")
        elif a.op == "update_issue":
            s = issues[a.key]
            gh.update_issue(s.repo, s.number, a.title, a.body, a.labels)
            log(f"updated {a.key} {s.url}")
        elif a.op == "comment":
            s = issues[a.key]
            gh.comment(s.repo, s.number, a.body)
        elif a.op == "add_item":
            item_ids[a.key] = gh.add_item(project["id"], issues[a.key].node_id)
        elif a.op == "set_field":
            gh.set_field(project["id"], item_ids[a.key], fields[a.field], a.value)
        elif a.op == "add_sub_issue":
            parent = issues[a.parent]
            gh.add_sub_issue(parent.repo, parent.number, issues[a.key].id)
        else:
            raise ValueError(f"unknown action {a.op}")
    return issues
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd $R/tools && PYTHONPATH= $VENV/bin/python -m pytest tests -q`
Expected: `36 passed`.

- [ ] **Step 6: Commit**

```bash
cd $R && git add tools && git commit -q -m "feat(fmsync): project setup, state loading and execution

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Write issue URLs back into the workbook

**Files:**
- Create: `$R/tools/fmsync/writeback.py`, `$R/tools/tests/test_writeback.py`

- [ ] **Step 1: Write the failing test `tools/tests/test_writeback.py`**

```python
import shutil

import openpyxl

from conftest import MAP
from fmsync import writeback


def test_writes_only_the_issue_column(tmp_path):
    path = tmp_path / "map.xlsx"
    shutil.copy(MAP, path)
    urls = {"F.04": "https://github.com/dorarobotics-dev/dora/issues/4",
            "F.12": "https://github.com/dorarobotics-dev/roadmap/issues/9"}
    assert writeback.write_issue_urls(path, urls) == 2
    assert writeback.write_issue_urls(path, urls) == 0
    wb = openpyxl.load_workbook(path)
    dora = {r[0].value: r for r in wb["dora"].iter_rows(min_row=2)}
    assert dora["F.04"][8].value == urls["F.04"]
    assert dora["F.04"][3].value.startswith("dora validate checks")
    assert wb["Summary"]["D2"].value == "=COUNTA(dora!$A:$A)-1"
    delivery = {r[0].value: r for r in wb["delivery"].iter_rows(min_row=2)}
    assert delivery["F.12"][8].value == urls["F.12"]
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd $R/tools && PYTHONPATH= $VENV/bin/python -m pytest tests/test_writeback.py -q`
Expected: `ImportError: cannot import name 'writeback'`.

- [ ] **Step 3: Write `tools/fmsync/writeback.py`**

```python
"""Write issue URLs into the `Issue / PR` column (I) of the feature sheets; nothing else."""
import openpyxl

from .model import SHEET_REPO

ISSUE_COL = 8  # zero-based index of column I


def write_issue_urls(path, urls: dict) -> int:
    wb = openpyxl.load_workbook(path)
    changed = 0
    for sheet in SHEET_REPO:
        for row in wb[sheet].iter_rows(min_row=2):
            fid = str(row[0].value or "").strip()
            if fid in urls and row[ISSUE_COL].value != urls[fid]:
                row[ISSUE_COL].value = urls[fid]
                changed += 1
    if changed:
        wb.save(path)
    return changed
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd $R/tools && PYTHONPATH= $VENV/bin/python -m pytest tests -q`
Expected: `37 passed`.

- [ ] **Step 5: Commit**

```bash
cd $R && git add tools && git commit -q -m "feat(fmsync): write issue URLs back into the workbook

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Command-line entry point

**Files:**
- Create: `$R/tools/fm_sync.py`, `$R/tools/tests/test_cli.py`

- [ ] **Step 1: Write the failing tests `tools/tests/test_cli.py`**

```python
import shutil

import fm_sync
from conftest import MAP
from fakes import FakeGh


def run(argv, g):
    out = []
    code = fm_sync.main(argv, gh=g, out=out.append)
    return code, out


def test_sync_dry_run_without_project_plans_everything():
    g = FakeGh()
    code, out = run(["sync"], g)
    assert code == 0 and g.issues == {}
    assert out[-2].startswith("plan: create_issue 145, update_issue 0, comment 9, add_item 145, set_field ")
    assert out[-2].endswith(", add_sub_issue 131")
    assert out[-1] == "dry run: nothing changed (add --apply)"


def test_sync_apply_needs_a_project():
    code, out = run(["sync", "--apply"], FakeGh())
    assert code == 1 and out[-1] == "no project: run `fm_sync.py setup --apply` first"


def test_setup_then_sync_then_idempotent():
    g = FakeGh()
    assert run(["setup", "--apply"], g)[0] == 0
    assert run(["sync", "--apply", "--only", "F"], g)[0] == 0
    assert {s.key for s in g.issues.values()} == {"RF"} | {f"F.{n:02d}" for n in range(1, 21)}
    assert run(["sync", "--apply"], g)[0] == 0
    code, out = run(["sync"], g)
    assert out[-2] == ("plan: create_issue 0, update_issue 0, comment 0, add_item 0, set_field 0, "
                       "add_sub_issue 0")


def test_writeback(tmp_path):
    path = tmp_path / "map.xlsx"
    shutil.copy(MAP, path)
    g = FakeGh()
    run(["setup", "--apply"], g)
    run(["sync", "--apply", "--only", "F.04", "--map", str(path)], g)
    code, out = run(["writeback", "--map", str(path)], g)
    assert out[-1] == "dry run: 2 issue URLs to write (add --apply)"  # RF and F.04; RF has no workbook cell
    code, out = run(["writeback", "--apply", "--map", str(path)], g)
    assert out[-1] == "1 cells written; recalculate the workbook before committing"
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd $R/tools && PYTHONPATH= $VENV/bin/python -m pytest tests/test_cli.py -q`
Expected: `ModuleNotFoundError: No module named 'fm_sync'`.

- [ ] **Step 3: Write `tools/fm_sync.py`**

```python
#!/usr/bin/env python3
"""Sync the feature-map workbook to GitHub issues and the org project. Dry run unless --apply."""
import argparse
import pathlib
import sys
from collections import Counter

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from fmsync import apply as ap  # noqa: E402
from fmsync import plan, workbook, writeback  # noqa: E402
from fmsync.data import PROJECT_TITLE  # noqa: E402

REQ = pathlib.Path(__file__).resolve().parents[1] / "docs" / "requirements"
MAP = REQ / "2026-10-26-feature-map-by-repo.xlsx"
SOURCE = REQ / "具身智能本体中间件_扩展功能_v1.3_withoutbudget.xlsx"
OPS = ("create_issue", "update_issue", "comment", "add_item", "set_field", "add_sub_issue")


def describe(a) -> str:
    if a.op in ("create_issue", "update_issue"):
        return f"{a.op:14} {a.key:7} {a.repo:13} {a.title}"
    if a.op == "set_field":
        return f"{a.op:14} {a.key:7} {a.field} = {a.value}"
    if a.op == "add_sub_issue":
        return f"{a.op:14} {a.key:7} under {a.parent}"
    return f"{a.op:14} {a.key}"


def main(argv=None, gh=None, out=print) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=["setup", "sync", "writeback"])
    p.add_argument("--apply", action="store_true", help="change GitHub (or the workbook, for writeback)")
    p.add_argument("--only", default="", help="comma-separated rows (F, 13, ...) or IDs (F.04, R13, ...)")
    p.add_argument("--map", default=str(MAP))
    p.add_argument("--source", default=str(SOURCE))
    a = p.parse_args(argv)
    if gh is None:
        from fmsync.github import Gh
        gh = Gh()

    if a.command == "setup":
        ap.setup(gh, a.apply, out)
        if not a.apply:
            out("dry run: nothing changed (add --apply)")
        return 0

    project = gh.find_project(PROJECT_TITLE)
    state = ap.load_state(gh, project)
    if a.command == "writeback":
        urls = {k: s.url for k, s in state.issues.items()}
        if not a.apply:
            out(f"dry run: {len(urls)} issue URLs to write (add --apply)")
            return 0
        out(f"{writeback.write_issue_urls(a.map, urls)} cells written; recalculate the workbook before committing")
        return 0

    reqs, feats = workbook.read_requirements(a.map, a.source), workbook.read_features(a.map)
    only = {x.strip() for x in a.only.split(",") if x.strip()} or None
    actions, warnings = plan.build(reqs, feats, state, only)
    for w in warnings:
        out("WARNING " + w)
    for action in actions:
        out(describe(action))
    counts = Counter(x.op for x in actions)
    out("plan: " + ", ".join(f"{op} {counts.get(op, 0)}" for op in OPS))
    if not a.apply:
        out("dry run: nothing changed (add --apply)")
        return 0
    if project is None:
        out("no project: run `fm_sync.py setup --apply` first")
        return 1
    ap.execute(gh, project, actions, state, out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd $R/tools && PYTHONPATH= $VENV/bin/python -m pytest tests -q`
Expected: `41 passed`.

- [ ] **Step 5: Commit**

```bash
cd $R && git add tools && git commit -q -m "feat(fmsync): fm_sync.py CLI (setup, sync, writeback; dry run by default)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: Bootstrap the org — `roadmap` repo, forks, pushes

This task writes to GitHub. Every command targets `dorarobotics-dev` only.

- [ ] **Step 1: Confirm the account and that the org is empty**

```bash
gh auth status 2>&1 | grep "Logged in"
gh api user/memberships/orgs/dorarobotics-dev --jq '.role+" "+.state'
gh api orgs/dorarobotics-dev/repos --jq 'length'
```
Expected: `bobdingAI`; `admin active`; `0`. If the org already has repos, stop and report them.

- [ ] **Step 2: Create `roadmap` and push it**

```bash
gh api -X POST orgs/dorarobotics-dev/repos -f name=roadmap \
  -f description="Requirements and feature tracking for the v1.3 embodied-middleware work on dora" \
  -F private=false -F has_issues=true -F has_projects=true --jq .html_url
cd $R && git remote add origin https://github.com/dorarobotics-dev/roadmap.git && git push -u origin main
```
Expected: `https://github.com/dorarobotics-dev/roadmap`; push succeeds.

- [ ] **Step 3: Fork the six code repos into the org**

```bash
for r in dora DORA_NAV dora-moveit2 dora-studio dora-hub; do
  gh api -X POST repos/dora-rs/$r/forks -f organization=dorarobotics-dev -F default_branch_only=true --jq .full_name
done
gh api -X POST repos/octos-org/octos/forks -f organization=dorarobotics-dev -F default_branch_only=true --jq .full_name
for r in dora DORA_NAV dora-moveit2 dora-studio dora-hub octos; do
  until gh api repos/dorarobotics-dev/$r --jq .full_name 2>/dev/null; do sleep 5; done
done
```
Expected: six `dorarobotics-dev/<repo>` names. (Forking writes only to `dorarobotics-dev`; the upstream repos are read.)

- [ ] **Step 4: Turn issues on in each fork**

```bash
for r in dora DORA_NAV dora-moveit2 dora-studio dora-hub octos; do
  gh api -X PATCH repos/dorarobotics-dev/$r -F has_issues=true --jq '.full_name+" issues="+(.has_issues|tostring)'
done
```
Expected: six lines ending `issues=true`.

- [ ] **Step 5: Add `dev` remotes and push the freeze tags and experiment branches**

```bash
for r in dora DORA_NAV dora-moveit2 dora-studio dora-hub octos; do
  git -C $W/$r remote add dev https://github.com/dorarobotics-dev/$r.git
  git -C $W/$r push dev maintenance-freeze-2026-11-03
done
git -C $W/dora push dev exp/contract-core
git -C $W/DORA_NAV push dev exp/contract-core
for r in dora DORA_NAV dora-moveit2 dora-studio dora-hub octos; do
  echo "$r: $(git -C $W/$r remote -v | grep push | tr '\n' ' ')"
done
```
Expected: pushes succeed; for every repo only `dev` has a real push URL (`origin`/`upstream` push = `DISABLED`).

- [ ] **Step 6: Verify on GitHub**

```bash
for r in dora DORA_NAV dora-moveit2 dora-studio dora-hub octos; do
  echo "$r tag=$(gh api repos/dorarobotics-dev/$r/git/ref/tags/maintenance-freeze-2026-11-03 --jq .object.sha | cut -c1-9)"
done
gh api repos/dorarobotics-dev/dora/branches/exp/contract-core --jq .commit.sha | cut -c1-9
gh api repos/dorarobotics-dev/DORA_NAV/branches/exp/contract-core --jq .commit.sha | cut -c1-9
```
Expected: tag SHAs `7f5595344`, `a9257f5`, `a3b509c`, `f28cb91`, `deb4f52`, `19ca7995` (annotated tags print the tag object SHA instead; then check with `git -C $W/$r rev-parse maintenance-freeze-2026-11-03` that it matches); branch heads equal `git -C $W/dora rev-parse --short=9 exp/contract-core` and the DORA_NAV equivalent.

No commit (nothing changed in `$R`).

---

### Task 11: Labels, project, fields and views

- [ ] **Step 1: Dry run**

Run: `cd $R/tools && PYTHONPATH= $VENV/bin/python fm_sync.py setup`
Expected: 7 × 20 = 140 `label …` lines, `project 'Embodied middleware v1.3'`, `fields and views follow once the project exists`, `dry run: nothing changed (add --apply)`.

- [ ] **Step 2: Apply**

Run: `cd $R/tools && PYTHONPATH= $VENV/bin/python fm_sync.py setup --apply`
Expected: the same label lines, then `Status options: …`, six `field …` lines, `view View 1 -> Overview`, 16 `view …` lines. If a GraphQL call fails because a selection-set name differs from the live schema, fix that query in `github.py`, re-run the unit tests (`41 passed`), commit the fix, and re-run this step (setup is idempotent).

- [ ] **Step 3: Re-run must do nothing**

Run: `cd $R/tools && PYTHONPATH= $VENV/bin/python fm_sync.py setup --apply`
Expected: empty output.

- [ ] **Step 4: Check on GitHub**

```bash
gh api graphql -f query='{organization(login:"dorarobotics-dev"){projectsV2(first:5){nodes{number title url views(first:30){nodes{name filter}} fields(first:30){nodes{... on ProjectV2FieldCommon{name}}}}}}}' \
  --jq '.data.organization.projectsV2.nodes[] | .url, ([.views.nodes[].name]|length), [.fields.nodes[].name]'
```
Expected: the project URL; `17`; field names include Status, Row, Target repo, Kind, Basis, Feature ID, Estimate (days).

No commit unless Step 2 needed a fix.

---

### Task 12: Live dry run of the sync

- [ ] **Step 1: Run it**

```bash
cd $R/tools && PYTHONPATH= $VENV/bin/python fm_sync.py sync | tail -3
```
Expected: `plan: create_issue 145, update_issue 0, comment 9, add_item 145, set_field <n>, add_sub_issue 131` and `dry run: nothing changed (add --apply)`, with no `WARNING` lines. `<n>` = 145 (Status) + 145 × Row/Target repo/Kind/Feature ID + 131 Basis + estimates: compute it from the output with `grep -c '^set_field'` and record it in the task report.

- [ ] **Step 2: Spot-check three rendered issues**

```bash
cd $R/tools && PYTHONPATH= $VENV/bin/python -c "
from fmsync import workbook, render
from fm_sync import MAP, SOURCE
q={x.row:x for x in workbook.read_requirements(MAP,SOURCE)}; f={x.id:x for x in workbook.read_features(MAP)}
print(render.requirement_title(q['13'])); print(render.requirement_body(q['13'])[:600]); print('---')
print(render.feature_title(f['F.04'])); print(render.feature_body(f['F.04'], q['F'].name)); print('---')
print(render.experiment_comment('13.02'))"
```
Expected: Chinese text verbatim; tables render; markers at the end.

No commit.

---

### Task 13: Apply — row F first, then everything; idempotency; write-back

- [ ] **Step 1: Apply row F only**

Run: `cd $R/tools && PYTHONPATH= $VENV/bin/python fm_sync.py sync --apply --only F 2>&1 | grep -E '^(created|updated|plan|WARNING)'`
Expected: 21 `created` lines (RF in roadmap; F.01–F.11, F.13, F.15–F.20 in their code repos; F.12 in roadmap; F.14 in octos); `plan: create_issue 21, …`.

- [ ] **Step 2: Check row F by hand on GitHub**

```bash
gh api "repos/dorarobotics-dev/roadmap/issues?state=all" --jq '.[] | "\(.number) \(.title)"'
RF=$(gh api "repos/dorarobotics-dev/roadmap/issues?state=all" --jq '.[] | select(.title|startswith("[RF]")) | .number')
gh api repos/dorarobotics-dev/roadmap/issues/$RF/sub_issues --jq 'length'
gh api "repos/dorarobotics-dev/dora/issues?state=all&per_page=100" --jq '.[] | "\(.number) \(.title) \([.labels[].name])"'
```
Expected: `[RF] 基础 · Foundation` and `[F.12] …` in roadmap; RF has 20 sub-issues; dora has F.01–F.06, F.13, F.15–F.20 with `row:F`, `kind:feature`, `status:*` labels. Open the project's "Row F" view in a browser: 21 cards; F.02 under "Done (experiment)"; F.01, F.03, F.04, F.06, F.07 under "In progress".

- [ ] **Step 3: Apply everything**

Run: `cd $R/tools && PYTHONPATH= $VENV/bin/python fm_sync.py sync --apply 2>&1 | grep -E '^(plan|WARNING)'`
Expected: `plan: create_issue 124, update_issue 0, comment 3, add_item 124, …, add_sub_issue 111`; no warnings. (124 = 145 − 21; comments 13.01, 13.02, 13.17; sub-issues 131 − 20.)

- [ ] **Step 4: Idempotency**

Run: `cd $R/tools && PYTHONPATH= $VENV/bin/python fm_sync.py sync | tail -2`
Expected: `plan: create_issue 0, update_issue 0, comment 0, add_item 0, set_field 0, add_sub_issue 0`.

- [ ] **Step 5: Write the URLs back, recalculate, commit and push**

```bash
cd $R/tools && PYTHONPATH= $VENV/bin/python fm_sync.py writeback --apply
$VENV/bin/python /home/demo/.claude/skills/synced/d6864d6a-bc5f-4c46-b8d4-c94b7fcf1b33_af86715d-ddd4-4f91-a212-c09a3aa18791/xlsx/scripts/recalc.py $R/docs/requirements/2026-10-26-feature-map-by-repo.xlsx
cd $R/tools && PYTHONPATH= $VENV/bin/python -m pytest tests -q
cd $R && git add docs/requirements/2026-10-26-feature-map-by-repo.xlsx && git commit -q -m "docs(workbook): issue URLs from the first sync

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" && git push
```
Expected: `131 cells written; …`; recalc success with 0 errors; `41 passed`; push succeeds.

---

### Task 14: Manual grouping, final check, handoff

- [ ] **Step 1: Group the two table views (by hand, in the browser)**

In the project (URL from Task 11 Step 4):
1. Open view **Overview** → view menu (▾ next to the view name) → **Group by** → **Row**. Then **Fields** → show **Sub-issues progress**, **Status**, **Target repo**, **Kind**, **Estimate (days)**. Click **Save**.
2. Open view **By repo** → **Group by** → **Target repo**; show **Status**, **Row**, **Basis**. **Save**.

- [ ] **Step 2: Final check**

```bash
for r in roadmap dora DORA_NAV dora-moveit2 dora-studio dora-hub octos; do
  echo "$r $(gh api "repos/dorarobotics-dev/$r/issues?state=all&per_page=100" --paginate --jq '.[] | select(.pull_request==null) | .number' | wc -l)"
done
```
Expected: roadmap 30 (14 requirements + 16 deliveries), dora 60, DORA_NAV 30, dora-moveit2 12, dora-studio 4, dora-hub 5, octos 4 (total 145).

- [ ] **Step 3: Update the handoff and folder notes**

In `$W/.claude-handoff/HANDOFF.md`, add under "Where things are":

```markdown
- Tracking: org `dorarobotics-dev` — repo `roadmap` (workbooks, docs, `tools/fm_sync.py`), forks dora, DORA_NAV,
  dora-moveit2, dora-studio, dora-hub, octos (issues on; `dev` remote in each local copy), project
  "Embodied middleware v1.3" (145 issues). Docs moved from `$W/docs` to `$W/roadmap/docs`.
```

In `$W/CLAUDE.md`, add to the opening paragraph: ``Docs, workbooks and the issue-sync script are in `roadmap/` (pushed to dorarobotics-dev/roadmap); edit the workbook there and run `tools/fm_sync.py sync`.`` and replace the rule ``Never push (push URLs are disabled on purpose); ask first.`` with ``Push only to the `dev` remote (dorarobotics-dev), and only when asked; `origin`/`upstream` push stays disabled.``

- [ ] **Step 4: Commit and push `roadmap` if anything changed there**

```bash
cd $R && git status --short && git log --oneline origin/main..HEAD
```
Expected: clean, nothing unpushed.
