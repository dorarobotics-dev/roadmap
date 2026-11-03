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
sets Status only when an issue first enters the project (or is in the project
without any Status, e.g. after an interrupted run). Requires `gh` logged in with
write access to `dorarobotics-dev`, and Python with openpyxl.

Issues are found by a hidden marker `<!-- fm:<ID> -->` in their body; the
experiment comment carries `<!-- fm-comment:<ID> -->`, so it is posted once and
re-posted only if it is missing. Re-running after an interruption finishes what
was left out. Things to know:

- **The workbook wins.** Title and body edits made on GitHub are overwritten by
  the next `sync`. Discuss in comments; change text in the workbook.
- **Labels are only added** (compared ignoring case), never removed. When a
  feature's status changes in the workbook, the old `status:*` label stays on
  the issue; remove it by hand.
- **Removing an issue from the project** and running `sync` again adds it back
  with Status reset to its start value (Todo, or the experiment status).
- **Moving a feature to another row is not supported**: the sync does not
  unlink the old parent, so adding the issue under the new requirement fails
  (GitHub allows one parent). Remove the old sub-issue link by hand, then run
  `sync` again. Moving a feature to another repo stops the sync with an error.
- `setup` re-applies a view's filter when it differs from the one in
  `tools/fmsync/data.py`; grouping is set by hand.

## Acceptance

The general acceptance rule (统一验收要求) is in the `delivery` sheet of the v1.3
workbook; each requirement issue quotes its own row's criteria.
