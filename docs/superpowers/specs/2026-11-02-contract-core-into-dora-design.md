# Contract core into dora: feasibility experiment

Date: 2026-11-02
Source requirement: `docs/requirements/2026-10-26-feature-map-by-repo.xlsx`, items F.01–F.04, F.06, F.07, 13.01, 13.02, 13.17.

## 1. Goal

Prove, with local changes to copies of the upstream repos, that the operator
contract can live inside dora itself: header metadata, validity rules, frames
and the transform library in dora core, checked by `dora validate`, used by a
frame_transform node, and emitted by the DORA_NAV MuJoCo sim. Nothing is pushed.

This is the first of several slices. Later slices, each with its own spec:
perception nodes (row 13), agent path (octos, octos-dora-bridge, client API),
data processing (row 16), navigation and arm adoption (rows 14, 19).

## 2. Findings that shape the design

dora already has, at `1016eab0a`:

- A standard type library, `libraries/core/types/std/{core,math,control,media,vision}/v1.yml`,
  with `std/math/v1/Pose`, `Transform`, `std/media/v1/PointCloud`, `Image`,
  `std/control/v1/Odometry`. A type can declare parameters and required
  metadata keys (`MetadataDef`).
- Port annotations `output_types`, `input_types`, `output_metadata` and
  `pattern` in the dataflow descriptor, checked by `dora validate --strict-types`.
- Service and action patterns: `pattern: action-server` requires `goal_id` and
  `goal_status`. Feature-map item F.05 ("no action concept") is wrong and is
  re-scoped in a later slice.
- Node manifests (`dora-node.yml`) with typed ports, resolved by `dora build`.
  F.03 extends these rather than adding a new declaration format.
- Typed metadata parameters (`Bool`, `Integer`, `Float`, `String`, lists,
  `Timestamp`) in `libraries/message/src/metadata.rs`.
- No way for a C node to send metadata: `dora_send_output` has no parameter
  argument. C++ has `send_output_with_metadata`.

The contract therefore extends this system. It does not add a second schema
system next to it.

## 3. Workspace

Each repo is cloned (`git clone`, own `.git`) into `/home/demo/Public/github_dimos/`
and gets a branch `exp/contract-core` cut at the listed commit. `origin` is the
local source checkout; `upstream` is the GitHub URL, fetch only. Nothing is pushed.

| Copy | From | Commit | Changed in this slice |
|---|---|---|---|
| `dora` | `~/Public/github_dora/dora` | `1016eab0a` | yes |
| `DORA_NAV` | `~/Public/github_dora/DORA_NAV` | `a9257f5` | yes |
| `dora-moveit2` | `~/Public/github_dora/dora-moveit2` | HEAD at copy time | no |
| `dora-hub` | `~/Public/github_dora/dora-hub` | HEAD at copy time | no |
| `octos` | `~/Public/github_octos-org/octos` | HEAD at copy time | no |
| `dora-studio` | `github.com/dora-rs/dora-studio` | `main` at copy time | no |
| `octos-dora-bridge` | `github.com/dorarobotics/octos-dora-bridge` | `main` at copy time | no |

Isolation:

- The experiment dora is built with `cargo build` and installed with
  `maturin develop` into `/home/demo/Public/github_dimos/.venv-exp`. The system
  `dora` 1.0.1 and the conda environments are not modified.
- Live runs use their own `dora up` with `DORA_COORDINATOR_PORT=6113` and a
  matching non-default daemon port. The shared coordinator on 6013 is never
  stopped, destroyed or sent a dataflow.
- DORA_NAV's Python sim is installed into `.venv-exp` against the experiment
  dora. DORA_NAV's C++ nodes are not built in this slice.

The Python package `packages/open-robot-operator` in this worktree (439 tests)
is the behavioural reference. Every Rust or Python test written in the copies
traces back to a reference test through a mapping table (section 8).

## 4. Changes in dora

### 4.1 Header (`libraries/message/src/header.rs`)

- Key constants: `frame_id`, `stamp_ns`, `seq`, `source`, `validity`, `reason`,
  `child_frame`.
- `enum Validity { Ok, Missing, Stale, Unpaired, LowConfidence, Rejected }`,
  serialised as the snake_case strings the reference uses.
- Read and write helpers over `MetadataParameters`. A read of a missing or
  wrongly typed key returns an error naming the key; it never defaults.
- `derive(inputs) -> Validity`: the output is the worst input validity. Only an
  operator that explicitly repairs may upgrade, and it must say so through a
  separate `repair()` call that sets `reason`.

### 4.2 Required keys on std types

`libraries/core/types/std/media/v1.yml` and `std/math/v1.yml`:

- `PointCloud`, `Image`: `metadata: [frame_id, stamp_ns]`.
- `Pose`, `Transform`: `metadata: [frame_id, child_frame, stamp_ns]`.

`PointCloud` gains a `fields` type parameter (default `xyz`; `xyzi` used here)
so the layout of `points` (packed float32) is declared, not guessed.

### 4.3 Frame annotations and frames file (descriptor)

- Node fields `output_frames` and `input_frames`, maps from port id to one of:
  a frame name, `any`, `same_as:<input id>`, `env:<VAR>`. `env:` resolves from
  the node's `env:` block; a missing variable, or a value of `any`, `none`,
  `same_as:` or `env:`, is an error.
- Dataflow top-level key `frames: { dictionary: <path>, extrinsics: <path> }`.
  Paths are relative to the dataflow file.
- Frames dictionary format: the reference `frames.yaml` 1.1.0 (kinds `fixed`,
  `dynamic`, `mounted`, `none`). Extrinsics format: the reference
  `extrinsics.schema.json`.

### 4.4 `dora validate` checks (`libraries/core/src/descriptor/validate.rs`)

Ported from the reference validator, reported as errors (not type warnings),
and run whenever the dataflow has a `frames:` key:

1. Every frame named in an annotation exists in the dictionary.
2. Across each edge, the output frame equals the input frame unless the input
   is `any` (after resolving `same_as:` and `env:`).
3. A node whose output frame differs from its input frame must have a route
   between them through the extrinsics and dynamic edges.
4. Each dynamic edge on that route must be covered by a pose input of the node
   whose declared `child_frame` lies on the edge; at most one dynamic edge per
   pose input.
5. A route needing an extrinsic that is not in the extrinsics file is refused.
   Missing calibration is never identity.

The validator reports the first failing route per node with the edges it tried.

### 4.5 Transform crate (`libraries/transform`, crate `dora-transform`)

Port of the reference `frames.py` and `transform.py`:

- `Frames` loads and checks the dictionary; unknown kinds and list-typed names
  are errors.
- `Extrinsics` loads the per-robot file and checks it against the dictionary.
- `Transform` is rigid only: construction from a matrix refuses a non-rigid
  rotation. It has `compose`, `inverse` and `apply` over packed float32 points.
- `route(from, to)` resolves in either direction. It returns
  `MissingExtrinsicError` before `DynamicEdgeError`, and `DynamicEdgeError`
  lists the edges.
- `resolve(route, poses)` composes the static and pose edges, trying the
  inverse pose orientation where the route runs against the pose.
- Stamp conversion uses exact integer nanoseconds with the reference rounding.

The Python binding is a `dora.transform` submodule in `apis/python/node`.

### 4.6 C API (`apis/c/node`)

```c
typedef enum { DORA_PARAM_BOOL, DORA_PARAM_INT, DORA_PARAM_FLOAT, DORA_PARAM_STRING } DoraParamKind;
typedef struct {
    const char *key; size_t key_len;
    DoraParamKind kind;
    union { bool b; int64_t i; double f; struct { const char *ptr; size_t len; } s; } value;
} DoraParam;

int dora_send_output_with_params(void *ctx, const char *id, size_t id_len,
                                 const char *data, size_t data_len,
                                 const DoraParam *params, size_t n_params);
```

Declared in `node_api.h`. A null `params` with `n_params == 0` behaves like
`dora_send_output`. Invalid UTF-8 in a key or string, or a null pointer with a
non-zero length, returns an error and sends nothing.

### 4.7 frame_transform node (`nodes/frame-transform`)

A Python package using `dora.transform`, with a `dora-node.yml` manifest.

- Inputs: `cloud` (`std/media/v1/PointCloud`, frame `any`), optional `pose`
  (`std/math/v1/Pose`).
- Outputs: `cloud` (`std/media/v1/PointCloud`, frame `env:TARGET_FRAME`) and
  `diag` (per-period counts: items, bytes, processing time, drops by reason).
- Behaviour follows the reference `frame_transform_op.py`:
  - A cloud is never published under a frame it is not in. A cloud with a
    missing or unknown `frame_id` (`bad_frame`), or with no route or no pose
    for a dynamic edge (`no_pose`), is not sent on `cloud`; it is a counted
    drop reported on `diag`.
  - A bad pose message is a counted `bad_pose` drop; the previous pose is kept.
  - A pose more than 100 ms from the cloud stamp, in either direction, makes the
    output `stale` with reason `stale_pose`; a degraded pose passes its
    validity on with reason `pose_<reason>`.
  - A degraded input cloud stays degraded; nothing upgrades it.
- `seq` is taken only for a published cloud, so a gap downstream means loss on
  the edge.

## 5. Changes in DORA_NAV

All in `modules/simulation/mujoco_mickrobot`:

- `dora_adapter.py` adds `frame_id`, `stamp_ns`, `seq`, `source` and
  `validity=ok` to the existing lidar, IMU, RGB and odometry outputs. Payloads
  are unchanged, so existing consumers keep working.
- New output `cloud`: the lidar scan as `std/media/v1/PointCloud[fields=xyzi]`
  in `lidar_link`.
- New output `odom_pose`: `std/math/v1/Pose`, `frame_id=odom`,
  `child_frame=base_footprint`.
- A `dora-node.yml` manifest declaring all outputs with types and frames.

New robot description, `robots/mickrobot-sim/`:

- `frames.yml`: map, odom (dynamic to base_footprint), base_footprint,
  base_link, lidar_link, imu_link, camera_link.
- `extrinsics.yml`: base_footprint → base_link, base_link → lidar_link at
  (0.25, 0, 0.25), imu and camera from the sim model.

New dataflows, `examples/contract-core/`:

- `good.yml`: sim → frame_transform (`TARGET_FRAME=odom`, inputs `cloud`,
  `odom_pose`) → checker.
- `bad-frame-mismatch.yml`, `bad-unknown-frame.yml`,
  `bad-missing-calibration.yml`, `bad-two-dynamic-edges.yml`: one refusal each.
- `checker.py`: the run-time assertions in section 7.

## 6. Data flow

```
mujoco sim ──cloud (lidar_link, PointCloud xyzi)──► frame_transform ──cloud (odom)──► checker
          └─odom_pose (odom→base_footprint, Pose)──┘        │      └──diag (drops)────┘
                                                            ▲
                                       extrinsics: base_footprint→base_link→lidar_link
```

## 7. Error handling and the live run

- Before launch: `dora validate` refuses each `bad-*.yml` with the specific
  reason and accepts `good.yml`.
- At run time: degraded inputs are forwarded with their validity, never
  upgraded; unroutable or unframed clouds are counted drops on `diag`, never
  published under the target frame.
- Checker assertions over a 60 s run while the sim drives a fixed velocity
  script:
  - every output has `frame_id=odom`, strictly increasing `seq`, and
    `validity=ok` once the first pose has arrived;
  - ground points (lowest 10 % by z in `lidar_link`) lie at z = 0 ± 0.03 m in
    `odom`;
  - a second run with `frame_id` stripped from the sim cloud (an env switch on
    the sim) yields no `cloud` outputs, and `diag` counts one `bad_frame` drop
    per input cloud.
- The checker subscribes to both `cloud` and `diag` and writes
  `examples/contract-core/records/contract-core.json` with counts, the
  ground-plane error statistics, the validity histogram and the drop counts.

## 8. Testing

- Rust unit tests in `libraries/message` (header), `libraries/core` (types,
  descriptor, validate) and `libraries/transform`.
- `docs/contract-core/test-mapping.md` in the dora copy: each reference test
  maps to a new test, or is marked "not applicable" with a reason.
- Python tests for `dora.transform` and `nodes/frame-transform`.
- C test: a C node sends a header through `dora_send_output_with_params`; a
  Python receiver asserts every key and type.
- `dora validate` run on `good.yml` and every `bad-*.yml`, expected results
  asserted by a script.
- Mutation sweep: the reference's 17 mutations, re-expressed as patches against
  the Rust and Python code in the copies. A script applies each, runs the
  tests, and reverts. Every mutation must be caught.
- The existing test suites of dora and DORA_NAV's sim still pass.

## 9. Exit criteria

1. All tests in section 8 pass and no existing test regresses.
2. `dora validate` accepts `good.yml` and refuses each `bad-*.yml` with its reason.
3. The live run on port 6113 completes and the record meets section 7.
4. Mutation sweep: 0 survivors.
5. `docs/contract-core/feasibility.md` in the dora copy lists what did not fit
   dora's model, the size of each change (files, lines), and an effort estimate
   for the later slices.

## 10. Out of scope

Perception nodes beyond frame_transform, camera intrinsics, timestamp aligner,
map-frame output (needs localization), DORA_NAV C++ builds, dora-moveit2,
dora-hub, dora-studio, octos and octos-dora-bridge changes, actions and client
APIs, security, any push or pull request.

## 11. Risks

- `std/media/v1/PointCloud` changes (required metadata, `fields` parameter) may
  break existing dora tests or examples. Mitigation: run the full dora test
  suite; if a change breaks users, put the required keys behind the
  `frames:` key instead and record it in the feasibility report.
- The dora master build may not match the pyo3 or Python versions in use.
  Mitigation: `.venv-exp` pins its own Python and maturin.
- MuJoCo rendering in the sim may need a display. Mitigation: run headless
  (`MUJOCO_GL=egl`); if the lidar ray-cast needs no rendering, disable the RGB
  camera for the run.
