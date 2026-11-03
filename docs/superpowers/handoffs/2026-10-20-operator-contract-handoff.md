# Handoff — 自主算子开发, sub-projects 0 and 1 complete

Date: 2026-10-20
From: macOS session (`/Users/Shared/hexin_dora` as working directory)
To: asus (10.10.5.7), `/home/demo/Public/github_dimos/open-robot-stack-operator-contract`
Read with: `docs/superpowers/specs/2026-10-20-operator-contract-and-data-processing-design.md`
(the design, §11 is the latest amendment) and
`docs/superpowers/plans/2026-10-20-operator-contract-and-data-processing.md` (17 tasks).

## 1. State

| Thing | Where | State |
|---|---|---|
| `feat/operator-contract` | pushed, **PR #1 → main**, MERGEABLE | 14 commits, 78 files, +16661. Head `26b39c5` |
| `feat/edge-inference-transparency` | pushed 2026-10-20 (first time) | 32 commits, +8057. Head `0de2f76`. **Incomplete — no PR on purpose** |
| Tender workbook | `outputs/operators_20261020/具身智能本体中间件_扩展功能_v1.3.xlsx` | v1.3 delivered; not in git, copied by hand |

Verified before the PR: contract layer **308** tests, pack **349**, normative
specs **66**, mutation sweep **0/10 surviving**. Both dataflows run end to end
under real dora 1.0.1. Cross-checked on asus (numpy 1.26→2.2, pyarrow 24→25):
byte-identical per-file test counts and byte-identical record ratios.

## 2. What was built

Sub-project 0 (contract layer, not separately priced) and sub-project 1
(data-processing pack, contract item 16, 28万).

- `packages/open-robot-operator/` — `Header`/`derive`, `Counters`,
  `operators.yaml` declarations, the pre-launch validator, the node
  bookkeeping layer (`node.py`), wire helpers.
- `specs/operators/` — frame, unit and eight payload dictionaries.
- `capabilities/data-processing/` — seven operators (point-cloud / image /
  state filtering, point-cloud / image compression, cleaning, ROS 2 codec),
  two tools (`diag_collector`, `ab_compare`), three mocks, two runnable
  dataflows, two delivered records.

Two invariants are enforced, not documented: a degraded message is forwarded
with its validity rather than dropped, and only the operator that repaired a
defect may raise a validity.

## 3. The commercial side, which changed after the code shipped

The tender workbook went v1.2 → **v1.3** on 2026-10-20. Column G (国家要求,
the actual obligation) is unchanged in all thirteen items and **no price
moved** (items 13–16 = 58/66/48/28 = 200万; 17–25 = 382万; total 582万). What
narrowed is column H and the delivery sheet for items 13–16, which had
promised work column G never asked for. Spec §11 records all nine changes.
The four that matter here:

- Item 13 no longer promises long-term tracking with lifecycle-tagged tracks,
  only nearest-neighbour association between adjacent frames.
- Item 13 no longer re-delivers downsampling and outlier rejection; the
  workbook now says item 16 provides them. This is the boundary spec §5.1
  already drew — the contract text caught up to the plan.
- Item 15 delivers one best trajectory with a confidence, not multiple
  candidates with probabilities, and its upstream is now the perception
  operators' target list plus the motion-capture system's keypoints (item 13
  never produced keypoints).
- Item 16's compression reports the achieved ratio per diagnostics period.
  `ratio_target` never existed in the code.

Acceptance floors came down too (100 frames → 50, five plans → three, ten IK
poses → five, three collaboration scenarios at ten trials → one at five).
Item 16's floors are unchanged: it is built and verified, so lowering them
buys nothing.

**Scope fell and the money did not, so margin rose unevenly — item 15 shed the
most risk. `填表注意事项` item 十一 flags the 200万 internal split as not yet
work-estimated.**

## 4. Next steps, in the order they were agreed

1. ~~Push the edge-inference branch; open the PR~~ — done 2026-10-20.
2. ~~Pin `dora-nav` and `dora-moveit2`~~ — done, `26b39c5`.
3. **Coordinate transformation: brainstorming → spec.** This is the next
   design task. §9's frame-handling decision cut transformation from the
   contract layer ("declare and check, never transform"), and v1.3 keeps
   item 13's "输出统一坐标系下的融合结果". So **nothing currently owns
   transformation**, and it is the largest unestimated piece of work in
   13–16. Open questions: where the TF tree lives (capability pack? library
   in `open-robot-operator`? reuse ROS 2 tf2 through the interop codec?),
   who publishes transforms, static vs dynamic, and how it relates to
   `specs/operators/frames.yaml`.
4. **Migrate one existing node chain onto the contract.** The cheapest real
   test of the contract and the shared prerequisite of sub-projects 2 and 3.
   Candidate: dora-nav's `peception/euclidean_cluster` chain. See §5.
5. **Finish the edge-inference branch** — Task 9's `config.schema.json`
   amendment unapplied, Tasks 10, 11, 13 un-run, Task 12 permanently not-run.
   Item 15 now depends on this branch per v1.3.

Sub-project order in spec §10 is 2 (perception, 13) → 3 (control, 14) →
4 (cognition, 15). Worth revisiting: after v1.3, item 14 is explicitly
"封装增强，不含新算法研制" over existing code while item 13 carries the TF
tree, so the shared migration in step 4 should come before the split.

## 5. What reading the upstreams turned up — plan around this

`dora-nav` and `dora-moveit2` are now pinned in `component-lock.yaml`
(revision + branch + version; `digest` stays `unresolved`, which is the
house convention — no entry in that file has a resolved digest).

**dora-nav's message set has forked inside the repo.** `Request_h` exists in
two layouts:

- `include/Planning.h` — four control-state constants as `uint8_t` **data
  members** with defaults, so 20 bytes and each instance carries mutable
  "constants".
- `control/include/Planning.h` — the same four as an `enum ControlState`
  outside the struct, so 16 bytes.

Same name, same repo, two sizes. A node built against one cannot exchange
`Request_h` with a node built against the other. `Localization.h` differs too
(the top-level copy declares a `CurPose_h` the control copies lack). The
migration has to pick one layout per message, not wrap both.

**dora-nav writes no dora metadata at all.** Of the 11 `metadata=` sites
across both repos, ten are dora-moveit2 and the eleventh is vendored YOLOv5
wandb code. So the migration *introduces* a convention on the navigation
side rather than replacing one — a different job from what spec §1 assumed.

**dora-moveit2's convention is absorbable.** Its ten writes are ad-hoc flags
(`success`, `encoding`, `num_waypoints`, `num_joints`, `version`,
`in_collision`, `dual`). None collide with the envelope's reserved keys, so
`header_to_metadata` takes them as extras.

**One silent-corruption site to kill:**
`dora_moveit/trajectory_execution/trajectory_executor.py:185` reads
`metadata.get("num_waypoints", len(traj_flat) // executor.num_joints)` — if
the producer omits the field, the consumer *computes a plausible value*
instead of refusing. Same defect family as the hard-coded frame at
`peception/euclidean_cluster/LidarRawObject_to_ros2.py:95`, which is still
there.

## 6. Environment on asus

```bash
cd /home/demo/Public/github_dimos/open-robot-stack-operator-contract
source /home/demo/Public/github_dimos/.venv-ors-operator/bin/activate
```

Python 3.10.12, numpy 2.2.6, pyarrow 25.0.1, scipy 1.15.3, Pillow 12.3.0,
zstandard 0.25.0, pyyaml 6.0.3, jsonschema 4.26.0, pytest 9.1.1, dora-rs
1.0.1 wheel with a matching CLI (`~/.local/bin/dora`, also in the venv).

Run the three suites:

```bash
python -m pytest packages/open-robot-operator/tests -q
python -m pytest capabilities/data-processing/tests -q
python -m pytest tests/test_specs.py -q
python tools/mutation-sweep.py          # expect 0/10 surviving
```

Run a dataflow for real:

```bash
cd capabilities/data-processing
dora up && dora run dataflows/preprocess-chain.yml && dora destroy
```

`dataflows/node.sh` resolves both package roots from its own location, so
there are no machine-specific paths in the manifests.

### Where the workbook lives on asus

Copied 2026-10-20, md5-verified: `/home/demo/Public/hexin_dora/` with the
deliverables under `outputs/operators_20261020/`. Twelve workbooks in all,
including the user's own two v1.3 derivatives made after the fact —
`具身智能本体中间件_扩展功能_v1.3_withbudget.xlsx` and `..._withoutbudget.xlsx`,
which carry identical H2:H5 text to the delivered v1.3 and differ only in
whether column I is filled.

Workbook editing on asus uses **system python3**, not the ORS venv: the venv
has no openpyxl, system python3 has 3.0.9 (the Mac had a newer one, so check
style-copy behaviour if it matters). `soffice` is at `/usr/bin/soffice` for
formula recalculation, same as the Mac flow.

The dora upstreams are **not on asus**: on the Mac they sit at
`/Users/Shared/github_dora/{dora-nav,dora-moveit2}` (915M and 232M). The
checkouts there track `bobdingAI/*` forks; the canonical URLs are
`github.com/dora-rs/DORA_NAV.git` and `github.com/dora-rs/dora-moveit2.git`,
and whether the pinned revisions are reachable from dora-rs is **not
verified**. Step 4 needs them cloned or copied onto asus first.

## 7. Traps that already cost time

- Never run the mutation sweep alongside anything else that runs tests in the
  same worktree, and clear `__pycache__` between runs. A killed sweep can
  leave a source file mutated; check with the anchor count, not the
  mutated-form column (two replacements are substrings of their own anchors).
- `yaml.safe_load` cannot read `DORA_NODE_CONFIG` — it carries `!Tcp` tags.
  Use `open_robot_operator.node._TagTolerantLoader`.
- dora metadata carries flat scalars only in all existing code. Nested dicts
  are not known to survive.
- A dora node with no inputs receives no events, so it silently sends nothing
  and the dataflow hangs with no clue. Source nodes need a
  `builtin: timer` port.
- macOS `tar` writes AppleDouble `._*` files into every archive. Use
  `COPYFILE_DISABLE=1`.
- Substring scans in tests are a recurring defect class here — two were
  found. Walk the AST and pin the scan itself with its own test.

## 8. Facts not derivable from the repo

- The tender workbook lives outside git at
  `/Users/Shared/hexin_dora/outputs/operators_20261020/` on the Mac. Its
  source, `具身智能本体中间件_扩展功能_v1.1.xlsx具身智能本体中间件_扩展功能_v1.1.xlsx`,
  has a literally doubled filename (48 chars). Deliberately not renamed.
- WPS Office stays open on the Mac. Saving the workbook from WPS overwrites
  what a script wrote.
- Assurance here is mutation testing, not coverage. Branch coverage was
  proven insufficient on the inference path, where a doubly-wrong gate passed
  a fully covered test.
