# Operator Contract and Data-Processing Operators — Design

Date: 2026-10-20
Status: approved
Amended: 2026-10-20 — §11, contract text v1.3
Scope: sub-projects 0 and 1 of the 自主算子开发 work (contract items 13–16)

## 1. Why this exists

Contract items 13–16 (`自主算子开发`, 200万) each promise a unified operator
interface. Item 13 promises an "接口与数据结构说明", item 14 promises a
"端口与坐标系字典", item 15 promises an "算子注册与接口文档", and item 16
promises an "接口文档". Those four artifacts are one thing described four
times, and none of it exists today.

What exists instead:

- `dora-nav` carries 20 C++ headers in `include/` (`LidarRawObject.h`,
  `ObjectArray.h`, `Localization.h`, `Planning.h`, `Twist.h`, `SlamPose.h`, …).
  They are a de-facto message set with no cross-language contract, no declared
  frames, units or versions, and no validity flags.
- `dora-moveit2` has a `RobotConfig` Protocol, which is a *configuration*
  contract, not a data contract. Each `*_op.py` carries its own ad-hoc
  dataclasses. There is no registry and no shared port schema.
- The wire idiom in both repos is a bare `pyarrow` array plus a loose
  `metadata` dict (`metadata={"encoding": "jointstate", "success": True}`).
  Across both repos `metadata` is written in 11 places and read in 44, but
  almost every read is a verbatim pass-through
  (`send_output("bbox", arrays, dora_event["metadata"])`); only two sites
  extract a field.

Item 15 additionally requires that the cognition operators consume the
perception operators' output and feed "控制类算子的规划与决策入口". That is a
hard cross-item interface requirement, so the contract layer is a prerequisite
for three of the four items, not an optional refinement.

Contract text v1.2 named that input "感知类算子输出的目标轨迹与关键点". v1.3
restates it as the perception operators' target list and rate estimates plus
the motion-capture system's body and hand keypoints, because item 13 never
produced keypoints and no longer produces long-term tracks. The cross-item
requirement is unchanged in force; §11 records the amendment.

### 1.1 The defect this fixes, in committed code

`dora-nav/peception/euclidean_cluster/LidarRawObject_to_ros2.py:95-96`:

```python
# 'frame_id': self.header['frame_id'],
'frame_id': "rslidar",
```

The frame that should have been restated by the producer was commented out and
replaced with a hard-coded literal. Blind metadata pass-through produces the
mirror-image bug: the YOLO node forwards the *image's* metadata onto its
*bbox* output, so the bbox carries the image's frame and schema label.

Both bugs come from having no rule about which header fields propagate and
which must be restated. Section 3 states that rule.

## 2. Architecture and boundaries

### 2.1 Deliverable units

| Output | Location | Contract artifact it satisfies |
|---|---|---|
| Operator contract spec (normative text + JSON Schema) | `specs/operators/operator-contract-v1.md` | 13 「接口与数据结构说明」, 16 「接口文档」 |
| Frame dictionary, unit dictionary | `specs/operators/frames.yaml`, `specs/operators/units.yaml` | 14 「端口与坐标系字典」 |
| Python reference implementation and pre-launch validator | `packages/open-robot-operator/` | 15 「算子注册与接口文档」 |
| Data-processing capability pack | `capabilities/data-processing/` | item 16 in full |

The contract layer is not separately priced. Its outputs are the four named
artifacts above, which means it must be built, and also that it must not grow
beyond them.

### 2.2 Repository placement

v1.3 §6 already reserves the directories this work lands in:

```text
specs/capabilities/            → specs/operators/ (sibling, same role)
capabilities/
├── navigation/                → sub-project 3 (control, dora-nav side)
├── manipulation/              → sub-project 3 (control, dora-moveit2 side)
├── perception/                → sub-project 2
└── speech/
    + inference/               → already built on feat/edge-inference-transparency
    + data-processing/         → sub-project 1 (this spec)
    + cognition/               → sub-project 4, depends on inference/
```

§6 also states the monorepo policy: "Start as a monorepo to simplify
governance and coordinated releases. Packs can graduate into separate
repositories when ownership and release cadence become clear."

### 2.3 Why a separate Python package

`open_robot_operator` is a new top-level package under `packages/` rather than
a module inside `open_robot_sdk`, for two reasons:

1. Every capability pack imports it. The SDK pulls in zenoh and discovery
   dependencies, which is too much weight for a dataclass and a validator.
2. The name `open_robot_sdk` already collides with an unrelated same-named
   project at `/Users/Shared/github_bdingff/open-robot-sdk`. The inference
   pack had to patch `sys.path` in its own `conftest.py` to work around it.
   A package whose only dependencies are `pyarrow` and `jsonschema` does not
   repeat that.

### 2.4 What this layer is not

In priority order, because the minimum-delivery posture is achieved by scope
cuts rather than by writing less code:

1. **Not a coordinate-transform engine.** The envelope and the validator never
   transform. A frame change happens only inside an operator that declares it,
   using `open_robot_operator.transform` against a per-robot calibration the
   validator has checked (check 6). The library ships with this package, but
   only as an optional extra, and it holds a static tree plus the latest pose
   rather than a TF buffer. See
   `2026-10-20-coordinate-transformation-design.md`.
2. **Not a capability-ID registry.** v1.3 §8.3 governs task-level
   request/response semantics (`robot.navigation.navigate-to` with
   `start`/`cancel`). Operators are streaming ports. The two granularities
   stay separate and are not merged.
3. **Not a new transport.** Messages stay on dora plus pyarrow. The envelope
   is a convention carried inside the existing message, not a replacement for
   it.
4. **Not a replacement for ROS 2 messages.** The envelope header is a superset
   of the ROS 2 header; `frame_id` keeps its ROS 2 name and meaning.
   Bidirectional conversion is the job of item 16's format-conversion
   operator.
5. **Not cross-language code generation.** Python gets a reference
   implementation. The C++ side is guaranteed only that the schemas are
   readable; no C++ library ships in this phase.
6. **Not a runtime registry service.** Item 15's "算子注册…机制" is satisfied
   by a declarative manifest (section 4.1). A resident registry process with
   its own lifecycle is out of scope.

### 2.5 Relationship to existing code

`dora_moveit`'s `RobotConfig` Protocol is untouched; it is a configuration
contract and orthogonal to this one. The 20 headers in `dora-nav/include/` are
untouched, per v1.3 §4.1 ("Compose upstreams; do not fork by default");
sub-project 2 will wrap them with Python adapter operators.

## 3. The envelope and the runtime contract

### 3.1 Two field classes with opposite rules

Verbatim pass-through is correct for one half of the header and wrong for the
other. The envelope is split along that line.

**Propagated verbatim** — conversion, compression and filtering must not
rewrite these:

| Field | Type | Meaning |
|---|---|---|
| `stamp_ns` | int64 | Original capture time |
| `source` | str | Origin identifier, e.g. `lidar.front` |

**Restated by every producer** — copying these from an input is a contract
violation:

| Field | Type | Meaning |
|---|---|---|
| `schema` | str | `openrobot.perception.object_array/1.0.0` — structure id plus SemVer |
| `frame_id` | str | Frame identifier, same name and meaning as ROS 2. Checked for agreement, never transformed |
| `seq` | int64 | Monotonic per output port. A gap reveals messages lost between two adjacent operators. It is **not** the basis for duplicate detection — see 3.2.1 |
| `validity` | str | See 3.2 |
| `reason` | str \| None | Required when `validity != "ok"`, and must be `None` otherwise |

Putting `frame_id` on the restated side is what fixes
`LidarRawObject_to_ros2.py:95`: the bug there is not the hard-coded literal,
it is that the field was being sourced from the input at all.

### 3.2 `validity` values and two invariants

Values: `ok`, `missing`, `stale`, `unpaired`, `low_confidence`, `rejected`.

They map onto the contract text directly. Item 13's "标识缺失、过期及不满足
配对条件的数据" yields `missing`, `stale` and `unpaired`. Item 15's
"低置信度结果显式标识" yields `low_confidence`. Item 14's "超限时拒绝执行并
上报原因" yields `rejected` with a mandatory `reason`.

**Invariant 1 — a message with `validity != "ok"` is still sent.** It is
never silently dropped; the downstream operator decides what to do with it.
The obligation runs one way: sending a degraded message does not oblige the
consumer to consume it. A downstream operator reads `validity` and may decline,
counting what it declined. Building the A/B example showed why that matters —
without the check the chain dies on a first sample whose defect the cleaner had
no history to repair, which is the contract working rather than a fault.
This discharges item 16's "对被丢弃的数据计数并上报，不静默丢弃" and item 15's
"低置信度结果显式标识而不隐式丢弃". It is the only rule in the contract with
real teeth.

**Invariant 2 — an output may be `ok` only if every contributing input was
`ok`, unless the operator counts the upgrade.** The cleaner turning
`unpaired` into `ok` is legal precisely because it reports a count; any other
operator doing so is in violation. The counters of section 3.5 are the only
legal exit from a degraded state.

The non-`ok` values are deliberately **not ordered among themselves**. There
is no sensible total order over `stale`, `missing`, `unpaired`,
`low_confidence` and `rejected`, so the invariant is stated over the single
`ok` / not-`ok` boundary instead. An operator with a degraded input may emit
whichever non-`ok` value it judges correct — a `stale` input may yield an
`unpaired` output — and only the step to `ok` is accounted for.

#### 3.2.0 Propagation under fusion, and who does the counting

When an operator has several contributing inputs, the two propagated fields
combine deterministically:

- `stamp_ns` is the **minimum** over the contributing parents. A fused result
  is no fresher than its oldest ingredient, which keeps the staleness
  reasoning in 3.2.2 sound. Taking a reference sensor's stamp instead would
  let a fused frame claim a freshness no ingredient had.
- `source` is the sorted, de-duplicated set of parent sources joined with
  `+`, e.g. `camera.front+lidar.front`. A single shared source stays
  unjoined, so the common case reads unchanged.

The upgrade accounting of invariant 2 is performed **by the library, inside
the header-deriving call**, not by the operator. If the operator had to
increment a counter itself, deleting that increment would be an undetectable
mutation. Passing the upgrade intent is the only way to obtain an `ok` output
from a degraded input, and the library counts it as a side effect of granting
it.

Frame resolution walks the dataflow graph and therefore **must detect
cycles**: dora dataflows may contain them, and a `same_as` chain around a
cycle would not terminate. The resolver carries the visited path and reports
it in the error.

#### 3.2.1 Duplicate and out-of-order detection use `stamp_ns`, not `seq`

`seq` is restated monotonically by each producer, so a downstream operator can
never observe a duplicate `seq` from its immediate upstream. Duplicate
detection therefore keys on the propagated fields: two messages carrying the
same `stamp_ns` **and** the same `source` are duplicates of one captured
frame. Out-of-order detection is a decrease in `stamp_ns` within one `source`.

`seq` serves the complementary purpose: a gap in it reveals messages lost on
the edge between two adjacent operators, which `stamp_ns` cannot show.

#### 3.2.2 `max_age_ms` is a same-host comparison

`stamp_ns` is `CLOCK_REALTIME` nanoseconds on the capturing host. A port's
`max_age_ms` is evaluated by comparing the receiving operator's local clock
against `stamp_ns`, which is well-defined only when capture and consumption
happen on the same host.

**Cross-host staleness is out of scope for this phase.** It requires a
two-sided age rule and clock-offset handling, which the edge-inference work
addresses for the inference path. A port declared with `max_age_ms` whose
producer runs on a different host is a configuration error, and the validator
cannot detect it because placement is a deployment detail (v1.3 §4.6). The
interface documentation states this limitation explicitly.

### 3.3 Units are not in the envelope

Units are declared in the **schema definition**, not in the per-message
header. `openrobot.control.twist/1.0.0` declares `linear: m/s` and
`angular: rad/s` once; messages carry only the schema identifier. Item 14's
"统一位置、姿态、速度与力的单位" is discharged by the unit dictionary plus the
schema declarations, which removes one per-message field.

### 3.4 Wire form

The header travels as **flat scalars in dora metadata**; the payload stays in
the arrow array. This is an empirical constraint, not a preference: every
existing metadata value in both repos is a `str`, `bool` or `int`, and nested
dicts are not known to survive. Therefore the timestamp is a single
`stamp_ns: int64`, and the ROS 2 `{sec, nanosec}` split is performed losslessly
by item 16's format-conversion operator.

The reserved key names do not collide with existing usage. Existing keys are
`encoding`, `success`, `dual`, `in_collision`, `num_waypoints`, `num_joints`
and `version`; the last is `planning_scene_op`'s scene version, whereas the
contract's version lives after the slash inside `schema`. Existing keys remain
legal as free-form extras that the contract does not govern.

Headers are **constructed by the shared library**, never by hand-written
dicts. The `send()` helper fills `schema`, `frame_id` and `seq`, and asserts
both invariants locally: `reason` is required when `validity != "ok"`, and
`stamp_ns` and `source` must be copied from a declared parent message rather
than invented.

Payload schemas are **not validated per frame**. Running a point cloud through
JSON Schema at 30 Hz is not acceptable, and check 1 of section 4.3 has already
reconciled the schemas before launch. The runtime guarantees header
correctness only.

### 3.5 Diagnostics use counters, not per-message tracing

Item 16 promises "逐级统计数据量削减比例与处理耗时". Each operator exposes an
additional diagnostics output port reporting rolling counters:
`in_items`, `out_items`, `in_bytes`, `out_bytes`, `proc_ns`, and
`drops_by_reason`. The chain-level reduction ratio is the product of the
per-stage ratios, which needs no per-message correlation.

Accumulating a trail inside the header was rejected: it grows without bound
with chain length and couples every operator to the length of the chain. An
optional `trace_id` field propagates for debugging, but **no correlation
machinery is built** — that belongs to v1.3 §6's `specs/tracing/`, not to this
sub-project.

## 4. Port declarations and the pre-launch validator

### 4.1 One `operators.yaml` per capability pack

v1.3 §8.5 fixes the casing: "Distribution manifest and deployment fields use
camelCase (§7.5); the dora `plugin.yaml` keeps its flat snake_case form.
Runtime/wire envelopes and descriptors use snake_case." Port descriptors are
runtime/wire descriptors, so they are snake_case, whereas `pack.yaml` is a
camelCase distribution manifest. Two files is cleaner than two casing
conventions in one file, and it avoids amending §7.3's `pack.yaml` schema.

```yaml
# capabilities/data-processing/operators.yaml — snake_case (§8.5)
contract_version: 1.0.0
operators:
  - name: point_cloud_filter
    module: open_robot_dataproc.filter.point_cloud_op
    inputs:
      cloud:
        schema: openrobot.sensor.point_cloud/^1.0   # SemVer caret (§8.5)
        frame: any
        max_age_ms: 200          # exceeded → emit validity=stale (see 3.2.2)
    outputs:
      cloud:
        schema: openrobot.sensor.point_cloud/^1.0
        frame: same_as:cloud     # reuses the input frame; no transformation
    diagnostics: diag
```

`frame` takes exactly three forms: `any`, a literal frame name, or
`same_as:<input_port>`.

`same_as` is what makes section 2.4's "no coordinate transformation" cut
enforceable. Filtering, compression, cleaning and conversion all declare
`same_as:`, so any operator that genuinely changes frames must state its
output frame explicitly, at which point the validator requires the downstream
port to accept it. Transforming silently without declaring it fails
validation.

`same_as` does not contradict section 3.1's restatement rule. Under
`same_as:cloud` the emitted `frame_id` does equal that input's `frame_id`, but
the library **resolves it from the declaration** rather than inheriting it as
a side effect of forwarding the metadata dict. The violation is forwarding:
an output port declared with a literal frame that emits its input's `frame_id`
is in breach, and so is an operator that bypasses `send()` to pass the raw
input metadata through.

This file is also the operator registry that item 15 promises.

### 4.2 The validator

`validate_dataflow(dataflow_yml, packs) -> list[Violation]` reads the dora
dataflow YAML's `inputs` mapping (`node/output → input`), resolves each node to
its operator declaration, and checks every edge:

| # | Check | Blocking |
|---|---|---|
| 1 | Producer and consumer schema ids match, and the producer version satisfies the consumer's caret constraint | yes |
| 2 | Frames agree, with `same_as` chains resolved to a literal or `any` | yes |
| 3 | The dataflow wires a port that no declaration defines | yes |
| 4 | A port declared as required is left unwired | yes |
| 5 | A declared diagnostics port is unwired | no — warning only |

Check 3 is the one that earns its keep day to day: a mistyped port name is the
most common failure in dataflows of this shape, and today it is only found at
run time. Any blocking violation exits non-zero, which is v1.3 §8.4's
"Missing requirements fail before motion".

### 4.3 CLI placement defers the spec change

v1.3 §9.2's command table has no operators namespace, and
`robot-stack plugin validate [path]` validates a plugin rather than a
dataflow. This phase therefore ships a library function plus
`python -m open_robot_operator.validate <dataflow.yml> --pack <dir>`, and
**does not amend the spec**. Folding it into `robot-stack operators validate`
is a one-line registration once §9.2 has a place for it.

The reason is sequencing: the edge-inference work already owes amendments to
§7.5 and §8, and attaching another spec amendment to sub-project 0 would turn
the prerequisite for three contract items into something that must clear
spec review first.

Pack declarations are located by explicit repeatable `--pack <dir>` arguments,
plus discovery of `capabilities/*/operators.yaml` when the validator runs
inside the monorepo.

## 5. Data-processing operator library (sub-project 1)

### 5.1 The boundary with perception, which saves work

Item 13's point-cloud direction promises "地面分割、**降采样、离群点剔除**与
聚类算子". Item 16's filtering direction promises "面向**点云**、图像及状态量的
时域与空域滤波算子". Downsampling and outlier rejection appear in both.

The boundary: **downsampling, outlier rejection and range cropping are
implemented in item 16** — they are pure preprocessing with no perception
semantics, and "降低数据冗余" is the definition of downsampling. **Ground
segmentation and clustering stay in item 13**, where the perception semantics
are. Item 13's promise is discharged by the perception pack *depending on* the
data-processing operators and wiring them in its own orchestration example.
The contract requires providing the operators, not reimplementing them.

Both items' deliverables hold; the implementation happens once.

Contract text v1.3 writes this boundary into the workbook itself: item 13 now
states that point-cloud downsampling and outlier rejection are provided by
item 16 and not re-delivered there. The boundary is unchanged — it is the
justification that moved from this spec into the contract (§11).

### 5.2 Minimum operator set: seven operators and two tools

**Filtering — three operators, using modes rather than more nodes**

| Operator | Modes | Coverage |
|---|---|---|
| `point_cloud_filter` | `voxel`, `passthrough`, `outlier`, `accumulate` | point cloud, spatial and temporal |
| `image_filter` | `gaussian`, `median`, `temporal_average` | image, spatial and temporal |
| `state_filter` | `moving_average`, `lowpass` | state vector, temporal |

State vectors have no spatial dimension. The interface documentation states
this explicitly so that it is not read as a missing item at acceptance. All
parameters are configurable, per item 16's "滤波参数可配置".

A bilateral image mode was considered and dropped. `cv2` is not available in
the target environment, neither `scipy.ndimage` nor `PIL.ImageFilter` provides
a bilateral filter, and the contract text asks only for "时域与空域滤波算子，
滤波参数可配置" without naming one. Hand-rolling a bilateral filter is work the
contract does not buy.

Outlier rejection uses `scipy.spatial.cKDTree` for k-nearest-neighbour
distances, not a pairwise distance matrix. A pairwise matrix is O(n²) in
memory, which at a realistic 100k-point cloud is 10¹⁰ entries. The KD-tree
form was measured at 66 ms for 100k points and gives results identical to the
brute-force version on small inputs.

**Compression — two operators**

- `image_compress` — `jpeg` (lossy, configurable quality) or `png`
  (lossless), selected by `lossy: bool`. `quality` applies only when `lossy`
  is true; in the lossless mode it is rejected rather than silently ignored.
- `point_cloud_compress` — quantization plus zstd (lossy, configurable
  quantization `precision`) or plain zstd (lossless), with `precision`
  rejected in the lossless mode on the same rule.

Neither operator takes a target ratio. A ratio is an *outcome* of the quality
or precision setting and of the payload's own entropy, so a `ratio_target`
would have to iterate the encoder to hit it. The achieved ratio is reported
instead, per diagnostics period, through `Counters.byte_ratio` (§3.5).

These two are the proving ground for invariant 1's companion rule:
compression **must** carry `stamp_ns` and `source` through unchanged, which is
item 16's "保留原始采集时间与来源标识".

**Cleaning — one operator covering four defect classes**

`data_cleaner` handles missing values, outliers (n-sigma), timestamp disorder
(by `stamp_ns`) and duplicate frames (by `stamp_ns` paired with `source`, per
3.2.1).

A value-level defect is **repaired in place, never removed**: the operator
holds the last good value at that index. The elements of a state vector are
positional — joint 3, velocity x — so deleting element 2 would silently shift
the meaning of every element after it, which is a worse failure than the
defect being repaired and precisely the silent corruption item 16 forbids. It
also keeps the payload width stable, which downstream filters require. With no
history to hold from, the operator reports `missing` rather than inventing a
measurement, and that case is not an upgrade.

The n-sigma test has a documented limit: it measures the spread of the very
sample it judges, so one extreme value in a short vector inflates that spread
enough to stay inside its own threshold. The usable sigma therefore depends on
the vector width, and the delivered record uses 2.0 rather than 3.0 for a
width-8 vector.

It is the **only operator in the library permitted to upgrade `validity`**
(invariant 2), and the price is that every upgrade is counted and reported.
The four defect classes are counted **independently** and never merged into a
single total: "对被丢弃的数据计数并上报" must be able to distinguish missing
from outlier from disorder from duplicate.

**Format conversion — one bidirectional operator**

`ros2_codec` converts between `openrobot.*` and ROS 2 messages in both
directions. It starts from the existing implementations in
`dora-nav/peception/euclidean_cluster/`: `LidarRawObject_to_ros2.py` (208
lines) and `rgb_pointcloud_to_ros2.py` (95 lines), with their hard-coded
headers replaced by contract headers.

"通用机器人数据格式" resolves to ROS 2 messages. It is the only such format
with an existing implementation here, and the only one actually present in the
deployment.

**Chain tools — two, and they are not operators**

- `diag_collector` aggregates the per-stage diagnostics ports and computes
  reduction ratios and latencies. This is item 16's "逐级数据量与耗时统计
  脚本".
- `ab_compare` splits one input two ways — through the preprocessing chain and
  bypassing it — and compares the downstream outputs. This is item 16's
  "支持以同一输入对比启用前后的下游算子输出".

`diag_collector` runs as a dora node, because it has to subscribe to the live
diagnostics ports; it declares four optional stage inputs, which is a bounded
checkable shape, and a longer chain splits into two collectors. `ab_compare`
stays a script, since comparing two recorded streams needs no port of its own.
Neither is a framework.

Both the examples also need mock sources and a recording sink. Those are
declared in `dataflows/mocks/operators.yaml` rather than the pack's own
registry, because `operators.yaml` states what the pack *provides* and a mock
lidar is not a capability anyone deploys.

### 5.3 Schemas: eight

`openrobot.sensor.point_cloud/1.0.0`,
`openrobot.sensor.point_cloud_compressed/1.0.0`,
`openrobot.sensor.image/1.0.0`, `openrobot.sensor.image_compressed/1.0.0`,
`openrobot.state.vector/1.0.0`, `openrobot.interop.ros2_message/1.0.0`,
`openrobot.diag.counters/1.0.0`, `openrobot.diag.chain_report/1.0.0`.

Four of those are the raw payloads; the other four exist because building the
manifests showed that collapsing them would defeat check 1. A compressed
payload is a *different layout* from the samples it came from — a zstd frame
or a JPEG file rather than an array of samples — so `point_cloud_compressed`
and `image_compressed` are separate ids rather than later versions. That way
wiring a compressed stream into an operator expecting raw points is a blocking
pre-launch violation instead of a run-time crash. The codec needs
`interop.ros2_message`, and the collector's chain report is a product across
stages with no meaning for one stage alone, so it is separate from a single
operator's counters.

The point cloud is a **flat float32 arrow array with a declared field order**
(`x,y,z[,intensity]`, with `point_step` declared in the schema) rather than a
struct array. It is cheaper and matches the existing
`pa.array(np.array(...), type=pa.float32())` idiom.

### 5.4 Pack layout follows the inference pack

```text
capabilities/data-processing/
├── pack.yaml              # CapabilityPack, camelCase
├── operators.yaml         # port declarations, snake_case
├── pyproject.toml
├── conftest.py            # same sys.path handling as the inference pack
├── open_robot_dataproc/
│   ├── filter/{point_cloud_op,image_op,state_op}.py
│   ├── compress/{image_op,point_cloud_op}.py
│   ├── clean/cleaner_op.py
│   ├── convert/ros2_codec_op.py
│   └── tools/{diag_collector,ab_compare}.py
├── dataflows/{preprocess-chain.yml,ab-compare.yml}
└── tests/test_*.py
```

### 5.5 The two records are produced by running, not by writing

The deliverables "逐级数据量与耗时统计记录" and "对比测试记录" are run
outputs: `dataflows/preprocess-chain.yml` with `diag_collector` produces the
first, and `ab-compare.yml` produces the second. The implementation plan fixes
this as an explicit step, because otherwise these degrade into hand-written
documents, and hand-written ones collapse under the first detailed question at
acceptance.

## 6. Error handling

v1.3 §4.5 requires that "Safe failure is part of every interface". Four
failure classes have bounded behavior:

| Failure | Behavior |
|---|---|
| Pre-launch validation violation | Non-zero exit, no launch. The message names the node, the port, the expected value and the actual value |
| Malformed header construction (e.g. `validity != "ok"` with no `reason`) | The shared library **raises immediately** |
| Degraded upstream data (stale, missing, low confidence) | **Neither raises nor drops**; tags `validity` and forwards |
| Unwired diagnostics port | Warning only; the operator runs normally |

The middle boundary is the key one: **a coding error must raise, and dirty
data must not**. Conflating them yields one of two failure modes — a chain
that crashes on the first bad frame, or a miswritten operator that is never
discovered. The fourth row follows the same logic: diagnostics are off the
critical path, so a missing diagnostics wire must not block launch.

## 7. Testing

### 7.1 Four layers

1. **Unit tests** per operator, following the inference pack's pytest layout.
2. **Contract tests** against `open_robot_operator` itself: header
   construction, both invariants, `same_as` chain resolution, caret version
   matching, and positive and negative cases for each of the five checks.
3. **Conformance** — the validator **runs as a test**, across every
   `capabilities/*/operators.yaml` paired with every `dataflows/*.yml`, and
   must report zero violations. This turns drift between declarations and
   orchestration into a CI failure instead of an on-robot discovery.
4. **End to end** — both dataflows actually run, producing the two records of
   section 5.5.

### 7.2 Assurance is by mutation testing

Branch coverage is insufficient, and there is direct evidence from the
edge-inference work: a **doubly wrong** gate implementation passed all 16 of
its tests at 100% branch coverage. Mutation testing therefore defines the
targets, and the five targets correspond to the five load-bearing promises:

| Mutation | Must be caught by |
|---|---|
| Drop messages where `validity != "ok"` | Contract tests (invariant 1) |
| Rewrite `stamp_ns` to the current time in compression or conversion | Unit tests (item 16, "保留原始采集时间") |
| Make an output port declared with a literal frame emit its input's `frame_id` | Contract tests (§3.1 restatement rule, §4.1) |
| Let the cleaner upgrade `validity` without counting | Unit tests (invariant 2) |
| Change caret matching to exact equality, or to always true | Contract tests (check 1's positive and negative cases) |

Mutation runs must not execute alongside anything else that runs tests in the
same worktree, and `__pycache__` is cleared between runs, because
equal-length patches defeat `.pyc` invalidation.

## 8. Acceptance alignment

Each line of contract text maps to one nameable artifact. This table is the
defense at acceptance.

| Contract text (excerpt) | Delivered by | Evidence |
|---|---|---|
| 16 「滤波、压缩、数据清洗与格式转换四类算子」 | seven operators | `operators.yaml` plus unit tests |
| 16 「统一接口后可按需串接为预处理链路」 | `preprocess-chain.yml` | validator reports zero violations |
| 16 「滤波参数可配置」 | per-operator modes and parameters | unit tests |
| 16 「压缩参数…可配置并支持有损与无损两种模式，按统计周期记录实际压缩比」 | `lossy` with `quality`/`precision`; `Counters.byte_ratio` on the diagnostics port | unit tests, chain record |
| 16 「保留原始采集时间与来源标识」 | §3.1 propagated fields | mutation target 2 |
| 16 「对被丢弃或被修复的数据计数并上报，不静默丢弃」 | four independent counters | invariant 1, mutation targets 1 and 4 |
| 16 「字段语义、单位与时间戳在转换前后一致」 | `ros2_codec` | **round-trip test** — every field equal after a round trip |
| 16 「逐级统计数据量削减比例与处理耗时」 | `diag_collector` | run record |
| 16 「以同一输入对比启用前后的下游输出质量」 | `ab-compare.yml` | run record |
| 13 「统一声明输入输出数据结构、坐标系、物理单位与版本信息」 | `operators.yaml`, schemas, `units.yaml` | conformance tests |
| 14 「端口与坐标系字典」 | `frames.yaml`, `units.yaml` | normative text |
| 15 「统一的算子注册…机制」 | `operators.yaml`, normative text | normative text |

## 9. Decisions recorded

| Decision | Choice | Rationale |
|---|---|---|
| Target platforms | Simulation (mujoco) covers all four categories; selected real-machine measurements on the target robots | Matches the contract's "以目标平台实测结果为准" |
| Cognition inference placement | Reuses the edge-inference channel; the robot side addresses a capability ID only | `capabilities/inference/pack.yaml` already declares `robot.cognition.describe-scene` |
| Contract-layer languages | Python reference implementation; the C++ side only reads schemas | Keeps sub-project 1 unblocked; a bilingual contract would cost 1.5–2× and require keeping both in sync |
| Contract shape | Declarative port schemas **and** a runtime envelope, as one mechanism with two faces | The contract text requires both: the declarations for items 13–16's "统一声明…", the envelope for the "标识/计数/不静默丢弃" promises |
| Frame handling | Declare and check agreement; the envelope and validator never transform. Transformation is explicit, in a declared operator, through `open_robot_operator.transform` (restated 2026-10-20) | Five v1.3 items need transforms and nothing owned them; a static tree plus the latest pose meets every acceptance line without a TF buffer |
| Operator registry | A declarative `operators.yaml`, no runtime service | Item 15 asks for a 机制, which a manifest satisfies |
| Diagnostics | Per-stage counters, no per-message correlation | A header trail grows without bound with chain length |
| Staleness scope | `max_age_ms` is same-host only; cross-host staleness deferred | Needs a two-sided age rule and clock-offset handling, which the inference path already owns |
| Duplicate detection key | `stamp_ns` paired with `source`, not `seq` | `seq` is restated per producer, so duplicates are invisible in it |
| Fusion propagation | `stamp_ns` = min over parents; `source` = sorted unique joined with `+` | A fused frame must not claim a freshness no ingredient had |
| Upgrade accounting | The library counts it inside the deriving call | An operator-side increment would be a deletable, undetectable mutation |
| Bilateral image filter | Dropped | No `cv2`; absent from scipy and PIL; the contract text does not name it |
| Outlier neighbourhood | `scipy.spatial.cKDTree` | A pairwise matrix is O(n²) — 10¹⁰ entries at 100k points. Measured 66 ms at 100k |
| Compressed payloads | Their own schema ids, not later versions | Otherwise check 1 cannot catch a compressed stream wired into a raw-sample port |
| Value-level repair | Hold the last good value; never remove an element | A state vector's elements are positional, so deleting one shifts the meaning of the rest |
| `diag_collector` | A node with four optional stage inputs | It has to subscribe to live diagnostics ports; `ab_compare` needs no ports and stays a script |
| Mock declarations | A separate `dataflows/mocks/operators.yaml` | The registry states what the pack provides, and a mock lidar is not that |
| Runtime frame resolution | `output_frame()` resolves from the declaration | The spec claimed the library resolves it, and nothing implemented that claim |
| Frame-less payloads | A declared `none` frame | A `Header` needs a frame_id, and counters are in no frame |
| CLI placement | Library plus `python -m`, no §9.2 amendment this phase | Avoids making the prerequisite for three items wait on spec review |
| Downsampling and outlier rejection | Implemented in item 16; item 13 depends on them | They appeared in both items' text; contract text v1.3 assigns them to 16 and states in 13 that they are not re-delivered there (§11) |

## 10. Sub-project sequence

This spec covers 0 and 1. The remaining three follow the dependency order,
not the budget order.

| # | Sub-project | Depends on | Contract item |
|---|---|---|---|
| 0 | Operator contract layer | — | shared across 13–16 |
| 1 | Data-processing operator library | 0 | 16 (28万) |
| 2 | Perception operator extension (dora-nav) | 0, 1 | 13 (58万) |
| 3 | Control operator extension (dora-nav, dora-moveit2) | 0, 2 | 14 (66万) |
| 4 | Cognition operator library (via the edge-inference channel) | 0, 2, 3, inference pack, item 25's keypoints | 15 (48万) |

Sub-projects 0 and 1 ship together: a contract layer built alone tends to
become a paper specification, and the data-processing library is pure Python
with no hardware dependency, which makes it the cheapest possible first real
consumer. Its four operator classes exercise every clause of the contract —
"保留原始采集时间与来源标识", "对被丢弃的数据计数并上报，不静默丢弃", and
"转换前后字段语义、单位与时间戳一致".

If the contract layer is wrong, sub-projects 2 through 4 all have to be
reworked. Validating it with the 28万 item is the cheapest available mistake.

## 11. Amendment 2026-10-20: contract text v1.3

The tender workbook moved from v1.2 to v1.3. Column G — the 国家要求, which is
the actual obligation — is unchanged in all thirteen items, and so is every
price. What changed is column H and the delivery sheet for items 13–16, where
the extension text had promised work that column G does not ask for. Nine of
those changes are recorded below; four of them touch this spec.

### 11.1 What the workbook changed

| Item | v1.2 claimed | v1.3 claims | Why |
|---|---|---|---|
| 13 | Long-term tracking with lifecycle-tagged tracks | Nearest-neighbour association between adjacent frames giving a 3-D rate of change; no track management, no identity continuity | Column G asks only for 实时目标检测识别 |
| 13 | 不少于三类 sensors fused | 不少于两类, extensible per the technical attachment | 多模态 is satisfied by two modalities |
| 13 | A self-built annotated test set, delivered | A sample input manifest and output examples; samples from the attachment or a public dataset | No clause asks for data labelling, and v1.2 made it an obligation |
| 13 | Downsampling and outlier rejection delivered here | Provided by item 16, not re-delivered here | §5.1's boundary, now stated in the contract text |
| 14 | 力控及阻抗控制接口, unqualified | A unified call interface plus a clamp-check layer; no whole-machine force-servo figure promised | The torque path depends on what the robot exposes |
| 15 | Multiple candidate trajectories with probabilities | One best trajectory with a confidence; the payload keeps an extension slot for multiple candidates | Column G asks to 判断轨迹, singular |
| 15 | Upstream = 感知类算子输出的目标轨迹与关键点 | Upstream = the perception operators' target list and rate estimates, plus the motion-capture system's body and hand keypoints | Item 13 never produced keypoints, and no longer produces long-term tracks |
| 16 | 支持配置压缩比及是否有损 | Parameters (image quality or quantisation precision) configurable, lossy and lossless modes, achieved ratio recorded per diagnostics period | `ratio_target` was never implemented, and a per-frame ratio contradicts §3.5 |
| 16 | 对被丢弃的数据计数 | 对被丢弃或被修复的数据计数 | The cleaner repairs in place rather than removing; see §9's value-level repair row |

The quantitative acceptance floors also came down — 100 frames to 50, five
plans to three, ten IK poses to five, three collaboration scenarios at ten
trials each to one at five. Item 16's floors are unchanged, because that item
is built and verified and lowering them buys nothing.

### 11.2 Effect on this spec

**Nothing built changes.** Sub-projects 0 and 1 are shipped, and no clause the
amendment touches is implemented by either. What the amendment did reveal is
that parts of this spec had drifted from the code, and those are corrected in
place: §1's quote of item 15's upstream, §5.2's `ratio_target`, §8's three
rows that quoted superseded text, and §9's rationale for the 13/16 boundary.

`ratio_target` is the one worth naming separately. It appeared in §5.2 and in
§8's acceptance row, and it exists nowhere in the implementation — the spec
invented a parameter, the code shipped `quality` and `precision` instead, and
nothing caught the divergence because the acceptance table was never executed.
Had the workbook been written from §8, it would have promised a knob that does
not exist.

Two forward dependencies move:

- **Sub-project 2 (item 13)** loses the tracking work. It no longer carries
  coordinate transformation alone: `2026-10-20-coordinate-transformation-design.md`
  puts the library in `open_robot_operator.transform`, shared by items 13, 14,
  the motion-capture item and the simulator. Item 13 still owns fusion and
  camera projection, and calls `lookup` for their extrinsic half.
- **Sub-project 4 (item 15)** drops multi-candidate probabilistic prediction,
  which was its principal technical risk, and gains a dependency on contract
  item 25 (动捕采集系统) for body and hand keypoints. §10's table is updated.
  Its inference runs through the edge-inference channel, which lives on
  `feat/edge-inference-transparency` — unpushed, with its own task 9 amendment
  unapplied. Item 15's text now depends on a deliverable that is not yet on
  the remote.

Prices were held at 58/66/48/28. The scope came down and the money did not, so
the margin rose, unevenly: item 15 shed the most risk. If the split inside the
200万 is ever restated, that is where it should come from.
