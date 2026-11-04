# Detailed requirement background in the tracking issues

> **Status:** Approved design, ready for planning
> **Date:** 2026-11-03
> **Builds on:** `2026-11-03-github-tracking-design.md` (the `fm_sync` tool and the 145 issues it made)

## 1. Purpose

Every issue made by `fm_sync` in dorarobotics-dev — 14 requirement issues in `roadmap` and 131
feature and deliverable issues across the code repos — carries only a generated table: location,
status, basis, notes, and for requirements the acceptance criteria. A developer picking one up
cannot tell why it exists, what "done" looks like in practice, or what interface to build.

This design adds four hand-written sections to every issue and changes the sync so it never
overwrites them:

1. **Summary**
2. **Use case / Why** — the real scenario: who hits the problem, what workflow it unlocks, the pain
   today. Not "I want a function".
3. **Proposed expected behavior** — what happens once the feature lands. Concrete and checkable.
4. **Proposed API / Design** — the proposed interface.

All text is in English. The Chinese requirement text stays quoted verbatim in the requirement
issues, as today.

## 2. Decisions

| Question | Decision |
|---|---|
| Language | English |
| Depth of API / Design | A researched proposal for every feature: signatures, dataflow ports and message types, CLI or config keys, the ROS 2 equivalent, and the existing code it builds on |
| Where the text lives | On GitHub. The issue body is the source for the prose; the sync owns only a delimited block |
| Who writes the first version | 14 research agents, one per requirement row, checked automatically and by 3 reviewers |

## 3. Issue body layout

```markdown
## Summary
…
## Use case / Why
…
## Proposed expected behavior
…
## Proposed API / Design
…

<!-- fm:begin -->
## Tracking
… generated content: today's table, or for a requirement the acceptance and 中文 sections …
<!-- fm:13.02 -->
<!-- fm:end -->
```

- Everything above `<!-- fm:begin -->` is the **prose area**. The sync never reads it for
  comparison and never changes it. Anyone may edit it on GitHub.
- The **managed block** runs from `<!-- fm:begin -->` to `<!-- fm:end -->` and sits at the end of the
  body. It holds the generated content under a `## Tracking` heading, and the `<!-- fm:ID -->`
  marker that identifies the issue. Title and labels stay sync-owned, as today.

### 3.1 Sync behaviour

- `render.requirement_body` and `render.feature_body` produce the managed block only (wrapped in the
  begin/end markers). A new `render.compose(prose, block)` joins the prose area and the block with
  one blank line; an empty prose area yields the block alone.
- A new `render.split(body)` returns `(prose, block)`:
  - both markers present, in order, once each → the text before `fm:begin` (trailing whitespace
    stripped) and the block up to and including `fm:end`;
  - neither marker present → `(None, body)`: a **legacy** body from before this change;
  - anything else (one marker without the other, either twice, `fm:end` before `fm:begin`) →
    `LayoutError` naming the issue (`repo#number`, key).
- `plan.build` compares `normalize(block)` against the rendered block, plus title and labels as
  today. Editing only the prose plans nothing.
- An update sends `compose(existing prose, new block)`. A legacy body was wholly generated, so
  its prose is taken as empty: the first sync after this change rewrites all 145 bodies once into
  the new layout.
- `find_marker` keeps working on the whole body, so loading issues is unchanged.
- An issue whose prose area contains `fm:begin`, `fm:end` or an `fm:ID` marker is refused: this
  can only happen through a bad hand edit, and silently guessing would lose text.
- Known limit: an update writes the prose it read at load time. A prose edit made on GitHub in the
  seconds between `load_state` and the update would be lost. Updates are rare (only when the
  workbook changes), so this is recorded rather than locked against.

### 3.2 Posting the prose: `fm_sync.py prose`

```
fm_sync.py prose <drafts-dir> [--apply] [--only ID,ID]
```

- Reads every `*.md` file in `<drafts-dir>`. Each file holds sections headed `# <ID>` (`# R13`,
  `# 13.02`, `# RF`, `# F.01`), and each section holds exactly the four `##` headings of §1, in
  order.
- For each ID it finds the issue by marker. It writes only when the issue's prose area is empty;
  an issue already in the new layout with prose, or still in the legacy layout, is skipped with a
  message (`prose` runs after the layout migration, see §5).
- Refuses before writing anything if: an ID is not in the workbook, an ID appears twice, a
  section lacks a heading or has an extra `##` heading, or a section contains marker text.
- Dry run by default: prints one line per issue it would write or skip.
- Writes with `update_issue(repo, number, title, compose(prose, block), labels)`, keeping title and
  labels exactly as they are on GitHub.

### 3.3 Tests

The existing 61 tests stay and are updated to the new layout. New tests, against `FakeGh`:

- prose survives a sync: write prose, change the workbook-derived content, sync, prose unchanged and
  block updated;
- prose-only edits plan 0 actions;
- a legacy body is migrated to the new layout with an empty prose area, then plans 0 actions;
- `split` refuses: only `fm:begin`; only `fm:end`; `fm:end` before `fm:begin`; markers twice;
  a marker in the prose;
- `prose`: dry run changes nothing; `--apply` fills empty prose areas; an issue with prose is
  skipped; unknown ID, duplicate ID, missing heading and marker text are each refused before any
  write; `--only` limits the IDs.

## 4. Writing the content

### 4.1 Research

14 agents run in parallel, one per row: F, 13, 14, … 25. Each receives:

- the row's Chinese requirement text and acceptance criteria (from the v1.3 source workbook) and
  the English acceptance summary;
- the row's feature entries from `2026-10-26-feature-map-by-repo.xlsx`: ID, title, repo,
  location, status, basis, notes;
- the earlier designs in `roadmap/docs/superpowers/` (operator contract, coordinate
  transformation, contract-core into dora, and their plans) and the experiment's
  `docs/contract-core/feasibility.md` on dora `exp/contract-core`;
- read access to the local repo copies under `~/Public/github_dorarobotics_dev/`.

Each writes one file, `<drafts-dir>/<row>.md`, with a `# <ID>` section for the requirement
(`R13`, `RF`) and one for every feature and deliverable in the row.

Content rules:

- **Summary:** 1–3 sentences.
- **Use case / Why:** a concrete scenario in this stack — a mobile base navigating with
  DORA_NAV, an arm with dora-moveit2, a sensor pipeline into perception, an agent calling the robot
  through octos — naming who is affected and what is painful or impossible today.
- **Proposed expected behavior:** concrete, observable outcomes. Numbers come only from the
  requirement's acceptance criteria; none are invented.
- **Proposed API / Design:**
  - the interface: function or class signatures, dataflow YAML with ports and message types, CLI
    commands, or config keys;
  - the ROS 2 equivalent it mirrors, where one exists;
  - the existing code it builds on, cited as `repo:path`. Every cited path must exist on the
    branch the issue targets (`main`/`master`, or `exp/contract-core` for experiment work);
  - ends with: *Proposed — confirm in the design review before implementing.*
- **Experiment features** (the 9 in `EXPERIMENT`) state what `exp/contract-core` already delivers
  and what is left, consistent with the experiment comment on the issue.
- **Deliverables** (records, reports, docs) describe the artefact, who consumes it and what it
  must contain, in place of an API; the API / Design heading holds the artefact's structure.
- **Requirement issues:** Summary, Use case and Expected behavior from the requirement text and
  acceptance criteria; API / Design is a map of how the row's features fit together and in what
  order.
- Length: 250–600 words per feature section, up to 900 for a requirement section.
- Nothing outside the workbook's features (for example POI, ThingsBoard, D1Max, jiuwensymbiosis).

### 4.2 Checking

A check script (in the scratchpad, not the repo) runs on every draft:

- the structure rules of §3.2;
- every ID of the row has a section and no other ID appears;
- every `repo:path` citation exists on the named branch (`git cat-file -e`);
- word counts within §4.1's limits;
- none of the excluded terms appear.

Then 3 independent reviewer agents, about 5 rows each, check claims against the code and the
requirement text: invented APIs, invented numbers, wrong ROS 2 equivalents, use cases that do not
fit the feature. Findings go back to the drafts; the check script runs again after every fix.

## 5. Rollout

1. Land the layout change (§3.1) and `prose` (§3.2) with tests, in `roadmap`.
2. `fm_sync.py sync` dry run: expect 145 `update_issue` and nothing else. Then `--apply`.
3. `fm_sync.py sync` again: expect 0 actions.
4. Research, check and review the drafts (§4).
5. `fm_sync.py prose <drafts-dir>` dry run: expect 145 writes, 0 skips. Then `--apply`.
6. `fm_sync.py sync`: expect 0 actions. Spot-check one requirement, one feature, one experiment
   feature and one deliverable on GitHub.
7. Update `roadmap/README.md`: the body layout, that the prose area is edited on GitHub, and the
   `prose` command.

## 6. Out of scope

- Keeping the prose in the repo. GitHub's per-issue edit history is the record; the drafts stay in
  the session scratchpad.
- Rewriting prose that already exists (`prose` only fills empty areas).
- Translating the prose into Chinese.
- The tier question (core / standard nodes / extras) raised for 16.01–16.03; the prose describes
  each feature at the location the workbook gives today.
