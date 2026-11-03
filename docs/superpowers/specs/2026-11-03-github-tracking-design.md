# GitHub tracking for the v1.3 feature map — design

Date: 2026-11-03. Account: `bobdingAI` (admin of `dorarobotics-dev`). Status: approved in brainstorming, awaiting spec review.

## Goal

Track every requirement and PR-sized feature of the v1.3 embodied-middleware work as GitHub issues in the org
[`dorarobotics-dev`](https://github.com/orgs/dorarobotics-dev), organised in one GitHub Project, with the
feature-map workbook as the single source of truth.

Sources:

- `docs/requirements/2026-10-26-feature-map-by-repo.xlsx` — 123 features (dora 53, DORA_NAV 30,
  dora-moveit2 12, dora-studio 4, octos 3, dora-hub 5, delivery 16) across 14 requirement groups (F, 13–25).
- `docs/requirements/具身智能本体中间件_扩展功能_v1.3_withoutbudget.xlsx` — original requirement text
  (`functions` sheet) and acceptance criteria (`delivery` sheet).
- `dora/docs/contract-core/feasibility.md` — effort estimates, corrections, "did not fit" list.

## Decisions (from brainstorming)

| Question | Decision |
|---|---|
| Where issues live | Mixed: requirement issues in a tracking repo; feature issues in the code repo that will close them, as sub-issues |
| Projects | One org project with views (not one per row) |
| Code repos in the org | GitHub forks of upstream; push the freeze tag and experiment branches |
| Granularity | One issue per feature row |
| Maintenance | Re-runnable script; the workbook is the source of truth |

## 1. Org layout

- **`dorarobotics-dev/roadmap`** (new): holds the 14 requirement issues and 16 delivery issues, plus the
  workbooks (`docs/requirements/`), the superpowers docs (`docs/superpowers/`) and the sync script (`tools/`).
  Visibility matches the forks (public, since the forks of public repos are public).
- **Six forks:** `dora`, `DORA_NAV`, `dora-moveit2`, `dora-studio`, `dora-hub` (from `dora-rs`) and `octos`
  (from `octos-org`). Issues are switched on in each (forks start with them off). `octos-dora-bridge` is not
  forked: the plan does not change it, and it already lives under `dorarobotics`.
- **Pushed to each fork:** tag `maintenance-freeze-2026-11-03`. Branch `exp/contract-core` only for `dora`
  and `DORA_NAV` (the other four have no experiment commits). dora's branch is pushed as it is (based on
  `1016eab0a`, 107 commits behind the tag); the rebase is tracked as its own feature issue. octos's local
  branch comes from a clone that diverged from upstream and is not pushed.
- **Local copies** (`~/Public/github_dorarobotics_dev/<repo>`): add remote `dev` → the fork. Only `dev` has a
  push URL; `origin` and `upstream` push stay `DISABLED`.
- **Labels**, identical in all seven repos: `row:F`, `row:13` … `row:25`; `status:new`,
  `status:basis-exists`, `status:built-to-move`; `kind:requirement`, `kind:feature`, `kind:delivery`.

## 2. Issues

| Level | Repo | Count | Title | Body |
|---|---|---|---|---|
| Requirement | roadmap | 14 | `[R13] 感知类算子 · Perception operators` (`[RF] 基础 · Foundation`) | Chinese national requirement and expansion text verbatim (`functions` sheet; none for F); English summary (`Rows` sheet); acceptance criteria verbatim (`delivery` sheet); effort estimate where the feasibility report gives one |
| Feature | code repo of the sheet | 107 (+ additions) | `[F.04] <Feature (one PR)>` | Feature, package/location, status, existing basis, notes, link to its requirement issue |
| Delivery | roadmap | 16 | `[<ID>] <Feature>` | Same fields as a feature |

- Feature and delivery issues are **sub-issues** of their requirement issue.
- Every issue body ends with a hidden marker `<!-- fm:<ID> -->` (requirements: `<!-- fm:R13 -->`); the
  script finds issues by marker, never by title.
- Labels: `row:*`, `kind:*`, and for features and deliveries `status:*`.
- **Experiment-built items** (status "built, to move" that `exp/contract-core` implemented) get a comment
  listing the commits and test evidence from `feasibility.md`.
- **Correction** applied to the workbook before sync: F.05 "new" → "basis exists", existing basis
  "dora master has action and service patterns (`goal_id`, `request_id`)". (F.03 is already "basis
  exists" in the workbook; its notes gain "frame, rate and max-age remain".)
- **Added features**, written into the workbook first (same ID scheme, next free number in the right sheet):
  rebase dora `exp/contract-core` onto the freeze tag (dora, row F); plan octos work against upstream main
  (octos, row F); one per "did not fit" item in `feasibility.md` that implies an upstream change (sheet and
  row chosen per item; the list is fixed in the plan).
- Language: requirement titles bilingual; feature titles English as in the workbook; Chinese source text
  quoted verbatim, never machine-translated.

## 3. Project

One org project, **"Embodied middleware v1.3"**, containing every issue above.

| Field | Type | Values |
|---|---|---|
| Status | single-select (built-in) | Todo · In progress · In review · Done (experiment) · Done |
| Row | single-select | `F 基础 Foundation`, `13 感知类算子 Perception`, … `25 采集系统 Motion capture` |
| Repo | single-select | dora, DORA_NAV, dora-moveit2, dora-studio, octos, dora-hub, roadmap |
| Kind | single-select | requirement · feature · delivery |
| Basis | single-select | new · basis exists · built, to move |
| Feature ID | text | e.g. `F.04`, `R13` |
| Estimate (days) | number | only where `feasibility.md` gives a figure |

- Status is set **only on create**: "Done (experiment)" for experiment-built items, otherwise "Todo".
  Later runs never change Status.
- Views, created by `fm_sync.py setup` through `createProjectV2View`/`updateProjectV2View` (name, layout,
  filter): Overview (table), 14 per-row boards (filter on Row; board columns default to Status), By repo
  (table), Delivery (table, filter Kind = delivery or requirement). Group-by cannot be set through the API:
  Overview (group by Row) and By repo (group by Repo) are grouped by hand once.
- Items the experiment delivered in part start as "In progress" (fully delivered: "Done (experiment)").

## 4. Sync script

`roadmap/tools/fm_sync.py [--dry-run | --apply] [--only <IDs>]`, Python 3.11 + openpyxl, calling GitHub
through `gh api` (REST and GraphQL; local gh 2.4 has no `gh project`), so no token is stored.

| Module | Responsibility |
|---|---|
| `workbook.py` | Read the by-repo workbook and the v1.3 `functions`/`delivery` sheets into records. Refuse duplicate IDs, unknown repo or row, empty title |
| `plan.py` | Pure: records + current GitHub state → ordered actions (create issue, update body/labels, add to project, set field, add sub-issue). Status only on create |
| `github.py` | Thin named wrappers: `find_by_marker`, `create_issue`, `update_issue`, `add_sub_issue`, `add_project_item`, `set_field`, … |
| `writeback.py` | Write each issue URL into the workbook's `Issue / PR` column only; formulas and formatting untouched |

Safety rules:

- Dry run is the default; `--apply` is required for any write. The dry run prints the plan and counts.
- Idempotent: match by marker; write sub-issue links and field values only when they differ. A second
  `--apply` straight after the first must plan 0 actions.
- Never deletes or closes. Features missing from the workbook are reported, not touched.
- Owner fixed to `dorarobotics-dev`; any other owner is refused.
- Rate limits: back off on 403/429; pause ~1 s between issue creations (secondary limit on content creation).

Bootstrap (once, by hand, before the first sync): create `roadmap`, the six forks, enable issues, create
labels, add `dev` remotes, push tags/branches, create the project, its fields and views (the script does
labels, project, fields and views; repos and pushes are explicit commands in the plan).

## 5. Testing

- Unit tests (pytest, no network): workbook parsing against the real xlsx (counts per sheet, 14 groups,
  refusal cases with doctored copies); plan generation against fake GitHub state — create, already exists,
  changed body, Status preserved, removed feature reported, bad workbook refused.
- Live dry run against the empty org: planned issue counts equal workbook counts (14 + 107 + 16 + added).
- First apply limited to row F with `--only`, checked by hand on GitHub; then all rows; then a second
  `--apply` must report 0 actions.

## Out of scope

- Implementing any feature; pushing anything to `dora-rs`, `octos-org` or `dorarobotics`.
- Setting a view's group-by through the API (not supported; two views are grouped by hand).
- Syncing status from GitHub back into the workbook (only issue URLs are written back).
