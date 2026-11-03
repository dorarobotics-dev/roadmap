# Coordinate Transformation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the stack one checked way to change the frame a message is expressed in: a static extrinsic tree per robot, explicit composition with a published pose, a `frame_transform` operator, and a pre-launch check that refuses a frame change no calibration supports.

**Architecture:** Two modules, split by dependency:

- `open_robot_operator.frames` is numpy-free. It loads the frame dictionary and a robot's extrinsics, and decides which edges a transform uses. The validator imports only this module.
- `open_robot_operator.transform` does the arithmetic and is the only module that imports numpy, through the optional extra `[transform]`.

The new `capabilities/perception/` pack ships `frame_transform`, whose output frame is declared `env:TARGET_FRAME` — a new declaration form the validator resolves from the dataflow. Per-robot numbers live in `robots/<name>/extrinsics.yaml`.

**Tech Stack:** Python 3.10, numpy 2.2, pyarrow 25, PyYAML 6, jsonschema 4, pytest 9, dora-rs 1.0.1 (runtime only inside `main()`).

**Design doc:** `docs/superpowers/specs/2026-10-20-coordinate-transformation-design.md`. Task 1 appends its §12, which records where this plan corrects it; read §12 first.

---

## Environment facts established before planning

Measured on asus (10.10.5.7) on 2026-10-20.

| Fact | Consequence |
|---|---|
| The login shell sources ROS 2 humble, so `PYTHONPATH=/opt/ros/humble/...` leaks into the venv and pytest auto-loads `launch_testing`, which fails on `import lark` | **Every** pytest and sweep command in this plan is prefixed `PYTHONPATH=`. It is part of the command, not optional |
| Venv: `source /home/demo/Public/github_dimos/.venv-ors-operator/bin/activate` | Has numpy 2.2.6, scipy, jsonschema, dora-rs 1.0.1 and the `dora` CLI |
| Baseline: `tests/test_specs.py` 66, contract package 308, data-processing 349, all passing; the sweep is 0/10 surviving | Re-check the baseline before Task 2. Any number that drops later is a regression |
| `1.001` s × 1e9 truncates to `1000999999` | The rounding test uses that value |
| `open_robot_dataproc.mocks.point_cloud_source.frame(0, points=256)` has first point `[2.7392337, -4.6042657, -9.18053, -9.669447]` | Task 11's record test recomputes its expectation from `frame(0)` with a hand formula, never with the code under test |
| dora runs a node with the dataflow file's directory as cwd | Relative paths in a dataflow's `env:` resolve against `dataflows/`, and the validator resolves them the same way |

Run every command from the repository root `/home/demo/Public/github_dimos/open-robot-stack-operator-contract` unless a step says otherwise.

## File structure

**Contract layer — `packages/open-robot-operator/`**

| File | Change | Responsibility |
|---|---|---|
| `open_robot_operator/frames.py` | create | Frame dictionary, extrinsics loading and checks, `Route` finding. No numpy |
| `open_robot_operator/transform.py` | create | `Transform`, `lookup`, `pose_transform`, `rotation_matrix`, `xyzw_from_named`. Only numpy importer |
| `open_robot_operator/wire.py` | modify | `stamp_ns_from_seconds`; `output_frame` refuses an unresolved `env:` |
| `open_robot_operator/declare.py` | modify | `env:<VAR>` output frame form, `PortDecl.env_var` |
| `open_robot_operator/resolve.py` | modify | `Graph.env`; `resolve_frame` resolves `env:` |
| `open_robot_operator/validate.py` | modify | `Dataflow.env` and `base_dir`; check 6 `transform`; `--extrinsics` and `--frames` |
| `open_robot_operator/__init__.py` | modify | Export the frames API and `stamp_ns_from_seconds` |
| `pyproject.toml` | modify | Version 0.2.0; extra `transform = ["numpy>=1.24"]` |
| `tests/test_frames.py`, `tests/test_transform.py` | create | |
| `tests/test_wire.py`, `test_declare.py`, `test_resolve.py`, `test_validate.py` | modify | |

**Normative artifacts**

| File | Change |
|---|---|
| `specs/operators/frames.yaml` | 1.0.0 → 1.1.0: `kind`, `base_footprint`, `rejected_names` |
| `specs/operators/schemas/openrobot.state.pose-1.0.0.json` | create |
| `specs/operators/extrinsics.schema.json` | create |
| `robots/simulated-mobile-robot/extrinsics.yaml` | create |
| `tests/test_specs.py` | modify |

**Perception pack — `capabilities/perception/`** (new)

| File | Responsibility |
|---|---|
| `pack.yaml`, `operators.yaml`, `pyproject.toml`, `conftest.py` | Manifests, registry, import roots |
| `open_robot_perception/transform/frame_transform_op.py` | The operator: pure functions plus `main()` |
| `open_robot_perception/mocks/cloud_sink.py` | Records the first cloud of a run |
| `dataflows/node.sh`, `dataflows/transform-chain.yml`, `dataflows/mocks/operators.yaml` | Launcher, the e2e chain, mock declarations |
| `records/transform-chain.json` | Produced by running Task 11, then committed |
| `tests/test_frame_transform.py`, `tests/test_conformance.py`, `tests/test_record.py` | |

**Other:** `tools/mutation-sweep.py` (perception suite plus seven anchors), the contract spec (§2.4, §9, §11.2), `component-lock.yaml`, and `capabilities/data-processing/pack.yaml` (version references).

---

## Task 1: Record the planning corrections in the spec

**Files:**
- Modify: `docs/superpowers/specs/2026-10-20-coordinate-transformation-design.md` (append §12)

- [ ] **Step 1: Append §12**

Append this to the end of the spec file:

```markdown

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
```

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/specs/2026-10-20-coordinate-transformation-design.md
git commit -m "docs(spec): nine corrections found while planning coordinate transforms"
```

---

## Task 2: The frame dictionary, 1.1.0

**Files:**
- Modify: `specs/operators/frames.yaml` (whole file)
- Test: `tests/test_specs.py`

- [ ] **Step 1: Check the baseline**

Run:
```bash
source /home/demo/Public/github_dimos/.venv-ors-operator/bin/activate
PYTHONPATH= python -m pytest tests/test_specs.py -q
PYTHONPATH= python -m pytest packages/open-robot-operator/tests -q
PYTHONPATH= python -m pytest capabilities/data-processing/tests -q
```
Expected: `66 passed`, `308 passed`, `349 passed`. If any differs, stop and find out why before going on.

- [ ] **Step 2: Write the failing tests**

In `tests/test_specs.py`, replace the parametrized `test_the_frames_the_operators_reference_are_declared` with the version below, and append the other tests to the end of the file:

```python
@pytest.mark.parametrize(
    "name", ["base_link", "base_footprint", "rslidar", "camera_front", "tool0", "map", "odom"]
)
def test_the_frames_the_operators_reference_are_declared(name):
    assert name in {f["name"] for f in FRAMES["frames"]}
```

```python
KINDS = {"fixed", "dynamic", "mounted", "none"}


def test_every_frame_declares_a_known_kind():
    for frame in FRAMES["frames"]:
        assert frame.get("kind") in KINDS, frame["name"]


def test_the_kinds_are_the_ones_the_transform_design_fixes():
    kinds = {f["name"]: f["kind"] for f in FRAMES["frames"]}
    assert kinds["none"] == "none"
    assert kinds["map"] == "fixed"
    assert kinds["odom"] == "dynamic"
    assert kinds["base_footprint"] == "dynamic"
    assert kinds["tool0"] == "dynamic", "the flange moves with the joints"
    for name in ("base_link", "rslidar", "camera_front", "imu_link"):
        assert kinds[name] == "mounted", name


def test_only_fixed_and_none_frames_are_roots():
    for frame in FRAMES["frames"]:
        is_root = frame["parent"] is None
        assert is_root == (frame["kind"] in ("fixed", "none")), frame["name"]


def test_base_footprint_sits_between_odom_and_base_link():
    """The simulator, its URDF and its odometry all put odometry here."""
    parents = {f["name"]: f["parent"] for f in FRAMES["frames"]}
    assert parents["base_footprint"] == "odom"
    assert parents["base_link"] == "base_footprint"


def test_rejected_names_point_at_frames_and_are_not_frames_themselves():
    names = {f["name"] for f in FRAMES["frames"]}
    rejected = FRAMES["rejected_names"]
    assert rejected, "the upstream names have to be listed to be rejected"
    for bad, good in rejected.items():
        assert bad not in names, bad
        assert good in names, (bad, good)


@pytest.mark.parametrize(
    "upstream", ["world", "rslidar_frame", "lidar", "lidar_link", "livox_frame", "camera_link"]
)
def test_every_upstream_name_the_survey_found_is_rejected(upstream):
    assert upstream in FRAMES["rejected_names"]
```

- [ ] **Step 3: Run them to see them fail**

Run: `PYTHONPATH= python -m pytest tests/test_specs.py -q`
Expected: FAIL. `base_footprint` and `camera_front` are missing from the parametrized test, and there is a `KeyError: 'kind'` and a `KeyError: 'rejected_names'`.

- [ ] **Step 4: Rewrite `specs/operators/frames.yaml`**

Replace the whole file:

```yaml
# Frame dictionary. The other half of contract item 14's 端口与坐标系字典.
#
# `parent` records the tree the fleet intends. Since 1.1.0 it is load-bearing:
# `kind` says how a frame relates to its parent, and per-robot extrinsics
# (robots/<name>/extrinsics.yaml) may calibrate only `mounted` edges.
#
# The envelope and the validator still NEVER transform. A frame change happens
# only inside an operator that declares it, through
# open_robot_operator.transform, against a calibration the validator has
# checked. See docs/superpowers/specs/2026-10-20-coordinate-transformation-design.md.
#
# kind:
#   fixed    a root that does not move
#   dynamic  its pose relative to its parent changes at run time; it comes
#            from a published openrobot.state.pose message, never from a file
#   mounted  rigidly attached to its parent; calibrated per robot
#   none     the frame-less sentinel; never part of a transform
contract_version: 1.1.0
frames:
  - name: none
    parent: null
    kind: none
    description: >-
      No spatial meaning. For payloads that are not in any frame, such as the
      diagnostic counters. A Header still needs a frame_id, so frame-less
      payloads name this one rather than leaving it blank or using 'any'.
  - name: map
    parent: null
    kind: fixed
    description: The fixed world frame a map is expressed in.
  - name: odom
    parent: map
    kind: dynamic
    description: Continuous odometric frame; drifts, never jumps.
  - name: base_footprint
    parent: odom
    kind: dynamic
    description: >-
      Ground projection of the robot body; the frame wheel odometry reports.
      The DORA_NAV simulator, its URDF and its odometry (child_frame_id
      base_footprint) all use this split.
  - name: base_link
    parent: base_footprint
    kind: mounted
    description: Robot body frame, origin at the chassis centre, x forward, y left, z up.
  - name: rslidar
    parent: base_link
    kind: mounted
    description: >-
      The primary 3-D lidar as mounted, whatever its make -- RoboSense, Livox
      or simulated. Upstream calls it rslidar_frame, livox_frame, lidar or
      lidar_link; adapters rename to this.
  - name: camera_front
    parent: base_link
    kind: mounted
    description: Front camera optical frame, z along the optical axis, x right, y down.
  - name: imu_link
    parent: base_link
    kind: mounted
    description: IMU frame, axes as mounted.
  - name: tool0
    parent: base_link
    kind: dynamic
    description: >-
      Manipulator flange frame, for the control operators' IK and force ports.
      Dynamic because it moves with the joints; its pose comes from forward
      kinematics, published as a pose, never from a calibration file.
# Upstream names, mapped to the name to use instead. A rejected name is never
# an alias: the validator and the library refuse it and say what to use.
rejected_names:
  world: map
  rslidar_frame: rslidar
  lidar: rslidar
  lidar_link: rslidar
  livox_frame: rslidar
  camera_link: camera_front
```

- [ ] **Step 5: Run the spec tests and the data-processing suite**

Run:
```bash
PYTHONPATH= python -m pytest tests/test_specs.py -q
PYTHONPATH= python -m pytest capabilities/data-processing/tests -q
```
Expected: specs PASS with 79 tests (66, plus 2 new cases in the replaced parametrized test, plus 11 from the six new functions); data-processing `349 passed`.

- [ ] **Step 6: Commit**

```bash
git add specs/operators/frames.yaml tests/test_specs.py
git commit -m "feat(specs): frame dictionary 1.1.0 with kinds, base_footprint and rejected names"
```

---

## Task 3: `frames.py` — the dictionary

**Files:**
- Create: `packages/open-robot-operator/open_robot_operator/frames.py`
- Test: `packages/open-robot-operator/tests/test_frames.py`

- [ ] **Step 1: Write the failing tests**

Create `packages/open-robot-operator/tests/test_frames.py`:

```python
import textwrap
from pathlib import Path

import pytest
import yaml

from open_robot_operator.frames import (
    FrameError,
    UnknownFrameError,
    load_frames,
    parse_frames,
)

FRAMES_YAML = textwrap.dedent(
    """
    contract_version: 1.1.0
    frames:
      - {name: none, parent: null, kind: none}
      - {name: map, parent: null, kind: fixed}
      - {name: odom, parent: map, kind: dynamic}
      - {name: base_footprint, parent: odom, kind: dynamic}
      - {name: base_link, parent: base_footprint, kind: mounted}
      - {name: rslidar, parent: base_link, kind: mounted}
      - {name: camera_front, parent: base_link, kind: mounted}
      - {name: imu_link, parent: base_link, kind: mounted}
    rejected_names:
      world: map
      lidar_link: rslidar
    """
)
FRAMES = parse_frames(yaml.safe_load(FRAMES_YAML))
REPO = Path(__file__).resolve().parents[3]


def _doc(frames, rejected=None):
    doc = {"contract_version": "1.1.0", "frames": frames}
    if rejected is not None:
        doc["rejected_names"] = rejected
    return doc


# --- the dictionary ----------------------------------------------------------

def test_a_known_frame_is_returned_with_its_kind_and_parent():
    frame = FRAMES.require("rslidar")
    assert (frame.name, frame.parent, frame.kind) == ("rslidar", "base_link", "mounted")


def test_a_rejected_name_is_refused_with_its_replacement():
    with pytest.raises(UnknownFrameError, match="use 'map'"):
        FRAMES.require("world")


def test_an_unknown_name_is_refused():
    with pytest.raises(UnknownFrameError, match="not in the frame dictionary"):
        FRAMES.require("velodyne")


def test_unknown_frame_error_is_a_value_error():
    """Callers that already catch ValueError keep working."""
    assert issubclass(UnknownFrameError, ValueError)


def test_chain_walks_from_a_frame_to_its_root():
    assert FRAMES.chain("rslidar") == ["rslidar", "base_link", "base_footprint", "odom", "map"]
    assert FRAMES.chain("map") == ["map"]


@pytest.mark.parametrize(
    "frames, match",
    [
        ([{"name": "a", "parent": None, "kind": "floating"}], "kind 'floating'"),
        ([{"name": "a", "parent": None, "kind": "mounted"}], "needs a parent"),
        ([{"name": "a", "parent": None, "kind": "dynamic"}], "needs a parent"),
        (
            [{"name": "m", "parent": None, "kind": "fixed"},
             {"name": "a", "parent": "m", "kind": "fixed"}],
            "cannot have a parent",
        ),
        ([{"name": "a", "parent": "ghost", "kind": "mounted"}], "unknown parent 'ghost'"),
        (
            [{"name": "a", "parent": None, "kind": "fixed"},
             {"name": "a", "parent": None, "kind": "fixed"}],
            "more than once",
        ),
        ([{"name": "", "parent": None, "kind": "fixed"}], "non-empty name"),
        (
            [{"name": "a", "parent": "b", "kind": "dynamic"},
             {"name": "b", "parent": "a", "kind": "dynamic"}],
            "cycle",
        ),
    ],
)
def test_a_malformed_dictionary_is_refused(frames, match):
    with pytest.raises(FrameError, match=match):
        parse_frames(_doc(frames))


def test_a_rejected_name_may_not_also_be_a_frame():
    frames = [{"name": "map", "parent": None, "kind": "fixed"}]
    with pytest.raises(FrameError, match="both a frame and a rejected name"):
        parse_frames(_doc(frames, {"map": "map"}))


def test_a_rejected_name_must_point_at_a_frame():
    frames = [{"name": "map", "parent": None, "kind": "fixed"}]
    with pytest.raises(FrameError, match="unknown frame 'globe'"):
        parse_frames(_doc(frames, {"world": "globe"}))


def test_a_document_without_a_frames_list_is_refused():
    with pytest.raises(FrameError, match="'frames' list"):
        parse_frames({"contract_version": "1.1.0"})


def test_the_repository_dictionary_loads():
    frames = load_frames(REPO / "specs" / "operators" / "frames.yaml")
    assert frames.require("camera_front").kind == "mounted"
    assert frames.require("tool0").kind == "dynamic"
    assert frames.rejected["livox_frame"] == "rslidar"
```

- [ ] **Step 2: Run them to see them fail**

Run: `cd packages/open-robot-operator && PYTHONPATH= python -m pytest tests/test_frames.py -q; cd -`
Expected: FAIL with `ModuleNotFoundError: No module named 'open_robot_operator.frames'`.

- [ ] **Step 3: Write the dictionary half of `frames.py`**

Create `packages/open-robot-operator/open_robot_operator/frames.py`:

```python
"""The frame dictionary and per-robot extrinsics, without any arithmetic.

The validator has to know before launch whether a static path exists between
two frames, and it must not need numpy to find out. So everything about
*which* edges a transform would use lives here, and the arithmetic that
composes them lives in `transform`, the only module that imports numpy.
"""

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import yaml

KINDS = ("fixed", "dynamic", "mounted", "none")

# Upstream dora-nav normalises in float32, which leaves the norm about 1e-7
# off; 1e-6 accepts that and still refuses a quaternion nobody normalised.
QUATERNION_NORM_TOLERANCE = 1e-6


class FrameError(ValueError):
    """A frame or calibration problem. A ValueError, so callers that already
    catch ValueError keep working."""


class UnknownFrameError(FrameError):
    """The name is not in the dictionary, or is an upstream name it rejects."""


class MissingExtrinsicError(FrameError):
    """A static path needs an edge the robot's calibration does not hold."""


class DynamicEdgeError(FrameError):
    """A static path would cross an edge that only a published pose can give."""


@dataclass(frozen=True)
class Frame:
    name: str
    parent: Optional[str]
    kind: str


@dataclass(frozen=True)
class FrameDict:
    frames: Dict[str, Frame]
    rejected: Dict[str, str]

    def require(self, name: str) -> Frame:
        if name in self.rejected:
            raise UnknownFrameError(
                f"frame {name!r} is an upstream name the dictionary rejects; "
                f"use {self.rejected[name]!r}")
        if name not in self.frames:
            raise UnknownFrameError(f"frame {name!r} is not in the frame dictionary")
        return self.frames[name]

    def chain(self, name: str) -> List[str]:
        """`name` and its ancestors, nearest first, ending at a root."""
        out: List[str] = []
        node: Optional[str] = name
        while node is not None:
            out.append(node)
            node = self.frames[node].parent
        return out


def parse_frames(doc: object) -> FrameDict:
    if not isinstance(doc, dict) or not isinstance(doc.get("frames"), list):
        raise FrameError("a frame dictionary must be a mapping with a 'frames' list")
    frames: Dict[str, Frame] = {}
    for entry in doc["frames"]:
        if not isinstance(entry, dict):
            raise FrameError(f"each frame must be a mapping, got {entry!r}")
        name = entry.get("name")
        kind = entry.get("kind")
        if not isinstance(name, str) or not name:
            raise FrameError(f"a frame needs a non-empty name, got {entry!r}")
        if name in frames:
            raise FrameError(f"frame {name!r} is declared more than once")
        if kind not in KINDS:
            raise FrameError(f"frame {name!r} has kind {kind!r}; expected one of {KINDS}")
        frames[name] = Frame(name=name, parent=entry.get("parent"), kind=kind)

    for frame in frames.values():
        if frame.parent is not None and frame.parent not in frames:
            raise FrameError(f"frame {frame.name!r} names unknown parent {frame.parent!r}")
        if frame.kind in ("dynamic", "mounted") and frame.parent is None:
            raise FrameError(f"{frame.kind} frame {frame.name!r} needs a parent")
        if frame.kind in ("fixed", "none") and frame.parent is not None:
            raise FrameError(f"{frame.kind} frame {frame.name!r} cannot have a parent")

    for start in frames:
        seen = set()
        node: Optional[str] = start
        while node is not None:
            if node in seen:
                raise FrameError(f"the frame tree has a cycle through {node!r}")
            seen.add(node)
            node = frames[node].parent

    rejected = doc.get("rejected_names") or {}
    if not isinstance(rejected, dict):
        raise FrameError("rejected_names must map an upstream name to a frame")
    for bad, good in rejected.items():
        if bad in frames:
            raise FrameError(f"{bad!r} is both a frame and a rejected name")
        if good not in frames:
            raise FrameError(f"rejected name {bad!r} points at unknown frame {good!r}")
    return FrameDict(frames=frames, rejected=dict(rejected))


def load_frames(path: Union[str, Path]) -> FrameDict:
    return parse_frames(yaml.safe_load(Path(path).read_text(encoding="utf-8")))
```

- [ ] **Step 4: Run the tests to see them pass**

Run: `cd packages/open-robot-operator && PYTHONPATH= python -m pytest tests/test_frames.py -q; cd -`
Expected: PASS (17 tests).

- [ ] **Step 5: Commit**

```bash
git add packages/open-robot-operator/open_robot_operator/frames.py packages/open-robot-operator/tests/test_frames.py
git commit -m "feat(operator): frame dictionary loader with kinds and rejected names"
```

---

## Task 4: `frames.py` — extrinsics and routes

**Files:**
- Modify: `packages/open-robot-operator/open_robot_operator/frames.py` (append)
- Test: `packages/open-robot-operator/tests/test_frames.py` (append)

- [ ] **Step 1: Write the failing tests**

First extend the import at the top of `tests/test_frames.py` to:

```python
from open_robot_operator.frames import (
    DynamicEdgeError,
    FrameError,
    MissingExtrinsicError,
    UnknownFrameError,
    load_extrinsics,
    load_frames,
    parse_extrinsics,
    parse_frames,
)
```

Then append to the file:

```python
# --- extrinsics --------------------------------------------------------------

CAMERA_Q = (-0.5, 0.5, -0.5, 0.5)  # base_link -> optical: z forward, x right, y down


def edge(parent, child, t=(0.0, 0.0, 0.0), q=(0.0, 0.0, 0.0, 1.0)):
    return {"parent": parent, "child": child, "translation_m": list(t), "rotation_xyzw": list(q)}


def extrinsics_doc(*transforms):
    return {
        "contract_version": "1.0.0",
        "robot": "test-bot",
        "calibrated": "2026-10-20",
        "source": "unit-test fixture",
        "transforms": list(transforms),
    }


FULL = parse_extrinsics(
    extrinsics_doc(
        edge("base_footprint", "base_link", (0.0, 0.0, 0.1)),
        edge("base_link", "rslidar", (0.25, 0.0, 0.25)),
        edge("base_link", "camera_front", (0.40, 0.0, 0.35), CAMERA_Q),
    ),
    FRAMES,
)


def test_extrinsics_are_keyed_by_child():
    assert set(FULL.edges) == {"base_link", "rslidar", "camera_front"}
    assert FULL.edges["camera_front"].rotation_xyzw == CAMERA_Q
    assert FULL.robot == "test-bot"


@pytest.mark.parametrize(
    "entry, match",
    [
        (edge("odom", "base_footprint"), "only mounted frames are calibrated"),
        (edge("map", "odom"), "only mounted frames are calibrated"),
        (edge("map", "rslidar"), "hangs from 'base_link'"),
        (edge("base_link", "lidar_link"), "use 'rslidar'"),
        (edge("base_link", "velodyne"), "not in the frame dictionary"),
        (edge("base_link", "rslidar", q=(0.0, 0.0, 0.0, 0.9)), "unit quaternion"),
        (edge("base_link", "rslidar", q=(0.0, 0.0, 0.0, 1.0 + 2e-6)), "unit quaternion"),
        (edge("base_link", "rslidar", t=(0.0, float("nan"), 0.0)), "not a finite number"),
        (edge("base_link", "rslidar", t=(0.0, 0.0)), "list of 3 numbers"),
        (edge("base_link", "rslidar", q=(0.0, 0.0, 1.0)), "list of 4 numbers"),
        (edge("base_link", "rslidar", t=(True, 0.0, 0.0)), "not a finite number"),
        ("base_link -> rslidar", "must be a mapping"),
    ],
)
def test_a_bad_extrinsic_is_refused(entry, match):
    with pytest.raises(FrameError, match=match):
        parse_extrinsics(extrinsics_doc(entry), FRAMES)


def test_a_quaternion_within_tolerance_is_accepted_and_not_normalised():
    q = (0.0, 0.0, 0.0, 1.0 + 5e-7)
    loaded = parse_extrinsics(extrinsics_doc(edge("base_link", "rslidar", q=q)), FRAMES)
    assert loaded.edges["rslidar"].rotation_xyzw == q


def test_a_child_may_be_calibrated_only_once():
    with pytest.raises(FrameError, match="more than once"):
        parse_extrinsics(
            extrinsics_doc(edge("base_link", "rslidar"), edge("base_link", "rslidar")), FRAMES)


@pytest.mark.parametrize("key", ["contract_version", "robot", "calibrated", "source", "transforms"])
def test_every_top_level_key_is_required(key):
    doc = extrinsics_doc(edge("base_link", "rslidar"))
    del doc[key]
    with pytest.raises(FrameError, match=f"missing the required key '{key}'"):
        parse_extrinsics(doc, FRAMES)


def test_an_empty_calibration_is_refused():
    with pytest.raises(FrameError, match="non-empty list"):
        parse_extrinsics(extrinsics_doc(), FRAMES)


def test_load_extrinsics_records_its_path(tmp_path):
    path = tmp_path / "extrinsics.yaml"
    path.write_text(yaml.safe_dump(extrinsics_doc(edge("base_link", "rslidar"))), encoding="utf-8")
    assert load_extrinsics(path, FRAMES).path == path


# --- routes ------------------------------------------------------------------

def test_a_route_climbs_to_the_common_ancestor_and_descends():
    route = FULL.route("rslidar", "camera_front")
    assert [e.child for e in route.up] == ["rslidar"]
    assert [e.child for e in route.down] == ["camera_front"]


def test_a_route_descends_from_the_ancestor_towards_the_target():
    route = FULL.route("base_footprint", "camera_front")
    assert route.up == ()
    assert [e.child for e in route.down] == ["base_link", "camera_front"]


def test_a_route_to_itself_uses_no_edges():
    route = FULL.route("rslidar", "rslidar")
    assert route.up == () and route.down == ()


def test_a_missing_extrinsic_is_an_error_never_identity():
    with pytest.raises(MissingExtrinsicError, match="never assumed to be identity"):
        FULL.route("imu_link", "base_link")


def test_a_static_route_never_crosses_a_dynamic_edge():
    with pytest.raises(DynamicEdgeError, match="'odom' -> 'base_footprint'"):
        FULL.route("rslidar", "odom")


def test_the_frame_less_sentinel_is_never_part_of_a_route():
    with pytest.raises(UnknownFrameError, match="never part of a transform"):
        FULL.route("none", "base_link")


def test_a_route_refuses_a_rejected_name():
    with pytest.raises(UnknownFrameError, match="use 'map'"):
        FULL.route("rslidar", "world")
```

- [ ] **Step 2: Run them to see them fail**

Run: `cd packages/open-robot-operator && PYTHONPATH= python -m pytest tests/test_frames.py -q; cd -`
Expected: FAIL with `ImportError: cannot import name 'load_extrinsics'`.

- [ ] **Step 3: Append the extrinsics half to `frames.py`**

Append to `packages/open-robot-operator/open_robot_operator/frames.py`:

```python
@dataclass(frozen=True)
class Edge:
    """One calibrated mounting: the pose of `child` expressed in `parent`."""

    parent: str
    child: str
    translation_m: Tuple[float, float, float]
    rotation_xyzw: Tuple[float, float, float, float]


@dataclass(frozen=True)
class Route:
    """The edges a static transform from `src` to `dst` uses.

    `up` climbs from `src` to the common ancestor, each edge applied child to
    parent. `down` descends from the common ancestor to `dst`, each edge
    applied parent to child -- that is, inverted.
    """

    src: str
    dst: str
    up: Tuple[Edge, ...]
    down: Tuple[Edge, ...]


@dataclass(frozen=True)
class Extrinsics:
    robot: str
    source: str
    frames: FrameDict
    edges: Dict[str, Edge]
    path: Optional[Path] = None

    def route(self, src: str, dst: str) -> Route:
        for name in (src, dst):
            if self.frames.require(name).kind == "none":
                raise UnknownFrameError(
                    "frame 'none' marks a payload with no spatial meaning and is "
                    "never part of a transform")
        up_chain = self.frames.chain(src)
        down_chain = self.frames.chain(dst)
        common = next((name for name in up_chain if name in down_chain), None)
        if common is None:
            raise MissingExtrinsicError(f"{src!r} and {dst!r} share no ancestor in the frame tree")
        up = self._edges(up_chain[: up_chain.index(common)], src, dst)
        down = self._edges(down_chain[: down_chain.index(common)], src, dst)
        return Route(src=src, dst=dst, up=tuple(up), down=tuple(reversed(down)))

    def _edges(self, children: List[str], src: str, dst: str) -> List[Edge]:
        out: List[Edge] = []
        for child in children:
            frame = self.frames.frames[child]
            if frame.kind == "dynamic":
                raise DynamicEdgeError(
                    f"{src!r} -> {dst!r} crosses the dynamic edge "
                    f"{frame.parent!r} -> {child!r}; compose with a published "
                    "pose instead of a static lookup")
            edge = self.edges.get(child)
            if edge is None:
                raise MissingExtrinsicError(
                    f"{src!r} -> {dst!r} needs the extrinsic {frame.parent!r} -> "
                    f"{child!r}, which {self.robot!r} does not calibrate; a "
                    "missing extrinsic is never assumed to be identity")
            out.append(edge)
        return out


_REQUIRED = ("contract_version", "robot", "calibrated", "source", "transforms")


def _numbers(value: object, count: int, label: str, where: str) -> tuple:
    if not isinstance(value, list) or len(value) != count:
        raise FrameError(f"{where}: {label} must be a list of {count} numbers, got {value!r}")
    out = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(item):
            raise FrameError(f"{where}: {label} holds {item!r}, which is not a finite number")
        out.append(float(item))
    return tuple(out)


def _edge(entry: object, frames: FrameDict, where: str) -> Edge:
    if not isinstance(entry, dict):
        raise FrameError(f"{where}: each transform must be a mapping, got {entry!r}")
    parent = entry.get("parent")
    child = entry.get("child")
    label = f"{where}: {parent} -> {child}"
    frames.require(parent)
    frame = frames.require(child)
    if frame.kind != "mounted":
        raise FrameError(
            f"{label}: {child!r} is {frame.kind}, and only mounted frames are "
            "calibrated; a dynamic edge comes from a published pose")
    if frame.parent != parent:
        raise FrameError(
            f"{label}: the frame dictionary says {child!r} hangs from {frame.parent!r}")
    translation = _numbers(entry.get("translation_m"), 3, "translation_m", label)
    rotation = _numbers(entry.get("rotation_xyzw"), 4, "rotation_xyzw", label)
    norm = math.sqrt(sum(c * c for c in rotation))
    if abs(norm - 1.0) > QUATERNION_NORM_TOLERANCE:
        raise FrameError(
            f"{label}: rotation_xyzw has norm {norm!r}; it must be a unit "
            "quaternion, and it is not normalised for you")
    return Edge(parent=parent, child=child, translation_m=translation, rotation_xyzw=rotation)


def parse_extrinsics(doc: object, frames: FrameDict, path: Optional[Path] = None) -> Extrinsics:
    where = str(path) if path is not None else "extrinsics"
    if not isinstance(doc, dict):
        raise FrameError(f"{where}: must be a mapping")
    for key in _REQUIRED:
        if key not in doc:
            raise FrameError(f"{where}: missing the required key {key!r}")
    entries = doc["transforms"]
    if not isinstance(entries, list) or not entries:
        raise FrameError(f"{where}: 'transforms' must be a non-empty list")
    edges: Dict[str, Edge] = {}
    for entry in entries:
        edge = _edge(entry, frames, where)
        if edge.child in edges:
            raise FrameError(f"{where}: {edge.child!r} is calibrated more than once")
        edges[edge.child] = edge
    return Extrinsics(robot=str(doc["robot"]), source=str(doc["source"]),
                      frames=frames, edges=edges, path=path)


def load_extrinsics(path: Union[str, Path], frames: FrameDict) -> Extrinsics:
    path = Path(path)
    return parse_extrinsics(yaml.safe_load(path.read_text(encoding="utf-8")), frames, path)
```

- [ ] **Step 4: Run the tests to see them pass**

Run: `cd packages/open-robot-operator && PYTHONPATH= python -m pytest tests/test_frames.py -q; cd -`
Expected: PASS (46 tests).

- [ ] **Step 5: Commit**

```bash
git add packages/open-robot-operator/open_robot_operator/frames.py packages/open-robot-operator/tests/test_frames.py
git commit -m "feat(operator): per-robot extrinsics and static routes; missing is never identity"
```

---

## Task 5: `transform.py`, the stamp helper, and the package metadata

**Files:**
- Create: `packages/open-robot-operator/open_robot_operator/transform.py`
- Modify: `packages/open-robot-operator/open_robot_operator/wire.py` (add one function)
- Modify: `packages/open-robot-operator/open_robot_operator/__init__.py`
- Modify: `packages/open-robot-operator/pyproject.toml`
- Test: `packages/open-robot-operator/tests/test_transform.py`, `tests/test_wire.py`

- [ ] **Step 1: Write the failing transform tests**

Create `packages/open-robot-operator/tests/test_transform.py`:

```python
"""Every expected number here was computed by hand (and cross-checked with
scipy when the plan was written), never by the code under test. Fixtures are
asymmetric on purpose: a symmetric rotation passes a swapped quaternion order."""

import math

import numpy as np
import pytest
import yaml

from open_robot_operator.envelope import Header
from open_robot_operator.frames import DynamicEdgeError, FrameError, parse_extrinsics, parse_frames
from open_robot_operator.transform import (
    FrameOrderError,
    Transform,
    lookup,
    pose_transform,
    rotation_matrix,
    xyzw_from_named,
)

from tests.test_frames import CAMERA_Q, FRAMES_YAML, edge, extrinsics_doc

FRAMES = parse_frames(yaml.safe_load(FRAMES_YAML))
EXT = parse_extrinsics(
    extrinsics_doc(
        edge("base_footprint", "base_link", (0.0, 0.0, 0.1)),
        edge("base_link", "rslidar", (0.25, 0.0, 0.25)),
        edge("base_link", "camera_front", (0.40, 0.0, 0.35), CAMERA_Q),
    ),
    FRAMES,
)
S = math.sin(math.pi / 4)  # a 90-degree yaw is (0, 0, S, S) in xyzw
POSE = "openrobot.state.pose/1.0.0"


def pose_header(frame_id="odom", **overrides):
    fields = dict(schema=POSE, frame_id=frame_id, seq=0, stamp_ns=1_000, source="test.localizer")
    fields.update(overrides)
    return Header(**fields)


# --- rotation ----------------------------------------------------------------

def test_the_camera_quaternion_gives_the_optical_axes_as_columns():
    expected = np.array([[0.0, 0.0, 1.0], [-1.0, 0.0, 0.0], [0.0, -1.0, 0.0]])
    assert np.allclose(rotation_matrix(CAMERA_Q), expected)


def test_the_identity_quaternion_is_xyzw_not_wxyz():
    """(0, 0, 0, 1) read as w, x, y, z would be a half turn about z."""
    assert np.allclose(rotation_matrix((0.0, 0.0, 0.0, 1.0)), np.eye(3))


def test_a_quarter_yaw_turns_x_into_y():
    assert np.allclose(rotation_matrix((0.0, 0.0, S, S)) @ [1.0, 0.0, 0.0], [0.0, 1.0, 0.0])


# --- Transform ---------------------------------------------------------------

def test_a_yaw_plus_translation_moves_a_point_where_the_hand_says():
    t = Transform.from_parts("a", "b", (1.0, 2.0, 3.0), (0.0, 0.0, S, S))
    assert np.allclose(t.apply_points([[1.0, 0.0, 0.0]]), [[1.0, 3.0, 3.0]])


def test_then_composes_in_application_order():
    shift = Transform.from_parts("a", "b", (1.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0))
    turn = Transform.from_parts("b", "c", (0.0, 0.0, 0.0), (0.0, 0.0, S, S))
    # shift first: (0,0,0) -> (1,0,0); then turn: -> (0,1,0)
    assert np.allclose(shift.then(turn).apply_points([[0.0, 0.0, 0.0]]), [[0.0, 1.0, 0.0]])
    assert (shift.then(turn).src, shift.then(turn).dst) == ("a", "c")


def test_then_refuses_frames_that_do_not_meet():
    a_to_b = Transform.identity("a")
    c_to_d = Transform.from_parts("c", "d", (0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0))
    with pytest.raises(FrameOrderError, match="do not meet"):
        a_to_b.then(c_to_d)


def test_a_transform_followed_by_its_inverse_is_identity():
    t = Transform.from_parts("a", "b", (1.0, 2.0, 3.0), CAMERA_Q)
    round_trip = t.then(t.inverse())
    assert (round_trip.src, round_trip.dst) == ("a", "a")
    assert np.allclose(round_trip.matrix, np.eye(4))


def test_a_transform_is_read_only():
    t = Transform.identity("a")
    with pytest.raises(ValueError):
        t.matrix[0, 3] = 5.0


@pytest.mark.parametrize(
    "matrix",
    [np.eye(3), np.full((4, 4), np.nan), np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [1, 0, 0, 1]])],
)
def test_a_transform_refuses_a_matrix_that_is_not_rigid_shaped(matrix):
    with pytest.raises(ValueError):
        Transform("a", "b", matrix)


def test_apply_points_needs_rows_of_three():
    with pytest.raises(ValueError, match="N x 3"):
        Transform.identity("a").apply_points([1.0, 2.0, 3.0])


# --- lookup ------------------------------------------------------------------

@pytest.mark.parametrize(
    "point, expected",
    [((0.0, 0.0, 1.0), (1.40, 0.0, 0.35)), ((1.0, 0.0, 0.0), (0.40, -1.0, 0.35))],
)
def test_camera_points_land_in_base_link_where_the_hand_says(point, expected):
    t = lookup(EXT, "camera_front", "base_link")
    assert np.allclose(t.apply_points([point]), [expected])


def test_a_lidar_point_lands_in_the_camera_frame_where_the_hand_says():
    """Up one edge and down an inverted, rotated one.
    (1,2,3) in rslidar -> (1.25, 2, 3.25) in base_link -> minus the camera's
    origin (0.85, 2, 2.9) -> optical axes x=-y, y=-z, z=x -> (-2, -2.9, 0.85)."""
    t = lookup(EXT, "rslidar", "camera_front")
    assert np.allclose(t.apply_points([[1.0, 2.0, 3.0]]), [[-2.0, -2.9, 0.85]])


def test_lookup_in_reverse_is_the_inverse():
    forward = lookup(EXT, "rslidar", "camera_front")
    backward = lookup(EXT, "camera_front", "rslidar")
    assert np.allclose(forward.matrix, backward.inverse().matrix)


def test_lookup_passes_route_errors_through():
    with pytest.raises(DynamicEdgeError):
        lookup(EXT, "rslidar", "odom")


# --- poses -------------------------------------------------------------------

def test_a_pose_maps_its_child_into_its_frame():
    values = [1.0, 2.0, 0.0, 0.0, 0.0, S, S]
    t = pose_transform(values, pose_header("odom"), "base_footprint", FRAMES)
    assert (t.src, t.dst) == ("base_footprint", "odom")
    assert np.allclose(t.apply_points([[1.0, 0.0, 0.0]]), [[1.0, 3.0, 0.0]])


def test_odometry_composes_with_the_static_tree():
    """rslidar -> base_footprint is static; base_footprint -> odom is the pose.
    (0,0,0) in rslidar -> (0.25, 0, 0.35) in base_footprint -> yaw 90 and
    shift (1, 2, 0) -> (1, 2.25, 0.35) in odom."""
    pose = pose_transform([1.0, 2.0, 0.0, 0.0, 0.0, S, S], pose_header("odom"),
                          "base_footprint", FRAMES)
    t = lookup(EXT, "rslidar", "base_footprint").then(pose)
    assert np.allclose(t.apply_points([[0.0, 0.0, 0.0]]), [[1.0, 2.25, 0.35]])


@pytest.mark.parametrize(
    "values, header, child, match",
    [
        ([0, 0, 0, 0, 0, 0, 1], pose_header("base_link"), "rslidar", "fixed or dynamic"),
        ([0, 0, 0, 0, 0, 0, 1], pose_header("odom"), "none", "never part of a transform"),
        ([0, 0, 0, 0, 0, 0], pose_header("odom"), "base_link", "seven"),
        ([0, 0, 0, 0, 0, 0, 0.5], pose_header("odom"), "base_link", "unit quaternion"),
        ([0, 0, float("inf"), 0, 0, 0, 1], pose_header("odom"), "base_link", "seven finite"),
        ([0, 0, 0, 0, 0, 0, 1], pose_header("world"), "base_link", "use 'map'"),
        ([0, 0, 0, 0, 0, 0, 1],
         pose_header("odom", schema="openrobot.state.vector/1.0.0"), "base_link",
         "openrobot.state.pose"),
    ],
)
def test_a_bad_pose_is_refused(values, header, child, match):
    with pytest.raises(FrameError, match=match):
        pose_transform(values, header, child, FRAMES)


# --- upstream adapters -------------------------------------------------------

UPSTREAM_POSE_JSON = {
    # The shape of DORA_NAV a9257f5 json_serialization.cpp poseToJson: named
    # keys, written in the order w, x, y, z.
    "header": {"frame_id": "map", "timestamp": 1729000000.5, "seq": 3},
    "pose": {
        "position": {"x": 1.0, "y": 2.0, "z": 0.0},
        "orientation": {"w": 0.5, "x": -0.5, "y": 0.5, "z": -0.5},
    },
}


def test_a_named_quaternion_is_read_by_name_not_by_position():
    orientation = UPSTREAM_POSE_JSON["pose"]["orientation"]
    assert list(orientation) == ["w", "x", "y", "z"], "the fixture must keep upstream's order"
    assert xyzw_from_named(orientation) == CAMERA_Q
```

- [ ] **Step 2: Add the stamp test**

Append to `packages/open-robot-operator/tests/test_wire.py`:

```python
from open_robot_operator.wire import stamp_ns_from_seconds


def test_seconds_become_nanoseconds_by_rounding_not_truncation():
    """1.001 s is stored as 1.00099999999..., which int() turns into
    1000999999 ns -- a nanosecond early, and a different stamp."""
    assert int(1.001 * 1e9) == 1_000_999_999  # the trap this guards against
    assert stamp_ns_from_seconds(1.001) == 1_001_000_000


def test_an_upstream_epoch_stamp_converts():
    assert stamp_ns_from_seconds(1729000000.5) == 1_729_000_000_500_000_000


@pytest.mark.parametrize("bad", [0, -1.0, float("nan"), float("inf"), True, "1.0"])
def test_a_stamp_that_is_not_a_positive_finite_number_is_refused(bad):
    with pytest.raises(ValueError):
        stamp_ns_from_seconds(bad)
```

If `tests/test_wire.py` does not already `import pytest` at the top, add it.

- [ ] **Step 3: Run them to see them fail**

Run: `cd packages/open-robot-operator && PYTHONPATH= python -m pytest tests/test_transform.py tests/test_wire.py -q; cd -`
Expected: FAIL. You should see `ModuleNotFoundError: No module named 'open_robot_operator.transform'` and `ImportError: cannot import name 'stamp_ns_from_seconds'`.

- [ ] **Step 4: Write `transform.py`**

Create `packages/open-robot-operator/open_robot_operator/transform.py`:

```python
"""Rigid transforms between frames. The only module here that imports numpy.

numpy comes from the optional extra `open-robot-operator[transform]`, so the
contract core -- envelope, declarations, validator -- keeps its three
dependencies. Which edges a transform uses is decided in `frames`, without
numpy; this module only does the arithmetic.
"""

from dataclasses import dataclass
from typing import Mapping, Sequence, Tuple

import numpy as np

from open_robot_operator.envelope import Header
from open_robot_operator.frames import (
    QUATERNION_NORM_TOLERANCE,
    Edge,
    Extrinsics,
    FrameDict,
    FrameError,
    UnknownFrameError,
)
from open_robot_operator.schemaref import parse_ref

POSE_SCHEMA_ID = "openrobot.state.pose"
POSE_ITEMS = 7


class FrameOrderError(FrameError):
    """Two transforms were composed whose frames do not meet."""


def rotation_matrix(q: Sequence[float]) -> np.ndarray:
    """A 3x3 rotation from a unit quaternion in x, y, z, w order."""
    x, y, z, w = (float(c) for c in q)
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
    ])


@dataclass(frozen=True, eq=False)
class Transform:
    """Maps coordinates expressed in `src` to coordinates expressed in `dst`."""

    src: str
    dst: str
    matrix: np.ndarray

    def __post_init__(self) -> None:
        m = np.array(self.matrix, dtype=np.float64)
        if m.shape != (4, 4) or not np.all(np.isfinite(m)):
            raise ValueError(f"a transform is a finite 4x4 matrix, got shape {m.shape}")
        if not np.allclose(m[3], (0.0, 0.0, 0.0, 1.0)):
            raise ValueError("the last row of a rigid transform must be 0 0 0 1")
        m.setflags(write=False)
        object.__setattr__(self, "matrix", m)

    @classmethod
    def identity(cls, frame: str) -> "Transform":
        return cls(frame, frame, np.eye(4))

    @classmethod
    def from_parts(cls, src: str, dst: str, translation: Sequence[float],
                   rotation_xyzw: Sequence[float]) -> "Transform":
        m = np.eye(4)
        m[:3, :3] = rotation_matrix(rotation_xyzw)
        m[:3, 3] = np.asarray(translation, dtype=np.float64)
        return cls(src, dst, m)

    def then(self, other: "Transform") -> "Transform":
        """Apply `self`, then `other`."""
        if self.dst != other.src:
            raise FrameOrderError(
                f"cannot apply {other.src!r} -> {other.dst!r} after "
                f"{self.src!r} -> {self.dst!r}; the frames do not meet")
        return Transform(self.src, other.dst, other.matrix @ self.matrix)

    def inverse(self) -> "Transform":
        r = self.matrix[:3, :3]
        t = self.matrix[:3, 3]
        m = np.eye(4)
        m[:3, :3] = r.T
        m[:3, 3] = -r.T @ t
        return Transform(self.dst, self.src, m)

    def apply_points(self, points) -> np.ndarray:
        p = np.asarray(points, dtype=np.float64)
        if p.ndim != 2 or p.shape[1] != 3:
            raise ValueError(f"points must be N x 3, got shape {p.shape}")
        return p @ self.matrix[:3, :3].T + self.matrix[:3, 3]


def edge_transform(edge: Edge) -> Transform:
    """child -> parent: an edge stores the child's pose in its parent."""
    return Transform.from_parts(edge.child, edge.parent, edge.translation_m, edge.rotation_xyzw)


def lookup(extrinsics: Extrinsics, src: str, dst: str) -> Transform:
    """The static transform from `src` to `dst`. Raises what `route` raises."""
    route = extrinsics.route(src, dst)
    result = Transform.identity(src)
    for edge in route.up:
        result = result.then(edge_transform(edge))
    for edge in route.down:
        result = result.then(edge_transform(edge).inverse())
    return result


def pose_transform(values, header: Header, child_frame: str, frames: FrameDict) -> Transform:
    """`child_frame -> header.frame_id`, from one openrobot.state.pose message."""
    schema_id, _ = parse_ref(header.schema)
    if schema_id != POSE_SCHEMA_ID:
        raise FrameError(f"a pose message carries {POSE_SCHEMA_ID}, not {schema_id}")
    parent = frames.require(header.frame_id)
    if parent.kind not in ("fixed", "dynamic"):
        raise FrameError(
            f"a pose is expressed in a fixed or dynamic frame, not the "
            f"{parent.kind} frame {parent.name!r}")
    if frames.require(child_frame).kind == "none":
        raise UnknownFrameError(
            "frame 'none' marks a payload with no spatial meaning and is never "
            "part of a transform")
    v = np.asarray(values, dtype=np.float64).reshape(-1)
    if v.size != POSE_ITEMS or not np.all(np.isfinite(v)):
        raise FrameError(
            f"a pose payload is seven finite values px py pz qx qy qz qw, got {v.tolist()}")
    norm = float(np.linalg.norm(v[3:]))
    if abs(norm - 1.0) > QUATERNION_NORM_TOLERANCE:
        raise FrameError(f"the pose orientation has norm {norm!r}; it must be a unit quaternion")
    return Transform.from_parts(child_frame, header.frame_id, v[:3], v[3:])


def xyzw_from_named(orientation: Mapping[str, float]) -> Tuple[float, float, float, float]:
    """Our positional order, from a quaternion with named components.

    Reading by name is the whole point. Upstream dora-nav's poseToJson writes
    w, x, y, z, and Eigen's constructor takes that order while its coeffs()
    returns x, y, z, w -- so position is the one thing never to trust.
    """
    return tuple(float(orientation[key]) for key in ("x", "y", "z", "w"))
```

- [ ] **Step 5: Add `stamp_ns_from_seconds` to `wire.py`**

Change the existing `import time` line in `packages/open-robot-operator/open_robot_operator/wire.py` to:

```python
import math
import time
```

Then append after `is_stale`:

```python
def stamp_ns_from_seconds(seconds: float) -> int:
    """A double-seconds stamp, such as upstream dora-nav's header.timestamp,
    as integer nanoseconds.

    Rounded, not truncated. 1.001 s is stored as 1.00099999999..., and int()
    would make that 1000999999 ns.
    """
    if isinstance(seconds, bool) or not isinstance(seconds, (int, float)):
        raise ValueError(f"a stamp in seconds must be a number, got {seconds!r}")
    if not math.isfinite(seconds) or seconds <= 0:
        raise ValueError(f"a stamp in seconds must be positive and finite, got {seconds!r}")
    return int(round(seconds * 1_000_000_000))
```

- [ ] **Step 6: Run the tests to see them pass**

Run: `cd packages/open-robot-operator && PYTHONPATH= python -m pytest tests/test_transform.py tests/test_wire.py -q; cd -`
Expected: PASS.

- [ ] **Step 7: Export the frames API, bump the version, add the extra**

In `packages/open-robot-operator/open_robot_operator/__init__.py`, add these names to `__all__`, keeping it alphabetical:

```python
    "DynamicEdgeError",
    "Extrinsics",
    "FrameDict",
    "FrameError",
    "MissingExtrinsicError",
    "UnknownFrameError",
    "load_extrinsics",
    "load_frames",
    "stamp_ns_from_seconds",
```

Then add this import block after the `envelope` import:

```python
from open_robot_operator.frames import (
    DynamicEdgeError,
    Extrinsics,
    FrameDict,
    FrameError,
    MissingExtrinsicError,
    UnknownFrameError,
    load_extrinsics,
    load_frames,
)
```

Finally, add `stamp_ns_from_seconds,` to the existing `from open_robot_operator.wire import (...)` block.

`transform` is deliberately **not** imported here. Importing the package must not need numpy.

In `packages/open-robot-operator/pyproject.toml`, change `version = "0.1.0"` to `version = "0.2.0"`, and replace the `[project.optional-dependencies]` table with:

```toml
[project.optional-dependencies]
transform = ["numpy>=1.24"]
dev = ["pytest>=7.0", "pytest-cov>=4.0", "numpy>=1.24"]
```

- [ ] **Step 8: Prove the core still imports without numpy**

Append to `packages/open-robot-operator/tests/test_frames.py`:

```python
def test_the_package_and_the_validator_import_without_numpy():
    """numpy is an optional extra: only open_robot_operator.transform needs it."""
    import subprocess
    import sys

    code = (
        "import sys; sys.modules['numpy'] = None\n"
        "import open_robot_operator, open_robot_operator.frames, open_robot_operator.validate\n"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                            cwd=Path(__file__).resolve().parents[1])
    assert result.returncode == 0, result.stderr
```

Run: `cd packages/open-robot-operator && PYTHONPATH= python -m pytest -q; cd -`
Expected: PASS, the whole contract suite.

- [ ] **Step 9: Commit**

```bash
git add packages/open-robot-operator
git commit -m "feat(operator): rigid transforms, pose composition and a rounding stamp helper"
```

---

## Task 6: The schemas and the simulator's calibration

**Files:**
- Create: `specs/operators/schemas/openrobot.state.pose-1.0.0.json`
- Create: `specs/operators/extrinsics.schema.json`
- Create: `robots/simulated-mobile-robot/extrinsics.yaml`
- Test: `tests/test_specs.py`

- [ ] **Step 1: Write the failing tests**

In `tests/test_specs.py`, insert `"openrobot.state.pose-1.0.0.json",` into the list in `test_the_expected_schemas_are_present`, directly before `"openrobot.state.vector-1.0.0.json",`. Then append:

```python
ROBOTS = Path(__file__).resolve().parents[1] / "robots"
EXTRINSICS_SCHEMA = json.loads((SPECS / "extrinsics.schema.json").read_text(encoding="utf-8"))
EXTRINSICS_FILES = sorted(ROBOTS.glob("*/extrinsics.yaml"))


def test_the_pose_schema_is_seven_float64_values_in_xyzw_order():
    doc = json.loads((SCHEMA_DIR / "openrobot.state.pose-1.0.0.json").read_text(encoding="utf-8"))
    assert doc["payload"]["encoding"] == "arrow.float64.flat"
    assert [f["name"] for f in doc["payload"]["fields"]] == ["px", "py", "pz", "qx", "qy", "qz", "qw"]
    assert "child_frame" in doc["description"], "the metadata key must be documented"


def test_the_simulated_robot_has_a_calibration():
    assert ROBOTS / "simulated-mobile-robot" / "extrinsics.yaml" in EXTRINSICS_FILES


@pytest.mark.parametrize("path", EXTRINSICS_FILES, ids=lambda p: p.parent.name)
def test_every_calibration_satisfies_its_json_schema(path):
    jsonschema.validate(yaml.safe_load(path.read_text(encoding="utf-8")), EXTRINSICS_SCHEMA)


@pytest.mark.parametrize("path", EXTRINSICS_FILES, ids=lambda p: p.parent.name)
def test_every_calibration_names_its_own_robot(path):
    assert yaml.safe_load(path.read_text(encoding="utf-8"))["robot"] == path.parent.name


@pytest.mark.parametrize("path", EXTRINSICS_FILES, ids=lambda p: p.parent.name)
def test_every_calibration_passes_the_library_checks(path):
    """The JSON Schema is for C++ readers; the library's checks are stricter
    (kinds, parents, unit norm) and are what a robot actually launches with."""
    from open_robot_operator.frames import load_extrinsics, load_frames

    load_extrinsics(path, load_frames(SPECS / "frames.yaml"))


def test_the_extrinsics_schema_refuses_an_rpy_rotation():
    """One rotation form only: rpy would bring back the axis-order question."""
    doc = {
        "contract_version": "1.0.0", "robot": "x", "calibrated": "2026-10-20", "source": "s",
        "transforms": [{"parent": "base_link", "child": "rslidar",
                        "translation_m": [0, 0, 0], "rpy": [0, 0, 0]}],
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(doc, EXTRINSICS_SCHEMA)
```

`test_every_calibration_passes_the_library_checks` imports `open_robot_operator`, so give the repo-level tests that import root. Create `tests/conftest.py`, or extend it if it already exists, with:

```python
import sys
from pathlib import Path

_CONTRACT = Path(__file__).resolve().parents[1] / "packages" / "open-robot-operator"
if str(_CONTRACT) not in sys.path:
    sys.path.insert(0, str(_CONTRACT))
```

- [ ] **Step 2: Run them to see them fail**

Run: `PYTHONPATH= python -m pytest tests/test_specs.py -q`
Expected: FAIL with `FileNotFoundError` for `extrinsics.schema.json` at collection.

- [ ] **Step 3: Create the pose payload schema**

Create `specs/operators/schemas/openrobot.state.pose-1.0.0.json`:

```json
{
  "id": "openrobot.state.pose",
  "version": "1.0.0",
  "title": "Pose of one frame in another",
  "description": "The pose of the frame named by the metadata key child_frame, expressed in the header's frame_id, as a flat float64 arrow array of seven values. It is the only source of a dynamic transform: no buffer is kept and nothing is interpolated, so a consumer composes with the latest pose it received. The header's frame_id must be a fixed or dynamic frame.",
  "payload": {
    "encoding": "arrow.float64.flat",
    "item_step": 7,
    "fields": [
      {"name": "px", "unit": "m", "description": "Position of the child frame's origin along the parent frame's x axis."},
      {"name": "py", "unit": "m", "description": "Position of the child frame's origin along the parent frame's y axis."},
      {"name": "pz", "unit": "m", "description": "Position of the child frame's origin along the parent frame's z axis."},
      {"name": "qx", "unit": "dimensionless", "description": "Orientation quaternion, x component. The order is x, y, z, w and the four have unit norm."},
      {"name": "qy", "unit": "dimensionless", "description": "Orientation quaternion, y component. The order is x, y, z, w and the four have unit norm."},
      {"name": "qz", "unit": "dimensionless", "description": "Orientation quaternion, z component. The order is x, y, z, w and the four have unit norm."},
      {"name": "qw", "unit": "dimensionless", "description": "Orientation quaternion, w (scalar) component, last rather than first."}
    ]
  }
}
```

- [ ] **Step 4: Create the extrinsics schema**

Create `specs/operators/extrinsics.schema.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "openrobot.geometry.extrinsics/1.0.0",
  "title": "Per-robot extrinsic calibration",
  "description": "robots/<name>/extrinsics.yaml. Each transform is the pose of child expressed in parent, for a mounted frame only. This schema fixes the shape for readers in any language; open_robot_operator.frames adds the checks a schema cannot express: known frames, matching parents, mounted kinds, one entry per child, and unit-norm quaternions that are not silently normalised.",
  "type": "object",
  "additionalProperties": false,
  "required": ["contract_version", "robot", "calibrated", "source", "transforms"],
  "properties": {
    "contract_version": {"type": "string", "pattern": "^\\d+\\.\\d+\\.\\d+$"},
    "robot": {"type": "string", "minLength": 1},
    "calibrated": {"type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$"},
    "source": {"type": "string", "minLength": 1},
    "transforms": {
      "type": "array",
      "minItems": 1,
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["parent", "child", "translation_m", "rotation_xyzw"],
        "properties": {
          "parent": {"type": "string", "minLength": 1},
          "child": {"type": "string", "minLength": 1},
          "translation_m": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3},
          "rotation_xyzw": {"type": "array", "items": {"type": "number"}, "minItems": 4, "maxItems": 4}
        }
      }
    }
  }
}
```

- [ ] **Step 5: Create the simulator's calibration**

Create `robots/simulated-mobile-robot/extrinsics.yaml`:

```yaml
# Extrinsic calibration of the simulated mobile robot. Each entry is the pose
# of `child` in `parent`, for mounted frames only (frames.yaml `kind`).
#
# Values copied from the MuJoCo model, not measured:
#   base_link   mickrobot.xml:29             pos="0 0 0.1" under base_footprint
#   rslidar     mickrobot.xml:63             lidar_link pos="0.25 0 0.25", identity
#   camera      mujoco_extensions.xml:10-12  camera_link pos="0.40 0 0.35", and
#               xyaxes="0 -1 0 0 0 1". MuJoCo cameras look along -z; frames.yaml's
#               optical frame looks along +z with y down, so the optical axes in
#               base_link are x=(0,-1,0), y=(0,0,-1), z=(1,0,0), which is the
#               quaternion (-0.5, 0.5, -0.5, 0.5) in x, y, z, w.
#   imu_link    mujoco_extensions.xml:14     pos="0 0 0.25", identity
#
# Every edge is written out, including the identity rotations: a missing edge
# is an error, never an assumed zero.
contract_version: 1.0.0
robot: simulated-mobile-robot
calibrated: "2026-10-20"
source: >-
  DORA_NAV a9257f5 modules/simulation/mujoco_mickrobot/models/mickrobot.xml
  and mujoco_extensions.xml (model values, not a physical calibration)
transforms:
  - parent: base_footprint
    child: base_link
    translation_m: [0.0, 0.0, 0.1]
    rotation_xyzw: [0.0, 0.0, 0.0, 1.0]
  - parent: base_link
    child: rslidar
    translation_m: [0.25, 0.0, 0.25]
    rotation_xyzw: [0.0, 0.0, 0.0, 1.0]
  - parent: base_link
    child: camera_front
    translation_m: [0.40, 0.0, 0.35]
    rotation_xyzw: [-0.5, 0.5, -0.5, 0.5]
  - parent: base_link
    child: imu_link
    translation_m: [0.0, 0.0, 0.25]
    rotation_xyzw: [0.0, 0.0, 0.0, 1.0]
```

- [ ] **Step 6: Run the tests to see them pass**

Run: `PYTHONPATH= python -m pytest tests/test_specs.py -q`
Expected: PASS. The meta-schema, unit, filename and description tests now also cover the pose schema.

- [ ] **Step 7: Commit**

```bash
git add specs/operators robots/simulated-mobile-robot/extrinsics.yaml tests/test_specs.py tests/conftest.py
git commit -m "feat(specs): pose payload, extrinsics schema, and the simulator's calibration"
```

---

## Task 7: The `env:` output frame form

**Files:**
- Modify: `packages/open-robot-operator/open_robot_operator/declare.py`
- Modify: `packages/open-robot-operator/open_robot_operator/resolve.py`
- Modify: `packages/open-robot-operator/open_robot_operator/wire.py`
- Modify: `packages/open-robot-operator/open_robot_operator/validate.py` (`Dataflow` and parsing only)
- Test: `tests/test_declare.py`, `tests/test_resolve.py`, `tests/test_wire.py`, `tests/test_validate.py`

- [ ] **Step 1: Write the failing tests**

Append to `packages/open-robot-operator/tests/test_declare.py`:

```python
ENV_DECL = """
contract_version: 1.0.0
operators:
  - name: xform
    module: m.xform
    inputs:
      cloud:
        schema: openrobot.sensor.point_cloud/^1.0
        frame: {in_frame}
    outputs:
      cloud:
        schema: openrobot.sensor.point_cloud/1.0.0
        frame: {out_frame}
"""


def test_an_output_frame_may_be_read_from_the_node_env():
    decls = parse_operators(ENV_DECL.format(in_frame="any", out_frame="env:TARGET_FRAME"))
    port = decls["xform"].outputs["cloud"]
    assert port.env_var == "TARGET_FRAME"
    assert port.same_as is None


def test_a_literal_frame_has_no_env_var():
    decls = parse_operators(ENV_DECL.format(in_frame="any", out_frame="base_link"))
    assert decls["xform"].outputs["cloud"].env_var is None


def test_env_is_output_only():
    with pytest.raises(ValueError, match="only meaningful on an output"):
        parse_operators(ENV_DECL.format(in_frame="env:TARGET_FRAME", out_frame="base_link"))


@pytest.mark.parametrize("bad", ["env:", "env:target_frame", "env:1FRAME", "env:TARGET-FRAME"])
def test_env_names_an_upper_case_variable(bad):
    with pytest.raises(ValueError, match="upper-case environment variable"):
        parse_operators(ENV_DECL.format(in_frame="any", out_frame=bad))
```

Append to `packages/open-robot-operator/tests/test_resolve.py`:

```python
ENV_DECLS = parse_operators(
    textwrap.dedent(
        f"""
        contract_version: 1.0.0
        operators:
          - name: driver
            module: m.driver
            inputs: {{}}
            outputs:
              cloud:
                schema: {PC_OUT}
                frame: rslidar
          - name: xform
            module: m.xform
            inputs:
              cloud:
                schema: {PC_IN}
                frame: any
            outputs:
              cloud:
                schema: {PC_OUT}
                frame: env:TARGET_FRAME
          - name: passthrough
            module: m.passthrough
            inputs:
              cloud:
                schema: {PC_IN}
                frame: any
            outputs:
              cloud:
                schema: {PC_OUT}
                frame: same_as:cloud
        """
    )
)
ENV_NODES = {"driver": "driver", "xf": "xform", "pass": "passthrough"}
ENV_EDGES = {("xf", "cloud"): ("driver", "cloud"), ("pass", "cloud"): ("xf", "cloud")}


def test_an_env_frame_resolves_from_the_node_env():
    graph = Graph(nodes=ENV_NODES, edges=ENV_EDGES, decls=ENV_DECLS,
                  env={"xf": {"TARGET_FRAME": "camera_front"}})
    assert resolve_frame(graph, "xf", "cloud") == "camera_front"
    assert resolve_frame(graph, "pass", "cloud") == "camera_front"


def test_an_env_frame_with_the_variable_unset_cannot_resolve():
    graph = Graph(nodes=ENV_NODES, edges=ENV_EDGES, decls=ENV_DECLS)
    with pytest.raises(ValueError, match="sets no TARGET_FRAME"):
        resolve_frame(graph, "xf", "cloud")
```

Append to `packages/open-robot-operator/tests/test_wire.py`:

```python
def test_an_unresolved_env_frame_is_never_published_literally():
    with pytest.raises(ValueError, match="resolve env:TARGET_FRAME"):
        output_frame("env:TARGET_FRAME", {})
```

If `output_frame` is not already imported in `test_wire.py`, add `from open_robot_operator.wire import output_frame`.

Append to `packages/open-robot-operator/tests/test_validate.py`:

```python
def test_parse_dataflow_keeps_each_nodes_env_as_strings():
    flow = parse_dataflow(
        "nodes:\n"
        "  - id: xf\n"
        "    env: {OPERATOR: xform, TARGET_FRAME: camera_front, DIAG_EVERY: 20}\n"
    )
    assert flow.env["xf"] == {"OPERATOR": "xform", "TARGET_FRAME": "camera_front", "DIAG_EVERY": "20"}
    assert flow.base_dir is None


def test_load_dataflow_records_the_directory_relative_env_paths_resolve_against(tmp_path):
    path = tmp_path / "flow.yml"
    path.write_text("nodes:\n  - id: a\n", encoding="utf-8")
    assert load_dataflow(path).base_dir == tmp_path.resolve()
```

- [ ] **Step 2: Run them to see them fail**

Run: `cd packages/open-robot-operator && PYTHONPATH= python -m pytest -q; cd -`
Expected: FAIL. You should see `AttributeError: 'PortDecl' object has no attribute 'env_var'`, `TypeError: ... unexpected keyword argument 'env'`, and `AttributeError: 'Dataflow' object has no attribute 'env'`.

- [ ] **Step 3: `declare.py`**

In `packages/open-robot-operator/open_robot_operator/declare.py`:

1. Change `from dataclasses import dataclass` to:

   ```python
   import re
   from dataclasses import dataclass
   ```

2. After `_SAME_AS = "same_as:"`, add:

   ```python
   _ENV = "env:"
   _ENV_VAR = re.compile(r"[A-Z][A-Z0-9_]*")
   ```

3. Add this property to `PortDecl`, after `same_as`:

   ```python
       @property
       def env_var(self) -> Optional[str]:
           """The node env variable an output's frame is read from, if any."""
           if self.frame is None or not self.frame.startswith(_ENV):
               return None
           return self.frame[len(_ENV):]
   ```

4. In `_port`, replace the `frame must be 'any', a literal name, or 'same_as:<input port>'` message so that it reads:

   ```python
           raise ValueError(
               f"{where} port {name!r}: frame must be 'any', a literal name, "
               f"'same_as:<input port>' or 'env:<VAR>', got {frame!r}")
   ```

5. Directly after the existing `if not is_output and frame.startswith(_SAME_AS):` block, add:

   ```python
       if frame.startswith(_ENV):
           if not is_output:
               raise ValueError(
                   f"{where} input port {name!r} declares {frame!r}; env names "
                   "where an output's frame comes from and is therefore only "
                   "meaningful on an output")
           if not _ENV_VAR.fullmatch(frame[len(_ENV):]):
               raise ValueError(
                   f"{where} port {name!r}: {frame!r} must name an upper-case "
                   "environment variable, such as env:TARGET_FRAME")
   ```

- [ ] **Step 4: `resolve.py`**

Replace `packages/open-robot-operator/open_robot_operator/resolve.py` with:

```python
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from open_robot_operator.declare import OperatorDecl

Endpoint = Tuple[str, str]


@dataclass(frozen=True)
class Graph:
    nodes: Dict[str, str]
    edges: Dict[Endpoint, Endpoint]
    decls: Dict[str, OperatorDecl]
    env: Dict[str, Dict[str, str]] = field(default_factory=dict)

    def decl_for(self, node: str) -> OperatorDecl:
        if node not in self.nodes:
            raise ValueError(f"node {node!r} is not in the dataflow")
        operator = self.nodes[node]
        if operator not in self.decls:
            raise ValueError(
                f"node {node!r} is bound to operator {operator!r}, which no "
                "operators.yaml declares")
        return self.decls[operator]


def resolve_frame(graph: Graph, node: str, port: str,
                  _seen: Optional[List[Endpoint]] = None) -> str:
    seen = list(_seen or [])
    here: Endpoint = (node, port)
    if here in seen:
        path = " -> ".join(f"{n}.{p}" for n, p in seen + [here])
        raise ValueError(f"frame resolution cycle: {path}")

    decl = graph.decl_for(node)
    if port not in decl.outputs:
        raise ValueError(f"operator {decl.name!r} declares no output port {port!r}")

    declared = decl.outputs[port]
    target = declared.same_as
    if target is None:
        var = declared.env_var
        if var is None:
            return declared.frame
        value = graph.env.get(node, {}).get(var)
        if not value:
            raise ValueError(
                f"{node}.{port} declares env:{var}, but node {node!r} sets no {var} "
                "in its env")
        return value

    upstream = graph.edges.get((node, target))
    if upstream is None:
        raise ValueError(
            f"{node}.{target} is unwired, so {node}.{port} cannot resolve same_as:{target}")
    return resolve_frame(graph, upstream[0], upstream[1], seen + [here])
```

- [ ] **Step 5: `wire.py`**

In `output_frame`, directly before `if declared == "any":`, add:

```python
    if declared.startswith("env:"):
        raise ValueError(
            f"the declaration says {declared!r}; resolve {declared} from the "
            "node's environment and pass the frame name itself")
```

- [ ] **Step 6: `validate.py` — the dataflow keeps env and its directory**

In `packages/open-robot-operator/open_robot_operator/validate.py`:

1. Change `from dataclasses import dataclass, field` to:

   ```python
   from dataclasses import dataclass, field, replace
   ```

2. Add two fields at the end of `Dataflow`:

   ```python
       env: Dict[str, Dict[str, str]] = field(default_factory=dict)
       base_dir: Optional[Path] = None
   ```

3. In `parse_dataflow`, next to `builtins: Dict[Endpoint, str] = {}`, add:

   ```python
       envs: Dict[str, Dict[str, str]] = {}
   ```

4. After `env = entry.get("env") or {}`, add:

   ```python
           envs[node] = {str(key): str(value) for key, value in env.items()}
   ```

5. Change the `return Dataflow(...)` to:

   ```python
       return Dataflow(nodes=nodes, edges=edges, declared_outputs=declared_outputs,
                       builtins=builtins, env=envs)
   ```

6. Replace `load_dataflow` with:

   ```python
   def load_dataflow(path: Union[str, Path]) -> Dataflow:
       """Parse a dataflow file. dora runs nodes with the file's directory as cwd,
       so relative paths in a node's env resolve against `base_dir`."""
       path = Path(path)
       return replace(parse_dataflow(path.read_text(encoding="utf-8")),
                      base_dir=path.resolve().parent)
   ```

7. In `validate_dataflow`, change the `graph = Graph(...)` line to:

   ```python
       graph = Graph(nodes=dataflow.nodes, edges=dataflow.edges, decls=decls, env=dataflow.env)
   ```

- [ ] **Step 7: Run every suite**

Run:
```bash
cd packages/open-robot-operator && PYTHONPATH= python -m pytest -q; cd -
PYTHONPATH= python -m pytest capabilities/data-processing/tests -q
```
Expected: both PASS. data-processing stays at `349 passed`.

- [ ] **Step 8: Commit**

```bash
git add packages/open-robot-operator
git commit -m "feat(operator): env:<VAR> output frames, resolved from the dataflow before launch"
```

---

## Task 8: Validator check 6, `transform`

**Files:**
- Modify: `packages/open-robot-operator/open_robot_operator/validate.py`
- Test: `packages/open-robot-operator/tests/test_validate.py`

- [ ] **Step 1: Write the failing tests**

Append to `packages/open-robot-operator/tests/test_validate.py`:

```python
# --- check 6: transform ------------------------------------------------------

import yaml

from open_robot_operator.frames import load_extrinsics, load_frames
from open_robot_operator.validate import main

from tests.test_frames import CAMERA_Q, FRAMES_YAML, edge, extrinsics_doc

XFORM_DECLS = parse_operators(f"""
contract_version: 1.0.0
operators:
  - name: driver
    module: m.driver
    inputs: {{}}
    outputs:
      cloud:
        schema: {PC}/1.0.0
        frame: rslidar
  - name: localizer
    module: m.localizer
    inputs: {{}}
    outputs:
      pose:
        schema: openrobot.state.pose/1.0.0
        frame: odom
  - name: xform
    module: m.xform
    inputs:
      cloud:
        schema: {PC}/^1.0
        frame: any
      pose:
        schema: openrobot.state.pose/^1.0
        frame: any
        required: false
    outputs:
      cloud:
        schema: {PC}/1.0.0
        frame: env:TARGET_FRAME
  - name: filt
    module: m.filt
    inputs:
      cloud:
        schema: {PC}/^1.0
        frame: any
    outputs:
      cloud:
        schema: {PC}/1.0.0
        frame: same_as:cloud
""")


@pytest.fixture
def calib(tmp_path):
    (tmp_path / "frames.yaml").write_text(FRAMES_YAML, encoding="utf-8")
    doc = extrinsics_doc(
        edge("base_footprint", "base_link", (0.0, 0.0, 0.1)),
        edge("base_link", "rslidar", (0.25, 0.0, 0.25)),
        edge("base_link", "camera_front", (0.40, 0.0, 0.35), CAMERA_Q),
    )
    (tmp_path / "extrinsics.yaml").write_text(yaml.safe_dump(doc), encoding="utf-8")
    frames = load_frames(tmp_path / "frames.yaml")
    return load_extrinsics(tmp_path / "extrinsics.yaml", frames)


def xform_flow(tmp_path, target="camera_front", *, calibration="extrinsics.yaml", pose=False):
    env = {"OPERATOR": "xform"}
    if target is not None:
        env["TARGET_FRAME"] = target
    if calibration is not None:
        env["ORS_EXTRINSICS"] = calibration
    inputs = {"cloud": "driver/cloud"}
    nodes = [{"id": "driver", "outputs": ["cloud"]}]
    if pose:
        inputs["pose"] = "localizer/pose"
        nodes.append({"id": "localizer", "outputs": ["pose"]})
    nodes.append({"id": "xf", "env": env, "inputs": inputs, "outputs": ["cloud"]})
    path = tmp_path / "flow.yml"
    path.write_text(yaml.safe_dump({"nodes": nodes}), encoding="utf-8")
    return path


def transform_violations(path, extrinsics):
    found = validate_dataflow(load_dataflow(path), XFORM_DECLS, extrinsics)
    return [v for v in found if v.check in ("transform", "frame")]


def test_a_calibrated_frame_change_passes(tmp_path, calib):
    assert transform_violations(xform_flow(tmp_path), calib) == []


def test_a_frame_change_without_a_calibration_is_blocking(tmp_path):
    found = transform_violations(xform_flow(tmp_path), None)
    assert found and all(v.blocking and v.check == "transform" for v in found)
    assert any("no --extrinsics" in v.message for v in found)


def test_a_node_that_launches_with_another_calibration_is_blocking(tmp_path, calib):
    other = tmp_path / "other.yaml"
    other.write_text((tmp_path / "extrinsics.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    found = transform_violations(xform_flow(tmp_path, calibration="other.yaml"), calib)
    assert [v.port for v in found] == ["ORS_EXTRINSICS"]
    assert "validated against" in found[0].message


def test_a_node_that_changes_frames_must_name_its_calibration(tmp_path, calib):
    found = transform_violations(xform_flow(tmp_path, calibration=None), calib)
    assert [v.port for v in found] == ["ORS_EXTRINSICS"]
    assert "sets no ORS_EXTRINSICS" in found[0].message


def test_a_missing_extrinsic_is_blocking(tmp_path, calib):
    found = transform_violations(xform_flow(tmp_path, target="imu_link"), calib)
    assert len(found) == 1 and "never assumed to be identity" in found[0].message


def test_a_rejected_target_name_is_blocking_with_its_replacement(tmp_path, calib):
    found = transform_violations(xform_flow(tmp_path, target="lidar_link"), calib)
    assert len(found) == 1 and "use 'rslidar'" in found[0].message


def test_a_dynamic_target_needs_a_wired_pose(tmp_path, calib):
    found = transform_violations(xform_flow(tmp_path, target="odom"), calib)
    assert len(found) == 1 and "no wired openrobot.state.pose input" in found[0].message


def test_a_dynamic_target_with_a_wired_pose_passes(tmp_path, calib):
    assert transform_violations(xform_flow(tmp_path, target="odom", pose=True), calib) == []


def test_an_env_frame_with_its_variable_unset_is_blocking(tmp_path, calib):
    found = transform_violations(xform_flow(tmp_path, target=None), calib)
    assert [(v.check, v.port) for v in found] == [("frame", "cloud")]
    assert "sets no TARGET_FRAME" in found[0].message


def test_same_as_operators_never_trigger_the_transform_check(tmp_path):
    """The shipped data-processing dataflows are all same_as; with no
    calibration at all they must still produce no transform violation."""
    path = tmp_path / "flow.yml"
    path.write_text(yaml.safe_dump({"nodes": [
        {"id": "driver", "outputs": ["cloud"]},
        {"id": "f", "env": {"OPERATOR": "filt"}, "inputs": {"cloud": "driver/cloud"},
         "outputs": ["cloud"]},
    ]}), encoding="utf-8")
    assert transform_violations(path, None) == []


def test_the_cli_checks_a_calibration(tmp_path, calib, capsys):
    flow = xform_flow(tmp_path)
    pack = tmp_path / "pack"
    pack.mkdir()
    (pack / "operators.yaml").write_text(
        f"""
contract_version: 1.0.0
operators:
  - name: driver
    module: m.driver
    inputs: {{}}
    outputs:
      cloud: {{schema: {PC}/1.0.0, frame: rslidar}}
  - name: xform
    module: m.xform
    inputs:
      cloud: {{schema: {PC}/^1.0, frame: any}}
    outputs:
      cloud: {{schema: {PC}/1.0.0, frame: "env:TARGET_FRAME"}}
""", encoding="utf-8")
    common = [str(flow), "--pack", str(pack), "--frames", str(tmp_path / "frames.yaml")]
    assert main(common + ["--extrinsics", str(tmp_path / "extrinsics.yaml")]) == 0
    assert main(common) == 1
    assert "no --extrinsics" in capsys.readouterr().out
```

- [ ] **Step 2: Run them to see them fail**

Run: `cd packages/open-robot-operator && PYTHONPATH= python -m pytest tests/test_validate.py -q; cd -`
Expected: FAIL with `TypeError: validate_dataflow() takes 2 positional arguments but 3 were given`.

- [ ] **Step 3: Implement check 6**

In `packages/open-robot-operator/open_robot_operator/validate.py`:

1. Add this import after the `declare` import:

   ```python
   from open_robot_operator.frames import (
       DynamicEdgeError, Extrinsics, FrameError, load_extrinsics, load_frames,
   )
   ```

2. After `TIMER_UNITS = ("millis", "secs")`, add:

   ```python
   POSE_SCHEMA = "openrobot.state.pose"
   EXTRINSICS_ENV = "ORS_EXTRINSICS"
   SPATIALLESS = ("any", "none")
   ```

3. Change the signature and docstring of `validate_dataflow`:

   ```python
   def validate_dataflow(
       dataflow: Dataflow, decls: Dict[str, OperatorDecl],
       extrinsics: Optional[Extrinsics] = None,
   ) -> List[Violation]:
       """Run the six checks. Returns every violation found, blocking or not.

       `extrinsics` is the robot calibration the dataflow will launch with. It
       is needed only when some operator changes frames (check 6).
       """
   ```

4. Directly before the final `return found` of `validate_dataflow`, add:

   ```python
       # check 6: a frame change needs a calibration that supports it
       found.extend(_transform_violations(dataflow, graph, decls, extrinsics))
   ```

5. Add these functions after `validate_dataflow`:

   ```python
   def _resolved_or_none(graph: Graph, node: str, port: str) -> Optional[str]:
       try:
           return resolve_frame(graph, node, port)
       except ValueError:
           return None  # reported by the frame check, or by the env check below


   def _input_frames(graph: Graph, dataflow: Dataflow, node: str,
                     decl: OperatorDecl) -> List[str]:
       """The spatial frames this node's data inputs resolve to. A pose input is
       what a transform composes with, not data it moves, so it is skipped."""
       frames = []
       for port, want in sorted(decl.inputs.items()):
           if want.builtin is not None or want.schema_id == POSE_SCHEMA:
               continue
           upstream = dataflow.edges.get((node, port))
           if upstream is None:
               continue
           producer = _decl(graph, upstream[0])
           if producer is None or upstream[1] not in producer.outputs:
               continue
           frame = _resolved_or_none(graph, *upstream)
           if frame is not None and frame not in SPATIALLESS:
               frames.append(frame)
       return frames


   def _transform_violations(dataflow: Dataflow, graph: Graph,
                             decls: Dict[str, OperatorDecl],
                             extrinsics: Optional[Extrinsics]) -> List[Violation]:
       found: List[Violation] = []
       base_dir = dataflow.base_dir or Path.cwd()
       for node, operator in sorted(dataflow.nodes.items()):
           decl = decls.get(operator)
           if decl is None:
               continue
           inputs = _input_frames(graph, dataflow, node, decl)
           changes = []
           for port, give in sorted(decl.outputs.items()):
               if give.same_as is not None:
                   continue
               if give.env_var is not None:
                   try:
                       resolve_frame(graph, node, port)
                   except ValueError as error:
                       found.append(Violation("frame", True, node, port, str(error)))
                       continue
               out = _resolved_or_none(graph, node, port)
               if out is None or out in SPATIALLESS:
                   continue
               changes.extend((src, out, port) for src in inputs if src != out)

           for src, dst, port in changes:
               if extrinsics is None:
                   found.append(Violation(
                       "transform", True, node, port,
                       f"changes frame {src!r} -> {dst!r}, but no --extrinsics file "
                       "was given, so the transform cannot be checked before launch"))
                   continue
               try:
                   extrinsics.route(src, dst)
               except DynamicEdgeError as error:
                   poses = [p for p, w in decl.inputs.items() if w.schema_id == POSE_SCHEMA]
                   if not any((node, p) in dataflow.edges for p in poses):
                       found.append(Violation(
                           "transform", True, node, port,
                           f"{error}; operator {decl.name!r} has no wired "
                           f"{POSE_SCHEMA} input to compose with"))
               except FrameError as error:
                   found.append(Violation("transform", True, node, port, str(error)))

           named = dataflow.env.get(node, {}).get(EXTRINSICS_ENV)
           if named is not None:
               if extrinsics is None or extrinsics.path is None:
                   found.append(Violation(
                       "transform", True, node, EXTRINSICS_ENV,
                       f"names the calibration {named!r}, but the validator was "
                       "given none to check it against"))
               else:
                   launched = (base_dir / named).resolve()
                   checked = extrinsics.path.resolve()
                   if launched != checked:
                       found.append(Violation(
                           "transform", True, node, EXTRINSICS_ENV,
                           f"launches with {launched} but was validated against "
                           f"{checked}; a robot must run the calibration it was "
                           "checked with"))
           elif changes:
               found.append(Violation(
                   "transform", True, node, EXTRINSICS_ENV,
                   f"changes frames but sets no {EXTRINSICS_ENV}, so the node "
                   "cannot load a calibration"))
       return found
   ```

6. In `main`, after the `--pack` argument, add:

   ```python
       parser.add_argument(
           "--extrinsics", metavar="FILE",
           help="the robot calibration this dataflow launches with "
                "(robots/<name>/extrinsics.yaml); needed when an operator changes frames",
       )
       parser.add_argument(
           "--frames", metavar="FILE", default="specs/operators/frames.yaml",
           help="the frame dictionary (default: %(default)s, relative to the cwd)",
       )
   ```

7. In `main`, replace the line `violations = validate_dataflow(load_dataflow(args.dataflow), _collect_decls(packs))` with:

   ```python
       extrinsics = None
       if args.extrinsics:
           try:
               extrinsics = load_extrinsics(args.extrinsics, load_frames(args.frames))
           except (FrameError, OSError) as error:
               print(f"cannot load the calibration: {error}")
               return 2
       violations = validate_dataflow(
           load_dataflow(args.dataflow), _collect_decls(packs), extrinsics)
   ```

- [ ] **Step 4: Run every suite**

Run:
```bash
cd packages/open-robot-operator && PYTHONPATH= python -m pytest -q; cd -
PYTHONPATH= python -m pytest capabilities/data-processing/tests -q
```
Expected: both PASS. data-processing stays at `349 passed`; that suite's `test_every_dataflow_validates_with_no_violations_at_all` is the proof that check 6 leaves the shipped dataflows alone.

- [ ] **Step 5: Commit**

```bash
git add packages/open-robot-operator
git commit -m "feat(operator): check 6 refuses a frame change no calibration supports"
```

---

## Task 9: The perception pack and `frame_transform`'s pure functions

**Files:**
- Create: `capabilities/perception/pack.yaml`, `operators.yaml`, `pyproject.toml`, `conftest.py`
- Create: `capabilities/perception/open_robot_perception/__init__.py`, `transform/__init__.py`, `transform/frame_transform_op.py`, `mocks/__init__.py`
- Test: `capabilities/perception/tests/test_frame_transform.py`

- [ ] **Step 1: Create the manifests and import roots**

`capabilities/perception/conftest.py`:

```python
"""Make the pack, the data-processing pack and the contract package importable
from a bare checkout. Perception depends on data-processing (spec §5.1 of the
contract design), so all three roots go at the FRONT of sys.path, for the same
reason as in the data-processing pack: a global open_robot_sdk on the dev
machines resolves to an unrelated project."""

import sys
from pathlib import Path

_PACK = Path(__file__).resolve().parent
_DATAPROC = _PACK.parent / "data-processing"
_CONTRACT = _PACK.parents[1] / "packages" / "open-robot-operator"
for root in (_PACK, _DATAPROC, _CONTRACT):
    if root.is_dir() and str(root) not in sys.path:
        sys.path.insert(0, str(root))
```

`capabilities/perception/pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=68.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "open-robot-perception"
version = "0.1.0"
description = "Perception operators for Open Robot Stack on the operator contract; starts with checked frame transformation"
requires-python = ">=3.10"
license = { text = "Apache-2.0" }
dependencies = ["numpy>=1.24", "pyarrow>=14", "pyyaml>=6.0"]

[project.optional-dependencies]
dev = ["pytest>=7.0"]

[tool.setuptools.packages.find]
include = ["open_robot_perception*"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

`capabilities/perception/pack.yaml`:

```yaml
# Capability Pack (v1.3 §7.3). camelCase, because a distribution manifest is
# camelCase per §8.5; the runtime port descriptors live in operators.yaml.
#
# Contract item 13's pack. It starts with the one operator every later item
# needs: a checked frame change. Fusion, clustering and detection land here in
# sub-project 2.
apiVersion: openrobot.dev/v1alpha1
kind: CapabilityPack

metadata:
  name: perception
  version: 0.1.0

provides:
  capabilities:
    - id: robot.perception.frame-transform
      version: 1.0.0
      operations:
        configure:
          protocol: robot-control-v1
          verb: provider.perception.frame_transform.configure
          safetyTier: observe

requires:
  packages:
    - id: open-robot-operator
      version: ^0.2
    - id: open-robot-dataproc
      version: ^0.1
```

`capabilities/perception/operators.yaml`:

```yaml
# Port declarations for the perception operators. snake_case per v1.3 §8.5.
# Like data-processing's, this file is the operator registry contract item 15
# promises.
contract_version: 1.0.0

operators:
  - name: frame_transform
    module: open_robot_perception.transform.frame_transform_op
    inputs:
      cloud:
        schema: openrobot.sensor.point_cloud/^1.0
        frame: any
      # Wired only when the path to TARGET_FRAME crosses a dynamic edge; the
      # validator's check 6 says when. Must equal POSE_MAX_AGE_MS in the module.
      pose:
        schema: openrobot.state.pose/^1.0
        frame: any
        max_age_ms: 100
        required: false
    outputs:
      cloud:
        schema: openrobot.sensor.point_cloud/1.0.0
        frame: env:TARGET_FRAME
      diag:
        schema: openrobot.diag.counters/1.0.0
        frame: none
    diagnostics: diag
```

Also create these empty files:

- `capabilities/perception/open_robot_perception/__init__.py`
- `capabilities/perception/open_robot_perception/transform/__init__.py`
- `capabilities/perception/open_robot_perception/mocks/__init__.py`

- [ ] **Step 2: Write the failing tests**

Create `capabilities/perception/tests/test_frame_transform.py`:

```python
import itertools
import math
from pathlib import Path

import numpy as np
import pytest

from open_robot_operator.declare import load_operators
from open_robot_operator.envelope import Header
from open_robot_operator.frames import load_extrinsics, load_frames
from open_robot_operator.node import ConfigError
from open_robot_perception.transform import frame_transform_op as op

PACK = Path(__file__).resolve().parents[1]
ROOT = PACK.parents[1]
FRAMES = load_frames(ROOT / "specs" / "operators" / "frames.yaml")
SIM = load_extrinsics(ROOT / "robots" / "simulated-mobile-robot" / "extrinsics.yaml", FRAMES)
S = math.sin(math.pi / 4)
T0 = 1_700_000_000_000_000_000


def cloud_header(stamp_ns=T0, validity="ok", reason=None, frame_id="rslidar"):
    return Header(schema="openrobot.sensor.point_cloud/1.0.0", frame_id=frame_id, seq=7,
                  stamp_ns=stamp_ns, source="mock.lidar", validity=validity, reason=reason)


def a_pose(stamp_ns=T0, validity="ok", reason=None):
    """base_footprint in odom: a quarter yaw and a shift of (1, 2, 0)."""
    header = Header(schema="openrobot.state.pose/1.0.0", frame_id="odom", seq=0,
                    stamp_ns=stamp_ns, source="mock.localizer", validity=validity, reason=reason)
    return op.read_pose([1.0, 2.0, 0.0, 0.0, 0.0, S, S], header, "base_footprint", FRAMES)


POINTS = np.array([[1.0, 2.0, 3.0, 42.0], [0.0, 0.0, 0.0, 7.0]], dtype=np.float32)


def run(points=POINTS, header=None, target="camera_front", pose=None):
    return op.process(points, header or cloud_header(), extrinsics=SIM, target_frame=target,
                      take_seq=itertools.count().__next__, pose=pose)


def test_a_static_change_moves_xyz_where_the_hand_says_and_keeps_intensity():
    """(1,2,3) in rslidar -> (-2, -2.9, 0.85) in camera_front (see test_transform)."""
    moved, header, drops = run()
    assert drops == {}
    assert moved[0, :3] == pytest.approx([-2.0, -2.9, 0.85], abs=1e-6)
    assert moved[:, 3].tolist() == [42.0, 7.0]
    assert moved.dtype == np.float32


def test_the_input_array_is_not_modified():
    before = POINTS.copy()
    run()
    assert np.array_equal(POINTS, before)


def test_the_header_keeps_the_capture_and_names_the_target():
    _, header, _ = run()
    assert (header.frame_id, header.stamp_ns, header.source) == ("camera_front", T0, "mock.lidar")
    assert header.validity == "ok" and header.seq == 0


def test_a_degraded_cloud_stays_degraded():
    _, header, _ = run(header=cloud_header(validity="stale", reason="late"))
    assert (header.validity, header.reason) == ("stale", "late")


def test_a_dynamic_target_with_no_pose_is_a_counted_drop():
    moved, header, drops = run(target="odom")
    assert moved is None and header is None
    assert drops == {"no_pose": 1}


def test_a_dynamic_target_composes_with_the_pose():
    """(0,0,0) in rslidar -> (0.25, 0, 0.35) in base_footprint -> yaw 90 and
    shift (1, 2, 0) -> (1, 2.25, 0.35) in odom."""
    moved, header, drops = run(target="odom", pose=a_pose())
    assert drops == {}
    assert moved[1, :3] == pytest.approx([1.0, 2.25, 0.35], abs=1e-6)
    assert (header.frame_id, header.validity) == ("odom", "ok")


@pytest.mark.parametrize("offset_ms", [101, -101])
def test_a_pose_too_far_from_the_cloud_in_either_direction_marks_it_stale(offset_ms):
    pose = a_pose(stamp_ns=T0 + offset_ms * 1_000_000)
    moved, header, _ = run(target="odom", pose=pose)
    assert moved is not None, "a stale pose is forwarded, not dropped"
    assert (header.validity, header.reason) == ("stale", "stale_pose")


def test_a_pose_within_the_limit_keeps_the_cloud_ok():
    _, header, _ = run(target="odom", pose=a_pose(stamp_ns=T0 - 100 * 1_000_000))
    assert header.validity == "ok"


def test_a_degraded_pose_passes_its_validity_on():
    _, header, _ = run(target="odom", pose=a_pose(validity="low_confidence", reason="few_points"))
    assert (header.validity, header.reason) == ("low_confidence", "pose_few_points")


def test_a_degraded_cloud_keeps_its_own_reason_over_a_stale_pose():
    _, header, _ = run(header=cloud_header(validity="missing", reason="gap"), target="odom",
                       pose=a_pose(stamp_ns=T0 + 10**9))
    assert (header.validity, header.reason) == ("missing", "gap")


def test_a_pose_is_ignored_when_the_path_is_static():
    _, header, _ = run(target="camera_front", pose=a_pose(stamp_ns=T0 + 10**9))
    assert header.validity == "ok"


def test_a_seq_is_taken_only_for_a_published_cloud():
    counter = itertools.count()
    op.process(POINTS, cloud_header(), extrinsics=SIM, target_frame="odom",
               take_seq=counter.__next__)
    assert next(counter) == 0, "a dropped cloud must not consume a sequence number"


def test_the_module_staleness_default_matches_the_declaration():
    decl = load_operators(PACK / "operators.yaml")["frame_transform"]
    assert decl.inputs["pose"].max_age_ms == op.POSE_MAX_AGE_MS


def test_config_needs_a_target_frame(monkeypatch):
    monkeypatch.setenv("ORS_FRAMES", str(ROOT / "specs" / "operators" / "frames.yaml"))
    monkeypatch.setenv("ORS_EXTRINSICS", str(SIM.path))
    monkeypatch.delenv("TARGET_FRAME", raising=False)
    with pytest.raises(ConfigError, match="TARGET_FRAME"):
        op.config_from_env()


@pytest.mark.parametrize("target, match", [("world", "use 'map'"), ("none", "no spatial meaning")])
def test_config_refuses_a_target_that_is_not_a_spatial_frame(monkeypatch, target, match):
    monkeypatch.setenv("ORS_FRAMES", str(ROOT / "specs" / "operators" / "frames.yaml"))
    monkeypatch.setenv("ORS_EXTRINSICS", str(SIM.path))
    monkeypatch.setenv("TARGET_FRAME", target)
    with pytest.raises(ConfigError, match=match):
        op.config_from_env()


def test_config_refuses_a_bad_calibration(monkeypatch, tmp_path):
    bad = tmp_path / "extrinsics.yaml"
    bad.write_text("contract_version: 1.0.0\n", encoding="utf-8")
    monkeypatch.setenv("ORS_FRAMES", str(ROOT / "specs" / "operators" / "frames.yaml"))
    monkeypatch.setenv("ORS_EXTRINSICS", str(bad))
    monkeypatch.setenv("TARGET_FRAME", "base_link")
    with pytest.raises(ConfigError, match="missing the required key"):
        op.config_from_env()
```

- [ ] **Step 3: Run them to see them fail**

Run: `cd capabilities/perception && PYTHONPATH= python -m pytest -q; cd -`
Expected: FAIL with `ModuleNotFoundError: No module named 'open_robot_perception.transform.frame_transform_op'`.

- [ ] **Step 4: Write the pure half of the operator**

Create `capabilities/perception/open_robot_perception/transform/frame_transform_op.py`:

```python
"""Change the frame a point cloud is expressed in, explicitly and checked.

The contract layer never transforms; this operator is where transforming
happens. Before launch, the validator's check 6 has already confirmed that the
robot's calibration holds a path from the input frame to TARGET_FRAME, or that
a pose input is wired when the path crosses a dynamic edge.

Only x, y and z move. Intensity and any other per-point field pass through,
and so do the capture stamp and source, because the cloud still describes the
same instant from the same sensor.
"""

from dataclasses import dataclass
from typing import Callable, Dict, Optional, Tuple

import numpy as np

from open_robot_operator.envelope import Header, derive
from open_robot_operator.frames import DynamicEdgeError, Extrinsics, FrameDict
from open_robot_operator.transform import Transform, lookup, pose_transform

SCHEMA = "openrobot.sensor.point_cloud/1.0.0"
ITEM_STEP = 4
# Must equal the max_age_ms operators.yaml declares on the pose input; a test
# pins the two together.
POSE_MAX_AGE_MS = 100


@dataclass(frozen=True)
class Pose:
    """The latest pose received, held as a ready transform."""

    transform: Transform
    header: Header


def read_pose(values, header: Header, child_frame: str, frames: FrameDict) -> Pose:
    return Pose(pose_transform(values, header, child_frame, frames), header)


def resolve(extrinsics: Extrinsics, src: str, dst: str,
            pose: Optional[Pose]) -> Tuple[Optional[Transform], bool]:
    """The transform for one cloud, and whether it used the pose.

    A static path never consults the pose. A dynamic one composes
    src -> pose child, the pose, then pose frame -> dst; with no pose yet there
    is no transform at all.
    """
    try:
        return lookup(extrinsics, src, dst), False
    except DynamicEdgeError:
        if pose is None:
            return None, False
    moving = pose.transform
    composed = (lookup(extrinsics, src, moving.src)
                .then(moving)
                .then(lookup(extrinsics, moving.dst, dst)))
    return composed, True


def transform_cloud(points: np.ndarray, transform: Transform) -> np.ndarray:
    out = np.array(points, dtype=np.float32, copy=True)
    out[:, :3] = transform.apply_points(out[:, :3]).astype(np.float32)
    return out


def _pose_quality(cloud: Header, pose: Pose, max_age_ms: int) -> Tuple[str, Optional[str]]:
    """What composing with this pose does to an otherwise sound cloud.

    Either direction counts: a pose far newer than the cloud places it as
    wrongly as one far older.
    """
    if pose.header.validity != "ok":
        return pose.header.validity, f"pose_{pose.header.reason}"
    if abs(cloud.stamp_ns - pose.header.stamp_ns) > max_age_ms * 1_000_000:
        return "stale", "stale_pose"
    return "ok", None


def process(points: np.ndarray, header: Header, *, extrinsics: Extrinsics,
            target_frame: str, take_seq: Callable[[], int], pose: Optional[Pose] = None,
            max_age_ms: int = POSE_MAX_AGE_MS
            ) -> Tuple[Optional[np.ndarray], Optional[Header], Dict[str, int]]:
    """Transform one cloud. Returns (points, header, drops).

    Points and header are None when the cloud cannot be placed in
    `target_frame` at all. That is a counted drop, never a cloud published
    under a frame it is not in. `take_seq` is called only for a published
    cloud, so a gap in seq still means loss on the edge downstream.
    """
    transform, used_pose = resolve(extrinsics, header.frame_id, target_frame, pose)
    if transform is None:
        return None, None, {"no_pose": 1}
    validity, reason = header.validity, header.reason
    if used_pose and validity == "ok":
        validity, reason = _pose_quality(header, pose, max_age_ms)
    out = derive([header], schema=SCHEMA, frame_id=target_frame, seq=take_seq(),
                 validity=validity, reason=reason)
    return transform_cloud(points, transform), out, {}


def config_from_env() -> dict:
    """Read and check everything at start-up, so a bad calibration stops the
    node before its first message rather than on it."""
    from open_robot_operator.frames import FrameError, load_extrinsics, load_frames
    from open_robot_operator.node import ConfigError, env_int, env_str

    try:
        frames = load_frames(env_str("ORS_FRAMES"))
        extrinsics = load_extrinsics(env_str("ORS_EXTRINSICS"), frames)
        target = env_str("TARGET_FRAME")
        if frames.require(target).kind == "none":
            raise ConfigError(
                "TARGET_FRAME is 'none', which has no spatial meaning; a cloud "
                "cannot be transformed into it")
    except (FrameError, OSError) as error:
        raise ConfigError(str(error)) from None
    return {
        "extrinsics": extrinsics,
        "target_frame": target,
        "max_age_ms": env_int("POSE_MAX_AGE_MS", POSE_MAX_AGE_MS, minimum=1),
        "item_step": env_int("ITEM_STEP", ITEM_STEP, minimum=3),
    }
```

`ConfigError` subclasses `ValueError` and `FrameError` subclasses `ValueError`, but `ConfigError` is not a `FrameError`, so the `raise ConfigError(...)` inside the `try` is not caught by the `except`.

- [ ] **Step 5: Run the tests to see them pass**

Run: `cd capabilities/perception && PYTHONPATH= python -m pytest -q; cd -`
Expected: PASS (18 tests).

- [ ] **Step 6: Commit**

```bash
git add capabilities/perception
git commit -m "feat(perception): frame_transform, static or composed with the latest pose"
```

---

## Task 10: The node loop, the sink, the dataflow and conformance

**Files:**
- Modify: `capabilities/perception/open_robot_perception/transform/frame_transform_op.py` (append `main`)
- Create: `capabilities/perception/open_robot_perception/mocks/cloud_sink.py`
- Create: `capabilities/perception/dataflows/node.sh`, `transform-chain.yml`, `mocks/operators.yaml`
- Test: `capabilities/perception/tests/test_conformance.py`

- [ ] **Step 1: Write the failing conformance tests**

Create `capabilities/perception/tests/test_conformance.py`:

```python
"""The validator, run as a test, for the perception pack's registry and its
dataflow. Mirrors data-processing's conformance suite."""

import ast
import importlib
from pathlib import Path

import pytest
import yaml

from open_robot_operator.declare import load_operators
from open_robot_operator.frames import load_extrinsics, load_frames
from open_robot_operator.validate import load_dataflow, validate_dataflow

PACK = Path(__file__).resolve().parents[1]
ROOT = PACK.parents[1]
DATAPROC_MOCKS = ROOT / "capabilities" / "data-processing" / "dataflows" / "mocks"
MOCKS = PACK / "dataflows" / "mocks"
DATAFLOWS = sorted(PACK.joinpath("dataflows").glob("*.yml"))
LAUNCHER = PACK / "dataflows" / "node.sh"
SIM = ROOT / "robots" / "simulated-mobile-robot" / "extrinsics.yaml"

PROVIDED = load_operators(PACK / "operators.yaml")
DECLS = {**PROVIDED, **load_operators(DATAPROC_MOCKS / "operators.yaml"),
         **load_operators(MOCKS / "operators.yaml")}
EXTRINSICS = load_extrinsics(SIM, load_frames(ROOT / "specs" / "operators" / "frames.yaml"))


def _nodes(path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))["nodes"]


def test_the_pack_declares_frame_transform():
    assert tuple(PROVIDED) == ("frame_transform",)


def test_mocks_are_declared_outside_the_pack_registry():
    assert all(name.startswith("mock_") for name in load_operators(MOCKS / "operators.yaml"))


def test_frame_transform_takes_its_output_frame_from_the_dataflow():
    assert PROVIDED["frame_transform"].outputs["cloud"].env_var == "TARGET_FRAME"


@pytest.mark.parametrize("name", sorted(DECLS))
def test_every_declared_module_is_importable(name):
    importlib.import_module(DECLS[name].module)


@pytest.mark.parametrize("name", sorted(PROVIDED) + sorted(load_operators(MOCKS / "operators.yaml")))
def test_no_module_imports_dora_at_load_time(name):
    """Walk the AST rather than grepping: a substring scan cannot tell an
    import from the word in a docstring."""
    module = importlib.import_module(DECLS[name].module)
    tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
    top_level = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            top_level.extend(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            top_level.append(node.module.split(".")[0])
    assert "dora" not in top_level


def test_the_expected_dataflows_exist():
    assert [p.name for p in DATAFLOWS] == ["transform-chain.yml"]


@pytest.mark.parametrize("path", DATAFLOWS, ids=lambda p: p.name)
def test_every_dataflow_validates_against_the_simulator_calibration(path):
    violations = validate_dataflow(load_dataflow(path), DECLS, EXTRINSICS)
    assert violations == [], "\n".join(str(v) for v in violations)


@pytest.mark.parametrize("path", DATAFLOWS, ids=lambda p: p.name)
def test_without_a_calibration_the_transform_check_blocks(path):
    """Pins check 6 to this pack: the chain changes frames, so it must not pass
    with no calibration given."""
    found = validate_dataflow(load_dataflow(path), DECLS)
    assert found and all(v.check == "transform" and v.blocking for v in found)


def test_the_launcher_exists_is_executable_and_hard_codes_no_host():
    assert LAUNCHER.stat().st_mode & 0o111
    text = LAUNCHER.read_text(encoding="utf-8")
    assert "/home/" not in text and ".venv" not in text


@pytest.mark.parametrize("path", DATAFLOWS, ids=lambda p: p.name)
def test_each_node_launches_the_module_its_declaration_names(path):
    for node in _nodes(path):
        assert node["path"] == "node.sh"
        operator = (node.get("env") or {}).get("OPERATOR", node["id"])
        assert DECLS[operator].module == node["args"], node["id"]


@pytest.mark.parametrize("path", DATAFLOWS, ids=lambda p: p.name)
def test_every_source_has_a_tick_and_a_frame_budget(path):
    flow = load_dataflow(path)
    for node in _nodes(path):
        operator = (node.get("env") or {}).get("OPERATOR", node["id"])
        if not any(p.builtin is None for p in DECLS[operator].inputs.values()):
            assert (node["id"], "tick") in flow.builtins
            assert "FRAMES" in (node.get("env") or {})
```

- [ ] **Step 2: Run them to see them fail**

Run: `cd capabilities/perception && PYTHONPATH= python -m pytest tests/test_conformance.py -q; cd -`
Expected: FAIL with `FileNotFoundError` for `dataflows/mocks/operators.yaml` at collection.

- [ ] **Step 3: Create the mock declaration and the sink**

`capabilities/perception/dataflows/mocks/operators.yaml`:

```yaml
# Mocks the perception examples need to be a complete, checkable graph. Kept
# out of the pack registry: a mock sink is not a capability anyone deploys.
# The lidar mock is data-processing's and is declared there.
contract_version: 1.0.0

operators:
  - name: mock_point_cloud_sink
    module: open_robot_perception.mocks.cloud_sink
    inputs:
      cloud:
        schema: openrobot.sensor.point_cloud/^1.0
        frame: camera_front
    outputs:
      recorded:
        schema: openrobot.sensor.point_cloud/1.0.0
        frame: same_as:cloud
```

The sink requires `camera_front`, so check 1's frame test also proves that `frame_transform`'s `env:` output resolves to what the dataflow says.

`capabilities/perception/open_robot_perception/mocks/cloud_sink.py`:

```python
"""A sink that records the first points of the first cloud it receives, so
the transform chain's record comes from a real dataflow rather than from
calling the pure functions in a loop."""

import numpy as np

from open_robot_operator.envelope import Header

KEEP = 3


def summarise(points, header: Header) -> dict:
    rows = np.asarray(points, dtype=np.float64)[:KEEP]
    return {
        "frame_id": header.frame_id,
        "stamp_ns": header.stamp_ns,
        "source": header.source,
        "validity": header.validity,
        "first_points": [[float(v) for v in row] for row in rows],
    }


def main() -> None:  # pragma: no cover - needs the dora runtime
    import json
    import pathlib

    from dora import Node

    from open_robot_dataproc.filter.point_cloud_op import as_points
    from open_robot_operator.node import carried_header, env_str
    from open_robot_operator.wire import SeqSource, header_to_metadata, metadata_to_header

    out_path = pathlib.Path(env_str("RECORD_PATH"))
    seq = SeqSource()
    first = None
    messages = 0

    node = Node()
    for event in node:
        if event["type"] != "INPUT" or event["id"] != "cloud":
            continue
        header = metadata_to_header(event["metadata"])
        item_step = int(event["metadata"].get("item_step", 4))
        points = as_points(event["value"].to_numpy(), item_step)
        if first is None:
            first = summarise(points, header)
        messages += 1
        out = carried_header(header, schema="openrobot.sensor.point_cloud/1.0.0",
                             declared_frame="same_as:cloud", port="cloud", seq=seq.take())
        node.send_output("recorded", event["value"],
                         metadata=header_to_metadata(out, item_step=item_step))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps({"messages": messages, "first": first}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    node.log_info(f"recorded {messages} clouds, wrote {out_path}")


if __name__ == "__main__":  # pragma: no cover
    main()
```

The sink forwards the incoming arrow array unchanged, so it needs no pyarrow import of its own.

- [ ] **Step 4: Append the node loop to `frame_transform_op.py`**

```python
def main() -> None:  # pragma: no cover - needs the dora runtime
    """The dora node loop. `dora` is imported here, not at module scope, so
    every pure function above stays testable without the runtime."""
    import time

    import pyarrow as pa
    from dora import Node

    from open_robot_dataproc.filter.point_cloud_op import as_points, to_flat
    from open_robot_operator.frames import FrameError
    from open_robot_operator.node import (
        DEFAULT_DIAG_EVERY, OperatorNode, diagnostics_metadata, env_int, node_id_from_env,
    )
    from open_robot_operator.wire import header_to_metadata, metadata_to_header, payload_nbytes

    config = config_from_env()
    extrinsics = config["extrinsics"]
    state = OperatorNode(
        node_id=node_id_from_env(),
        diagnostics_port="diag",
        diag_every=env_int("DIAG_EVERY", DEFAULT_DIAG_EVERY, minimum=1),
    )
    pose = None

    node = Node()
    for event in node:
        if event["type"] != "INPUT":
            continue
        if event["id"] == "pose":
            try:
                pose = read_pose(event["value"].to_numpy(), metadata_to_header(event["metadata"]),
                                 str(event["metadata"].get("child_frame", "")), extrinsics.frames)
            except ValueError:
                state.counters.count_drop("bad_pose")
            continue
        if event["id"] != "cloud":
            continue

        header = metadata_to_header(event["metadata"])
        raw = event["value"].to_numpy()
        started = time.perf_counter_ns()
        points = as_points(raw, config["item_step"])
        try:
            moved, out_header, drops = process(
                points, header, extrinsics=extrinsics, target_frame=config["target_frame"],
                take_seq=lambda: state.seq("cloud"), pose=pose, max_age_ms=config["max_age_ms"])
        except FrameError:
            moved, out_header, drops = None, None, {"bad_frame": 1}
        elapsed = time.perf_counter_ns() - started

        out_items, out_bytes = 0, 0
        if moved is not None:
            payload = pa.array(to_flat(moved))
            node.send_output("cloud", payload,
                             metadata=header_to_metadata(out_header, item_step=config["item_step"]))
            out_items, out_bytes = len(moved), payload_nbytes(payload)
        state.tally(in_items=len(points), in_bytes=payload_nbytes(raw),
                    out_items=out_items, out_bytes=out_bytes, proc_ns=elapsed, drops=drops)
        if state.due():
            blob, diag_header, _ = state.diagnostics()
            node.send_output("diag", pa.array(list(blob), type=pa.uint8()),
                             metadata=diagnostics_metadata(diag_header))


if __name__ == "__main__":  # pragma: no cover
    main()
```

- [ ] **Step 5: Create the launcher and the dataflow**

`capabilities/perception/dataflows/node.sh`:

```bash
#!/usr/bin/env bash
# Launch one operator node with the three package roots on PYTHONPATH:
# this pack, data-processing (whose mocks and point-cloud helpers it reuses)
# and the contract package. Every root is resolved from this script's own
# location, so the same YAML runs from any checkout.
#
# ORS_FRAMES defaults to the repository's frame dictionary; a dataflow may
# override it in a node's env.
set -euo pipefail

here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
pack=$(cd -- "$here/.." && pwd)                 # capabilities/perception
root=$(cd -- "$pack/../.." && pwd)              # repository root

export PYTHONPATH="$pack:$root/capabilities/data-processing:$root/packages/open-robot-operator${PYTHONPATH:+:$PYTHONPATH}"
export ORS_FRAMES="${ORS_FRAMES:-$root/specs/operators/frames.yaml}"
exec "${PYTHON:-python3}" -m "$@"
```

Then run: `chmod +x capabilities/perception/dataflows/node.sh`

`capabilities/perception/dataflows/transform-chain.yml`:

```yaml
# A mock lidar in rslidar, moved into the front camera's optical frame by
# frame_transform against the simulator's calibration, and recorded.
# camera_front rather than base_link: rslidar is mounted without rotation, so
# only this target exercises a rotation and an inverted edge.
#
# Validate, then run, from the repository root and capabilities/perception:
#   python -m open_robot_operator.validate capabilities/perception/dataflows/transform-chain.yml \
#     --pack capabilities/perception --pack capabilities/data-processing/dataflows/mocks \
#     --pack capabilities/perception/dataflows/mocks \
#     --extrinsics robots/simulated-mobile-robot/extrinsics.yaml
#   cd capabilities/perception && dora up && dora run dataflows/transform-chain.yml && dora destroy
nodes:
  - id: mock_lidar
    path: node.sh
    args: open_robot_dataproc.mocks.point_cloud_source
    env:
      OPERATOR: mock_point_cloud_source
      FRAMES: "10"
      POINTS: "256"
    inputs:
      tick: dora/timer/millis/50
    outputs:
      - cloud

  - id: to_camera
    path: node.sh
    args: open_robot_perception.transform.frame_transform_op
    env:
      OPERATOR: frame_transform
      TARGET_FRAME: camera_front
      ORS_EXTRINSICS: ../../../robots/simulated-mobile-robot/extrinsics.yaml
      DIAG_EVERY: "10"
    inputs:
      cloud: mock_lidar/cloud
    outputs:
      - cloud
      - diag

  - id: sink
    path: node.sh
    args: open_robot_perception.mocks.cloud_sink
    env:
      OPERATOR: mock_point_cloud_sink
      RECORD_PATH: ../records/transform-chain.json
    inputs:
      cloud: to_camera/cloud
    outputs:
      - recorded
```

- [ ] **Step 6: Run the perception suite**

Run: `cd capabilities/perception && PYTHONPATH= python -m pytest -q; cd -`
Expected: PASS.

- [ ] **Step 7: Run the validator CLI by hand**

Run from the repository root:
```bash
PYTHONPATH=packages/open-robot-operator python -m open_robot_operator.validate \
  capabilities/perception/dataflows/transform-chain.yml \
  --pack capabilities/perception --pack capabilities/data-processing/dataflows/mocks \
  --pack capabilities/perception/dataflows/mocks \
  --extrinsics robots/simulated-mobile-robot/extrinsics.yaml
```
Expected: `capabilities/perception/dataflows/transform-chain.yml: OK`, exit 0. Then run the same command without `--extrinsics`. Expected: `[transform]` errors and exit 1.

- [ ] **Step 8: Commit**

```bash
git add capabilities/perception
git commit -m "feat(perception): frame_transform node loop, a recording sink, and a checked chain"
```

---

## Task 11: Run the chain under dora and commit its record

**Files:**
- Create (by running): `capabilities/perception/records/transform-chain.json`
- Test: `capabilities/perception/tests/test_record.py`

- [ ] **Step 1: Write the failing record test**

Create `capabilities/perception/tests/test_record.py`:

```python
"""The record is produced by running dataflows/transform-chain.yml under dora,
then committed. The expectation is recomputed here from the mock's
deterministic first frame with a hand formula -- never with the transform
code."""

import json
from pathlib import Path

import pytest

from open_robot_dataproc.mocks.point_cloud_source import frame

RECORD = json.loads(
    (Path(__file__).resolve().parents[1] / "records" / "transform-chain.json").read_text(encoding="utf-8")
)


def test_the_record_is_from_a_complete_run():
    assert RECORD["messages"] == 10


def test_the_first_point_landed_where_the_calibration_puts_it():
    cloud, _ = frame(0, points=256)
    x, y, z, intensity = (float(v) for v in cloud[0])
    # rslidar -> base_link: add (0.25, 0, 0.25). base_link -> camera_front:
    # subtract the camera origin (0.40, 0, 0.35), then the optical axes give
    # x_opt = -y, y_opt = -z, z_opt = x.
    bx, by, bz = x + 0.25 - 0.40, y, z + 0.25 - 0.35
    got = RECORD["first"]["first_points"][0]
    assert got[:3] == pytest.approx([-by, -bz, bx], abs=1e-5)
    assert got[3] == pytest.approx(intensity), "intensity must pass through untouched"


def test_the_capture_stamp_and_source_survived_the_transform():
    _, header = frame(0, points=256)
    first = RECORD["first"]
    assert first["stamp_ns"] == header.stamp_ns
    assert first["source"] == header.source
    assert (first["frame_id"], first["validity"]) == ("camera_front", "ok")
```

- [ ] **Step 2: Run it to see it fail**

Run: `cd capabilities/perception && PYTHONPATH= python -m pytest tests/test_record.py -q; cd -`
Expected: FAIL with `FileNotFoundError` for `records/transform-chain.json`.

- [ ] **Step 3: Run the dataflow for real**

```bash
cd capabilities/perception
PYTHONPATH= dora up
PYTHONPATH= dora run dataflows/transform-chain.yml
PYTHONPATH= dora destroy
cd -
```
Expected: the sink logs `recorded 10 clouds, wrote ../records/transform-chain.json`, and the file exists at `capabilities/perception/records/transform-chain.json`.

If the run hangs, check the source has its `tick` wired (handoff §7). If `messages` is below 10, do not edit the test. Find out where the clouds went: `dataflows/out/<run>/log_to_camera.jsonl` shows the transform node's errors. Fix the cause, then rerun.

- [ ] **Step 4: Run the record test**

Run: `cd capabilities/perception && PYTHONPATH= python -m pytest -q; cd -`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add capabilities/perception/records/transform-chain.json capabilities/perception/tests/test_record.py
git commit -m "test(perception): a transform-chain record produced by a real dora run"
```

---

## Task 12: The mutation sweep

**Files:**
- Modify: `tools/mutation-sweep.py`

- [ ] **Step 1: Add the perception suite**

In `tools/mutation-sweep.py`, replace:

```python
SUITES = (CONTRACT, DATAPROC)
```

with:

```python
PERCEPTION = ROOT / "capabilities" / "perception"
SUITES = (CONTRACT, DATAPROC, PERCEPTION)
```

- [ ] **Step 2: Append the seven mutations to `MUTATIONS`**

Add these entries before the closing `]` of `MUTATIONS`:

```python
    (
        "10. a missing extrinsic is quietly treated as identity",
        CONTRACT / "open_robot_operator/frames.py",
        "            if edge is None:\n                raise MissingExtrinsicError(",
        "            if edge is None:\n                continue\n                raise MissingExtrinsicError(",
    ),
    (
        "11. transforms compose even when their frames do not meet",
        CONTRACT / "open_robot_operator/transform.py",
        "        if self.dst != other.src:\n            raise FrameOrderError(",
        "        if False:\n            raise FrameOrderError(",
    ),
    (
        "12. rotation_xyzw is read as w, x, y, z",
        CONTRACT / "open_robot_operator/transform.py",
        "    x, y, z, w = (float(c) for c in q)",
        "    w, x, y, z = (float(c) for c in q)",
    ),
    (
        "13. a calibration file may carry a dynamic edge",
        CONTRACT / "open_robot_operator/frames.py",
        '    if frame.kind != "mounted":\n        raise FrameError(',
        "    if False:\n        raise FrameError(",
    ),
    (
        "14. a cloud composed with a stale pose is forwarded as ok",
        PERCEPTION / "open_robot_perception/transform/frame_transform_op.py",
        '        return "stale", "stale_pose"',
        '        return "ok", None',
    ),
    (
        "15. the validator skips the transform check",
        CONTRACT / "open_robot_operator/validate.py",
        "    found.extend(_transform_violations(dataflow, graph, decls, extrinsics))",
        "    pass",
    ),
    (
        "16. a node may launch with a different calibration than was checked",
        CONTRACT / "open_robot_operator/validate.py",
        "                if launched != checked:",
        "                if False:",
    ),
```

Mutation 16's anchor is indented 16 spaces, as the line is in `validate.py` once Task 8 lands (the plan shows that code inside a list item, which adds 3 more). Each anchor must occur exactly once; the sweep reports `SKIP` otherwise.

- [ ] **Step 3: Confirm each anchor occurs exactly once**

Run:
```bash
python3 - <<'EOF'
import importlib.util, pathlib
spec = importlib.util.spec_from_file_location("sweep", "tools/mutation-sweep.py")
sweep = importlib.util.module_from_spec(spec); spec.loader.exec_module(sweep)
for label, path, anchor, _ in sweep.MUTATIONS:
    n = pathlib.Path(path).read_text(encoding="utf-8").count(anchor)
    print(n, label)
EOF
```
Expected: every line starts with `1`. Fix any anchor that does not, matching the file as it actually is. Never change the code to fit the anchor.

- [ ] **Step 4: Run the sweep, alone**

Nothing else may run tests in this worktree while it runs (handoff §7).

Run: `PYTHONPATH= python tools/mutation-sweep.py`
Expected: `baseline ... green`, every mutation `CAUGHT`, `restored baseline ... green`, `surviving mutations: 0/17`.

If one survives, the suite has a hole. Write the test that kills it first, then rerun. Do not weaken the mutation.

- [ ] **Step 5: Confirm the worktree is clean of mutations**

Run: `git status --short packages capabilities`
Expected: only `tools/mutation-sweep.py` is modified. Any source file listed means a mutation was not restored; restore it with `git checkout -- <file>`.

- [ ] **Step 6: Commit**

```bash
git add tools/mutation-sweep.py
git commit -m "test(sweep): seven transform mutations and the perception suite; 0/17 survive"
```

---

## Task 13: Restate the contract spec, update the manifests, verify everything

**Files:**
- Modify: `docs/superpowers/specs/2026-10-20-operator-contract-and-data-processing-design.md` (§2.4 item 1, §9 frame row, §11.2 first bullet)
- Modify: `component-lock.yaml` (the `open-robot-operator` entry; add `open-robot-perception`)
- Modify: `capabilities/data-processing/pack.yaml` (requires `open-robot-operator ^0.2`)

- [ ] **Step 1: Restate §2.4 item 1**

Replace this text in the contract spec:

```markdown
1. **Not a coordinate-transform engine.** Frames are declared and checked for
   agreement; transformation between frames is never performed here. That work
   belongs to the perception and control operators. Building a TF tree would
   turn sub-project 0 into a project of its own.
```

with:

```markdown
1. **Not a coordinate-transform engine.** The envelope and the validator never
   transform. A frame change happens only inside an operator that declares it,
   using `open_robot_operator.transform` against a per-robot calibration the
   validator has checked (check 6). The library ships with this package, but
   only as an optional extra, and it holds a static tree plus the latest pose
   rather than a TF buffer. See
   `2026-10-20-coordinate-transformation-design.md`.
```

- [ ] **Step 2: Restate the §9 frame-handling row**

Replace:

```markdown
| Frame handling | Declare and check agreement; never transform | Largest scope cut; a TF tree would make sub-project 0 its own project |
```

with:

```markdown
| Frame handling | Declare and check agreement; the envelope and validator never transform. Transformation is explicit, in a declared operator, through `open_robot_operator.transform` (restated 2026-10-20) | Five v1.3 items need transforms and nothing owned them; a static tree plus the latest pose meets every acceptance line without a TF buffer |
```

- [ ] **Step 3: Restate the §11.2 first bullet**

Replace the bullet that begins `- **Sub-project 2 (item 13)** loses the tracking work and keeps the coordinate` (through `amendment does not reduce it.`) with:

```markdown
- **Sub-project 2 (item 13)** loses the tracking work. It no longer carries
  coordinate transformation alone: `2026-10-20-coordinate-transformation-design.md`
  puts the library in `open_robot_operator.transform`, shared by items 13, 14,
  the motion-capture item and the simulator. Item 13 still owns fusion and
  camera projection, and calls `lookup` for their extrinsic half.
```

- [ ] **Step 4: Update the manifests**

In `component-lock.yaml`, change the `open-robot-operator` entry's `version: 0.1.0` to `version: 0.2.0`, and add one line to the end of its comment block:

```yaml
    # 0.2.0 adds open_robot_operator.frames, the [transform] extra and
    # validator check 6.
```

Then add this entry after `open-robot-dataproc`:

```yaml
  open-robot-perception:
    version: 0.1.0
    # The perception capability pack (contract item 13). Starts with
    # frame_transform; fusion, clustering and detection land in sub-project 2.
    # Depends on open-robot-dataproc for its point-cloud helpers and mocks.
    digest: unresolved
```

In `capabilities/data-processing/pack.yaml`, change the `open-robot-operator` requirement from `version: ^0.1` to `version: ^0.2`.

- [ ] **Step 5: Full verification**

Run each command and read its output before moving on:
```bash
PYTHONPATH= python -m pytest tests/test_specs.py -q
PYTHONPATH= python -m pytest packages/open-robot-operator/tests -q
PYTHONPATH= python -m pytest capabilities/data-processing/tests -q
PYTHONPATH= python -m pytest capabilities/perception/tests -q
PYTHONPATH= python tools/mutation-sweep.py
cd capabilities/data-processing && PYTHONPATH= dora up && PYTHONPATH= dora run dataflows/preprocess-chain.yml && PYTHONPATH= dora destroy; cd -
git status --short
```

Expected:
- All four suites pass. data-processing is still `349 passed`, and every other count is higher than its baseline.
- The sweep reports `0/17`.
- The existing preprocess chain still runs end to end.
- `git status` shows only the files this task touches. A run regenerates `records/chain-statistics.txt`; if the content changed only in timings, `git checkout -- capabilities/data-processing/records` restores it.

- [ ] **Step 6: Commit**

```bash
git add docs/superpowers/specs/2026-10-20-operator-contract-and-data-processing-design.md component-lock.yaml capabilities/data-processing/pack.yaml
git commit -m "docs(spec): restate frame handling as declared transforms; bump the contract to 0.2.0"
```

---

## What this plan does not build

These come from spec §10 and are repeated here so that nobody adds them mid-plan:

- No time-indexed transform buffer and no interpolation.
- No URDF or MJCF parsing at run time.
- No kinematic chains (dora-moveit2's forward kinematics stays where it is).
- No camera intrinsics or projection.
- No calibration procedures.
- No C++ library.
- No upstream adapters. Sub-projects 2 and 3 write them: hdl_localization → `state.pose` is the recommended first one, using `xyzw_from_named` and `stamp_ns_from_seconds`.
- No obstacle-list transform. The obstacle-list schema does not exist yet.
