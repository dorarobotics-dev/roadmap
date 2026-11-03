# Coordinate Transformation — Design

Date: 2026-10-20
Status: approved in brainstorming, awaiting spec review
Amends: `2026-10-20-operator-contract-and-data-processing-design.md` §2.4
item 1, §9 (frame-handling row), §11.2 (first forward dependency)
Handoff step: §4 step 3 of `docs/superpowers/handoffs/2026-10-20-operator-contract-handoff.md`

## 1. Why this exists

The contract layer's §9 decision was "declare and check agreement; never
transform". It was the right cut for sub-project 0, but it left transformation
unowned. Contract text v1.3 asks for coordinate work in five places, not one:

| Item (workbook row) | Text | Transform actually needed |
|---|---|---|
| 13 (H2) | 输出统一坐标系下的融合结果 | lidar and camera into `base_link` — static |
| 13 (H2) | 输出…三维位置 | camera into `base_link` — static |
| 14 (H3) | 统一…坐标系…口径；端口与坐标系字典 | dictionary (exists); localization already composes its own extrinsic |
| H8 | 统一位置、姿态与速度…坐标系 | dictionary plus declared frames on every port |
| H14 (动捕) | 支持设备标定、坐标转换；交付…标定文件 | device into robot — static, from a calibration file |
| H11 (仿真) | 统一坐标展示 | map → `base_link` — dynamic, display only |

Every acceptance line can be met with **static** extrinsics plus the pose that
localization already publishes. No acceptance line asks for map-frame fusion,
a time-indexed transform buffer, or interpolation.

### 1.1 What the upstreams do today

Surveyed on asus, 2026-10-20, across `dora-nav` (dora-rs master `a9257f5`),
`dora-moveit2`, `dora` and `dora-hub`:

- **No TF tree, no transform buffer, no tf2 inside any dataflow.** tf2 appears
  only in two vendored ROS 1 scripts that no dataflow runs.
- **Every extrinsic is applied by hand in the node that needs it**, and the
  values come from four different places:
  - JSON config: `hdl_localization_config.json` `lidar_to_base_link`, x = −0.45.
  - Hard-coded: `ndt_mapper.cpp:18` `baselink2lidar_config[6] = {0,…}`. Its
    comment says "in the config file"; it is not read from one.
  - Environment variables: dora-hub's `TRANSFORM` and `*_TRANSFORM`.
  - Hand-copied `LINK_TRANSFORMS` in dora-moveit2's robot configs ("Extracted
    from URDF").
- **One physical frame has several names.** The lidar is `rslidar_frame`,
  `rslidar`, `livox_frame`, `lidar` and `lidar_link`. The fixed frame is both
  `map` and `world`.
- **All-zero extrinsics are common** (`MID360_config.json`, `ndt_mapper.cpp:18`,
  `lightning_slam_config.yaml`). Nothing distinguishes "measured as zero" from
  "never set".

### 1.2 Upstream base: dora-rs master, not the fork

Sub-projects 2 and 3 build on dora-rs `DORA_NAV` master (`a9257f5`), not on
the bobdingAI fork revision `1f297df` that `component-lock.yaml` pinned. The
fork diverged at `2041d8c` (2026-02-23): 15 fork-only commits (Python nav
nodes, obstacle avoidance) against 22 upstream ones, and `1f297df` is not
reachable from dora-rs.

Upstream reorganised in `fac6f21` (2026-07-17, "adjust the directory layout"),
with two consequences:

- `include/Planning.h`, `include/Localization.h` and
  `peception/euclidean_cluster/` no longer exist. That removes the forked
  `Request_h` layout recorded in the handoff (§5), and it also removes handoff
  step 4's candidate chain.
- Messages are now `msg/nav_msgs/*.hpp`: ROS 2-shaped JSON whose
  `HeaderMessage` is `{stamp, frame_id, seq}`, with `OdomMessage` carrying a
  `child_frame_id`. That is already close to the envelope, and a pose with a
  parent and a child frame is the only dynamic-transform input this design
  needs.

## 2. Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Scope | Static extrinsic tree, plus explicit composition with a published pose | Meets every v1.3 acceptance line. A time-indexed buffer is the expensive half of a TF tree, and nothing asks for it |
| Placement | Library `open_robot_operator.transform`, plus a `frame_transform` node in `capabilities/perception/` | Five items need the same math. A node alone forces fusion and mocap to duplicate it |
| Library dependency | numpy, through an optional extra `open-robot-operator[transform]` | The core keeps §2.3's three dependencies |
| Per-robot numbers | `robots/<name>/extrinsics.yaml` | `robots/<name>/` already holds per-robot facts; `frames.yaml` stays the vocabulary |
| Rotation form | Unit quaternion, `xyzw`, nothing else | One form means no rpy-order ambiguity |
| Missing extrinsic | An error, never identity | Rules out the upstream all-zero defect |
| Upstream frame names | Rejected with a "use instead" hint, never aliased | The `Request_h` rule from handoff §5: pick one, don't wrap both |
| ROS 2 tf2 | Not used | The dora ros2-bridge has no `tf2_msgs`, and tf2 would bring a ROS 2 install into every pack |

**Restating §9 rather than reversing it:** the envelope and the pre-launch
validator still never transform anything. Transformation happens only inside
an operator that declares it, using `open_robot_operator.transform`, against a
per-robot calibration file the validator has checked.

## 3. Data model

### 3.1 `specs/operators/frames.yaml` → 1.1.0

Three changes:

1. **Each frame gains `kind`:**
   - `fixed` — `map`.
   - `none` — the frame-less `none`. It is never part of a transform.
   - `dynamic` — its pose relative to its parent changes at run time: `odom`,
     `base_footprint`.
   - `mounted` — rigidly attached to its parent: `base_link`, `rslidar`,
     `camera_front`, `imu_link`, `tool0`.

   Only `mounted` edges may appear in an extrinsics file.

2. **`base_footprint` is added** as `dynamic`, with parent `odom`, and
   `base_link` is re-parented under it as `mounted`. The MuJoCo model
   (`mickrobot.xml:27-29`, `base_link` 0.1 m above `base_footprint`), its URDF,
   and its odometry (`child_frame_id: base_footprint`) all use this split, so
   without it the simulator's odometry has nowhere to land.

   `parent` remains documentation for integrators, as before. The tree
   structure is now also checked (§3.2), and its only reader before this change
   was `tests/test_specs.py`.

3. **A `rejected_names` table** maps upstream names to the dictionary name:

   | Rejected name | Use instead |
   |---|---|
   | `world` | `map` |
   | `rslidar_frame` | `rslidar` |
   | `lidar` | `rslidar` |
   | `lidar_link` | `rslidar` |
   | `livox_frame` | `rslidar` |
   | `camera_link` | `camera_front` |

   The validator and the library report a rejected name together with its
   replacement. Renaming is the adapter's job, at the boundary where an
   upstream message enters a contract port.

`rslidar` keeps its name even for the Livox and simulated lidars. It already
means "the primary 3-D lidar as mounted", and renaming it would break the
shipped data-processing mocks (`point_cloud_source`, `dataflows/mocks/operators.yaml`)
for no gain. Its description is updated
to say so.

### 3.2 `robots/<name>/extrinsics.yaml`

One file per robot calibration:

```yaml
contract_version: 1.0.0
robot: simulated-mobile-robot
calibrated: 2026-10-20
source: >-
  DORA_NAV a9257f5 modules/simulation/mujoco_mickrobot/models/mickrobot.xml
  and mujoco_extensions.xml
transforms:
  - parent: base_footprint      # base_footprint is dynamic, but this edge
    child: base_link            # (footprint -> link) is the mounted one
    translation_m: [0.0, 0.0, 0.1]
    rotation_xyzw: [0.0, 0.0, 0.0, 1.0]
  - parent: base_link
    child: rslidar
    translation_m: [0.25, 0.0, 0.25]
    rotation_xyzw: [0.0, 0.0, 0.0, 1.0]
  - parent: base_link
    child: camera_front         # optical: z forward, x right, y down
    translation_m: [0.40, 0.0, 0.35]
    rotation_xyzw: [-0.5, 0.5, -0.5, 0.5]
  - parent: base_link
    child: imu_link
    translation_m: [0.0, 0.0, 0.25]
    rotation_xyzw: [0.0, 0.0, 0.0, 1.0]
```

Each entry is the pose of `child` expressed in `parent`. The camera quaternion
is derived from MuJoCo's `xyaxes="0 -1 0 0 0 1"`. The MuJoCo camera looks
along its −z, and the optical frame in `frames.yaml` looks along +z, so the
optical axes in `base_link` are x = (0,−1,0), y = (0,0,−1), z = (1,0,0). The
plan pins this derivation with a test.

The JSON Schema is
`specs/operators/schemas/openrobot.geometry.extrinsics-1.0.0.json`.
`load_extrinsics` enforces the following, and every failure is blocking:

- `parent` and `child` are both names in `frames.yaml`, and neither is a
  rejected name.
- `child`'s declared `parent` in `frames.yaml` equals the entry's `parent`.
- `child` is `mounted`. This is what enforces "static only": a dynamic edge
  cannot be written into the file.
- `child` appears at most once.
- The quaternion has unit norm within 1e-6. It is not silently normalised.
- `translation_m` has three finite numbers, and `rotation_xyzw` has four.

An absent edge is not an identity transform. An extrinsic that really is zero
is written out explicitly, and the `source` field says where it was measured.

### 3.3 `openrobot.state.pose-1.0.0` (new payload schema)

This schema is the dynamic half. A message carries the pose of `child_frame`
expressed in the header's `frame_id`:

| Field | Type | Unit |
|---|---|---|
| `child_frame` | string, a `frames.yaml` name | — |
| `position` | float64[3] | m |
| `orientation_xyzw` | float64[4], unit norm | — |

The header's `frame_id` must be `fixed` or `dynamic`. `child_frame` may be any
known frame other than `none`. This deliberately mirrors upstream's
`OdomMessage` without the twist. No buffer is kept and nothing is
interpolated: a consumer uses the latest message it received.

## 4. Library: `open_robot_operator.transform`

numpy is imported only in this module.

- **`load_extrinsics(path, frames=None) -> Extrinsics`** runs every check in
  §3.2. `frames` defaults to the packaged `frames.yaml`.
- **`Extrinsics.lookup(src, dst) -> Transform`** walks `mounted` edges up to a
  common ancestor and composes them. It raises in three cases:
  - `MissingExtrinsicError` — a needed edge is absent from the file.
  - `DynamicEdgeError` — the path would cross a `dynamic` edge. A static lookup
    can never quietly produce a map-frame answer.
  - `UnknownFrameError` — either frame is unknown or rejected; the message
    carries the replacement name.
- **`Transform`** is frozen and holds `src`, `dst` and a 4×4 float64 array. It
  maps coordinates expressed in `src` to coordinates expressed in `dst`.
  - `apply_points(points)` takes N×3 and returns N×3.
  - `inverse()` returns the `dst → src` transform.
  - `then(other)` applies `self` and then `other`. It raises `FrameOrderError`
    unless `self.dst == other.src`, so composing in the wrong order is an
    error, not a wrong matrix.
- **`pose_transform(pose_payload, header) -> Transform`** returns
  `child_frame → header.frame_id`. Odometry passthrough is written out by the
  consumer, for example:

  ```python
  ext.lookup("rslidar", "base_footprint").then(pose_transform(odom, hdr))
  ```

  This yields `rslidar → odom`.

### 4.1 Staleness of a composed result

There is no new mechanism. A consumer that composes with a pose declares its
pose input with `max_age_ms`. If the latest pose's `stamp_ns` is older than the
data's `stamp_ns` by more than that, the output is forwarded with validity
`degraded` and reason `stale_pose`, and the stage counter increments. If no
pose has arrived yet, the reason is `no_pose`, and that is also forwarded
rather than dropped. Both §3.2 invariants of the contract spec hold unchanged:
nothing is dropped, and this operator repaired nothing, so it never raises a
validity.

## 5. Node: `frame_transform`

This is the first operator of `capabilities/perception/`, declared in that
pack's `operators.yaml`.

| Port | Direction | Schema | Frame |
|---|---|---|---|
| `cloud` | in | `openrobot.sensor.point_cloud` ^1 | `any` |
| `pose` | in, optional | `openrobot.state.pose` ^1 | `any` |
| `cloud` | out | `openrobot.sensor.point_cloud` ^1 | literal, from config `target_frame` |

- **What it changes:** only xyz is rotated and translated. Every other field
  is passed through by name, and so are the original `stamp_ns` and `source`,
  through `derive`; only `frame_id` changes.
- **How it gets the transform:** from `ORS_EXTRINSICS`, the file path, at
  start-up. A file that fails §3.2's checks stops the node before its first
  message.
- **When it uses the pose:** only when the static path from the input frame to
  `target_frame` crosses a dynamic edge. Exactly one dynamic edge is
  supported, the pose's own (child -> parent), crossed in either direction:
  upwards as src -> child, pose, parent -> dst, or downwards as
  src -> parent, pose inverted, child -> dst. Any other route is a
  `bad_frame` drop, logged once.
- **Payload scope is point clouds only.** The obstacle-list schema belongs to
  item 13's clustering, which does not exist yet. When it lands, transform
  support for it lands in the same change.

## 6. Validator check: `transform` (blocking)

- **Trigger:** an operator whose output declares a literal frame that differs
  from the resolved frame of one of its inputs. `none` and `any` are excluded
  on either side.
- **Requirement:** the validator was given `--extrinsics <path>`, and the file
  passes §3.2 and contains a path between the two frames.
- **Additional requirement when the path crosses a `dynamic` edge:** the
  operator must declare a `state.pose` input, and that input must be wired.
  A path crossing more than one dynamic edge is blocking even with a pose
  wired: one pose input covers one dynamic edge.
- **Same-file check:** a node whose `env.ORS_EXTRINSICS` is set must name the
  same file as `--extrinsics`, compared after path resolution. A robot cannot
  be validated against one calibration and launched with another.
- **No effect on existing dataflows.** Every data-processing operator uses
  `same_as`, so both shipped dataflows produce exactly the violations they
  produce today, and a test pins this.

## 7. Upstream adapters: the traps

Sub-projects 2 and 3 write these adapters; this design only fixes their rules.

- **Quaternion order.** Upstream's `poseToJson`
  (`json_serialization.cpp:88-113`) writes named `w,x,y,z` keys. The trap is
  in turning those into our positional `xyzw`, and in Eigen, whose constructor
  takes `(w,x,y,z)` while `coeffs()` returns `xyzw`.
- **Stamps.** Upstream's `header.timestamp` is double seconds, so it must be
  converted to integer `stamp_ns`. A double holds about 0.2 µs of precision at
  current epoch times, which is fine, but the conversion must round, not
  truncate.
- **Child frame.** `poseToJson` emits no child frame (it is always `base_link`
  in `map`). The adapter supplies `child_frame` from its declaration, not from
  a literal in code.
- **Frame names.** Upstream names are renamed through `rejected_names`, at the
  adapter only.

## 8. Testing

These are the four layers of the contract spec's §7. Assurance is by mutation,
not by coverage.

**Unit tests use asymmetric fixtures on purpose.** The main fixture is the sim
camera, quaternion (−0.5, 0.5, −0.5, 0.5), together with a 90° yaw plus a
non-zero translation. A symmetric fixture would pass a swapped quaternion
order.

The unit tests cover:

- **Round trips:** `T.then(T.inverse())` is identity, and
  `lookup(a, b) == lookup(b, a).inverse()`.
- **Every §3.2 rejection.** Each has a fixture file.
- **Every §4 error path:** missing edge, dynamic edge, unknown frame, rejected
  frame (with the hint text), and `then()` order.
- **Hand-computed points** for `camera_front → base_link`:
  - `(0, 0, 1)`, one metre along the optical axis, maps to `(1.40, 0, 0.35)`.
  - `(1, 0, 0)`, optical right, maps to `(0.40, −1, 0.35)`.

  These were checked independently with scipy. The tests assert them as
  literals and never recompute them with the code under test.

The adapter rule tests cover:

- Upstream's JSON pose sample, converted, matches a literal expected `xyzw`.
- Seconds-to-nanoseconds conversion rounds rather than truncates.

**Mutation anchors** are added to `tools/mutation-sweep.py`, with a target of
0 surviving:

- a missing edge returns identity
- `then()`'s frame check is removed
- `rotation_xyzw` is read as `wxyz`
- the dynamic-edge rejection is removed in `load_extrinsics`
- `stale_pose` forwards `ok`
- the validator's `transform` check is skipped
- the same-file check is skipped

**End to end:** `capabilities/perception/dataflows/transform-chain.yml` runs a
mock lidar in `rslidar`, then `frame_transform` with
`target_frame: base_link`, then a sink, under real dora 1.0.1. The sink
asserts one point against a literal expected value and checks that `stamp_ns`
and `source` are unchanged.

## 9. Changes to existing artifacts

| Artifact | Change |
|---|---|
| Contract spec §2.4 item 1, §9 frame row | Restated as in §2 above |
| Contract spec §11.2 | "The only place a TF tree can live is item 13" becomes: the library is shared by 13, 14, H14 and H11; item 13 owns fusion and projection |
| `specs/operators/frames.yaml` | 1.0.0 → 1.1.0: `kind`, `base_footprint`, `rejected_names` (§3.1) |
| `tests/test_specs.py` | Covers `kind`, the tree, `rejected_names`, and the new schemas |
| `component-lock.yaml` | dora-nav re-pinned to dora-rs master `a9257f5` (§1.2) — done with this spec |
| Handoff step 4 | The candidate chain is gone (§1.2). Recommendation, to settle in its own brainstorm: migrate hdl_localization's pose output onto `state.pose`. It is the dynamic source this design needs, and its frames are already explicit |

## 10. Out of scope

- Time-indexed transform buffers and interpolation.
- URDF or MJCF parsing at run time. `extrinsics.yaml` is written by hand, with
  its source cited.
- Kinematic chains. dora-moveit2's FK stays where it is; `tool0` is a
  dictionary entry only.
- Camera intrinsics and projection. Item 13's fusion operator owns them and
  calls `lookup` for the extrinsic half.
- Calibration procedures. H14 delivers its own calibration files in this
  format.
- Any C++ library. C++ nodes read `extrinsics.yaml` against its JSON Schema,
  as with every other schema (contract spec §2.4 item 5).

## 11. Size

These are rough figures for the plan to firm up:

| Piece | Size |
|---|---|
| Library | about 250 lines |
| `frame_transform` node and its declaration | about 120 lines |
| Validator check | about 60 lines |
| Schemas and dictionary changes | two schemas, one dictionary bump, one extrinsics file |
| Tests | about 60, plus seven mutation anchors and one dataflow |

## 12. Amendments made while planning (2026-10-20)

Reading the code for the implementation plan turned up nine places where this
spec did not match the layer it extends, or chose worse than it could have.
The plan follows the text below wherever it and §§3–8 disagree.

1. **There is no `degraded` validity.** `VALIDITY` is `ok, missing, stale,
   unpaired, low_confidence, rejected`. Instead:
   - A cloud composed with a pose whose `stamp_ns` differs from the cloud's by
     more than `max_age_ms`, in either direction, goes out `stale` with reason
     `stale_pose`. A pose far newer than the cloud is as wrong as one far
     older.
   - A pose that is itself not ok passes its validity on, with reason
     `pose_<its reason>`.
   - A cloud that is already not ok keeps its own validity, because a header
     carries one reason.
2. **No pose yet is a counted drop, not a forward.** With no pose there is no
   transform, and nothing truthful to publish in `target_frame`. A counted drop
   (`no_pose`) satisfies 不静默丢弃. §4.1's "forwarded rather than dropped"
   applies to `stale_pose` only.
3. **Forwarding a worse message increments no counter.** `Counters` counts
   drops and repairs, matching item 16's "被丢弃或被修复". A forwarded stale
   cloud is visible in its own header.
4. **The route and the arithmetic are split.** `open_robot_operator.frames`
   (no numpy) loads the dictionary and the extrinsics and finds the route; the
   validator imports only it. `open_robot_operator.transform` (numpy) does the
   arithmetic, so `lookup(extrinsics, src, dst)` is a function there, not an
   `Extrinsics` method. There is no packaged `frames.yaml`; its path is passed
   in. The validator takes `--frames` (default `specs/operators/frames.yaml`),
   and the node reads `ORS_FRAMES`, which the pack's launcher defaults.
5. **The extrinsics JSON Schema is `specs/operators/extrinsics.schema.json`.**
   `schemas/` holds payload schemas, and every file there must satisfy the
   payload meta-schema, which an extrinsics file is not.
6. **`child_frame` travels as a metadata key**, and the pose payload is
   float64[7] in the order px py pz qx qy qz qw. A payload schema's fields are
   numeric and carry units, so a string cannot be one of them.
7. **`frame_transform` declares its output frame as `env:TARGET_FRAME`.** This
   is a new declaration form: an output's frame is read from the node's `env:`
   in the dataflow, so one operator serves any target and the validator still
   resolves the frame before launch. Like `same_as:`, it is output-only.
8. **`tool0` is `dynamic`, not `mounted`.** The flange moves with the joints,
   and a mounted `tool0` would invite a static calibration of a moving frame.
9. **The end-to-end chain targets `camera_front`, not `base_link`.** `rslidar`
   is mounted without rotation, so a `base_link` target would exercise only a
   translation. `camera_front` exercises a rotation and an inverted edge.
