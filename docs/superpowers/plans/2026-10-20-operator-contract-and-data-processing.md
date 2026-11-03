# Operator Contract and Data-Processing Operators Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the shared operator contract layer (declarative port manifests, a runtime envelope, and a pre-launch dataflow validator) together with its first real consumer, the data-processing capability pack of seven operators and two chain tools.

**Architecture:** One mechanism with two faces. `open_robot_operator` defines an envelope whose header splits into fields that propagate verbatim (`stamp_ns`, `source`) and fields every producer must restate (`schema`, `frame_id`, `seq`, `validity`, `reason`); the same vocabulary appears in each pack's `operators.yaml` as a static projection, which a validator checks against a dora dataflow before launch. `capabilities/data-processing` then implements filtering, compression, cleaning and format conversion on top of it, exercising every clause of the contract.

**Tech Stack:** Python 3.12 (floor 3.10), pyarrow 24, numpy 1.26, scipy (`ndimage`, `signal`, `spatial.cKDTree`), Pillow 10.4, zstandard 0.23, jsonschema 4.23, PyYAML 6, pytest 9. The dora runtime is imported only inside `main()` bodies, never at module import time.

**Design doc:** `docs/superpowers/specs/2026-10-20-operator-contract-and-data-processing-design.md`

---

## Environment facts established before planning

Verify these yourself if anything behaves unexpectedly; they were measured on this host.

| Fact | Consequence |
|---|---|
| `cv2` is **not installed**; scipy, PIL, zstandard, jsonschema, PyYAML are | `image_filter` uses `scipy.ndimage`; there is no bilateral mode |
| The installed `dora` binding is 0.2.6 while the stack pins 1.0.1 | No task runs a dataflow. Every operator is tested through a pure function, and a test asserts each node module imports with `dora` absent |
| A global `open_robot_sdk` resolves to an unrelated project at `/Users/Shared/github_bdingff/open-robot-sdk` | Both new packages carry their own `conftest.py` that puts their roots at the **front** of `sys.path`. Do not `pip install -e` anything |
| Quantised point-cloud round-trip error reaches exactly `precision/2` | Assert `<= precision/2 + 1e-6`, never `<` |

## File structure

**Contract layer — `packages/open-robot-operator/`**

| File | Responsibility |
|---|---|
| `pyproject.toml` | Package metadata; deps `pyarrow`, `jsonschema`, `pyyaml` |
| `conftest.py` | Puts the package root first on `sys.path` |
| `open_robot_operator/__init__.py` | Re-exports the public names |
| `open_robot_operator/schemaref.py` | Parse `id/version` references; SemVer caret matching |
| `open_robot_operator/envelope.py` | `VALIDITY`, `Header`, `Upgrade`, `originate()`, `derive()` and both invariants |
| `open_robot_operator/counters.py` | `Counters`: per-stage tallies, with one bucket per drop reason |
| `open_robot_operator/declare.py` | Load and type-check `operators.yaml` into `OperatorDecl`/`PortDecl` |
| `open_robot_operator/resolve.py` | Frame resolution across the dataflow graph, with cycle detection |
| `open_robot_operator/validate.py` | The five checks, `Violation`, `validate_dataflow()`, `__main__` entry |
| `open_robot_operator/wire.py` | The header on the wire, `SeqSource`, the same-host age rule, and `output_frame()` |

**Normative artifacts — `specs/operators/`**

| File | Responsibility |
|---|---|
| `frames.yaml` | Frame dictionary — contract item 14's 坐标系字典, plus the `none` sentinel |
| `units.yaml` | Unit dictionary — contract item 14's 单位字典, ASCII symbols only |
| `schemas/_meta.schema.json` | The shape every payload schema must satisfy |
| `schemas/*.json` | Eight payload schemas, each field carrying its unit |

**Data-processing pack — `capabilities/data-processing/`**

| File | Responsibility |
|---|---|
| `pack.yaml` | CapabilityPack manifest, camelCase |
| `operators.yaml` | Port declarations, snake_case — item 15's registry |
| `pyproject.toml`, `conftest.py` | As above, plus a path entry for `open-robot-operator` |
| `open_robot_dataproc/filter/point_cloud_op.py` | `voxel`, `passthrough`, `outlier`, `accumulate` |
| `open_robot_dataproc/filter/image_op.py` | `gaussian`, `median`, `temporal_average` |
| `open_robot_dataproc/filter/state_op.py` | `moving_average`, `lowpass` |
| `open_robot_dataproc/compress/image_op.py` | JPEG lossy, PNG lossless |
| `open_robot_dataproc/compress/point_cloud_op.py` | Quantise+zstd lossy, zstd lossless |
| `open_robot_dataproc/clean/cleaner_op.py` | Four defect classes, four independent counters, the only legal upgrade |
| `open_robot_dataproc/convert/ros2_codec_op.py` | `openrobot.*` ↔ ROS 2 dicts, both directions |
| `open_robot_dataproc/tools/diag_collector.py` | Per-stage reduction ratios and latencies |
| `open_robot_dataproc/tools/ab_compare.py` | Same input through and around the chain |
| `open_robot_dataproc/mocks/*.py` | A cloud source, a state source that plants all four defects, and a recording sink |
| `dataflows/mocks/operators.yaml` | The mocks' declarations, kept out of the pack's own registry |
| `dataflows/preprocess-chain.yml`, `dataflows/ab-compare.yml` | Orchestration examples and the validator's conformance corpus |
| `records/*.txt` | The two delivered records, generated by running the chain |

Every `*_op.py` splits into a pure function (tested) and a `main()` that owns the dora loop (not tested, never imported at module load). A conformance test walks each module's AST to prove `dora` is absent from module scope.

There is no `specs/operators/operator-contract-v1.md` task. The design document is the normative text, and a second copy of it would drift; what `specs/operators/` adds is the machine-readable half — the dictionaries and the schemas.

**Repo-level files**

| File | Responsibility |
|---|---|
| `tools/mutation-sweep.py` | Seven mutations, one per load-bearing promise |
| `docs/operator-contract.md` | The entry point for both pieces |
| `tests/test_specs.py` | Keeps the dictionaries and schemas consistent with each other |
| `component-lock.yaml` | Gains both new components |

---

## Task 1: Package skeleton and schema references

**Files:**
- Create: `packages/open-robot-operator/pyproject.toml`
- Create: `packages/open-robot-operator/conftest.py`
- Create: `packages/open-robot-operator/open_robot_operator/__init__.py`
- Create: `packages/open-robot-operator/open_robot_operator/schemaref.py`
- Test: `packages/open-robot-operator/tests/test_schemaref.py`

- [ ] **Step 1: Create the package scaffolding**

`packages/open-robot-operator/pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=68.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "open-robot-operator"
version = "0.1.0"
description = "Operator contract for Open Robot Stack capability packs: message envelope, port declarations, and a pre-launch dataflow validator"
requires-python = ">=3.10"
license = { text = "Apache-2.0" }
dependencies = ["pyarrow>=14", "jsonschema>=4.0", "pyyaml>=6.0"]

[project.optional-dependencies]
dev = ["pytest>=7.0", "pytest-cov>=4.0", "numpy>=1.24"]

[tool.setuptools.packages.find]
include = ["open_robot_operator*"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

`packages/open-robot-operator/conftest.py`:

```python
"""Make the package importable from a bare checkout.

A global `open_robot_sdk` on this machine resolves to an unrelated project of
the same name, so the stack's convention is that each package puts its own
root at the FRONT of sys.path rather than relying on an editable install that
another project may depend on.
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
```

`packages/open-robot-operator/open_robot_operator/__init__.py`:

```python
"""Operator contract for Open Robot Stack capability packs."""

__all__ = ["parse_ref", "satisfies"]

from open_robot_operator.schemaref import parse_ref, satisfies
```

- [ ] **Step 2: Write the failing test**

`packages/open-robot-operator/tests/test_schemaref.py`:

```python
import pytest

from open_robot_operator.schemaref import parse_ref, satisfies


@pytest.mark.parametrize(
    "text,want",
    [
        ("openrobot.sensor.point_cloud/^1.0", ("openrobot.sensor.point_cloud", "^1.0")),
        ("openrobot.sensor.image/1.0.0", ("openrobot.sensor.image", "1.0.0")),
        ("openrobot.state.vector/^0.2", ("openrobot.state.vector", "^0.2")),
    ],
)
def test_parse_ref_splits_id_from_version(text, want):
    assert parse_ref(text) == want


@pytest.mark.parametrize(
    "text",
    [
        "openrobot.sensor.point_cloud",      # no version at all
        "openrobot.sensor.point_cloud/",     # empty version
        "openrobot.sensor.point_cloud/~1.0", # tilde is not a supported operator
        "openrobot.sensor.point_cloud/v1.0", # no 'v' prefix
        "/1.0.0",                            # no id
        "Openrobot.Sensor/1.0.0",            # ids are lower case
        "",
    ],
)
def test_parse_ref_rejects_malformed_references(text):
    with pytest.raises(ValueError):
        parse_ref(text)


@pytest.mark.parametrize(
    "produced,constraint,want",
    [
        # v1.3 §8.5: "^1.0 means >=1.0.0 <2.0.0"
        ("1.0.0", "^1.0", True),
        ("1.2.9", "^1.0", True),
        ("2.0.0", "^1.0", False),
        ("0.9.9", "^1.0", False),
        ("1.0.0", "^1.2", False),   # below the floor
        ("1.2.0", "^1.2", True),
        # standard SemVer treats 0.x as its own compatibility range
        ("0.2.0", "^0.2", True),
        ("0.2.7", "^0.2", True),
        ("0.3.0", "^0.2", False),
        ("0.1.9", "^0.2", False),
        # a bare version is an exact match, not a floor
        ("1.2.3", "1.2.3", True),
        ("1.2.4", "1.2.3", False),
        ("1.2.2", "1.2.3", False),
    ],
)
def test_satisfies(produced, constraint, want):
    assert satisfies(produced, constraint) is want


def test_satisfies_rejects_a_caret_producer():
    """The produced side is always concrete; only the constraint may be a range."""
    with pytest.raises(ValueError):
        satisfies("^1.0", "^1.0")
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `cd packages/open-robot-operator && python3 -m pytest tests/test_schemaref.py -q`
Expected: collection error — `ModuleNotFoundError: No module named 'open_robot_operator.schemaref'`

- [ ] **Step 4: Write the implementation**

`packages/open-robot-operator/open_robot_operator/schemaref.py`:

```python
"""Schema references: `<id>/<version-or-constraint>`.

A reference names a payload structure and the version of it. Producers always
state a concrete version; consumers may state a caret constraint. v1.3 §8.5
defines `^1.0` as `>=1.0.0 <2.0.0` and leaves 0.x unstated, so this follows
standard SemVer and treats each 0.x line as its own compatibility range.
"""

import re
from typing import Tuple

_REF = re.compile(r"^(?P<id>[a-z0-9_]+(?:\.[a-z0-9_]+)*)/(?P<spec>\^?\d+\.\d+(?:\.\d+)?)$")


def parse_ref(text: str) -> Tuple[str, str]:
    """Split a reference into its id and its version spec.

    Raises ValueError for anything that is not exactly `<id>/<spec>`.
    """
    match = _REF.match(text or "")
    if match is None:
        raise ValueError(f"malformed schema reference: {text!r}")
    return match.group("id"), match.group("spec")


def _triple(version: str) -> Tuple[int, int, int]:
    parts = [int(p) for p in version.split(".")]
    while len(parts) < 3:
        parts.append(0)
    return parts[0], parts[1], parts[2]


def satisfies(produced: str, constraint: str) -> bool:
    """Does a concrete produced version satisfy a consumer's constraint?

    `produced` must be concrete. `constraint` is either a caret range or an
    exact version.
    """
    if produced.startswith("^"):
        raise ValueError(f"the produced version must be concrete, got {produced!r}")
    actual = _triple(produced)
    if not constraint.startswith("^"):
        return actual == _triple(constraint)
    floor = _triple(constraint[1:])
    if actual < floor:
        return False
    if floor[0] > 0:
        return actual[0] == floor[0]
    if floor[1] > 0:
        return actual[0] == 0 and actual[1] == floor[1]
    return actual[0] == 0 and actual[1] == 0
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `cd packages/open-robot-operator && python3 -m pytest tests/test_schemaref.py -q`
Expected: PASS, 24 tests

- [ ] **Step 6: Commit**

```bash
git add packages/open-robot-operator
git commit -m "feat(operator): schema references and SemVer caret matching"
```

---

## Task 2: The envelope header

**Files:**
- Create: `packages/open-robot-operator/open_robot_operator/envelope.py`
- Modify: `packages/open-robot-operator/open_robot_operator/__init__.py`
- Test: `packages/open-robot-operator/tests/test_envelope.py`

- [ ] **Step 1: Write the failing test**

`packages/open-robot-operator/tests/test_envelope.py`:

```python
import pytest

from open_robot_operator.envelope import VALIDITY, Header

GOOD = dict(
    schema="openrobot.sensor.point_cloud/1.0.0",
    frame_id="rslidar",
    seq=1,
    stamp_ns=1_700_000_000_000_000_000,
    source="lidar.front",
)


def header(**overrides):
    return Header(**{**GOOD, **overrides})


def test_a_well_formed_header_is_accepted():
    h = header()
    assert h.validity == "ok"
    assert h.reason is None


def test_validity_vocabulary_is_closed():
    assert VALIDITY == (
        "ok",
        "missing",
        "stale",
        "unpaired",
        "low_confidence",
        "rejected",
    )


@pytest.mark.parametrize("bad", ["broken", "OK", "", "none", None])
def test_unknown_validity_is_rejected(bad):
    with pytest.raises(ValueError):
        header(validity=bad)


def test_reason_is_required_when_validity_is_not_ok():
    for value in VALIDITY:
        if value == "ok":
            continue
        with pytest.raises(ValueError):
            header(validity=value)
        with pytest.raises(ValueError):
            header(validity=value, reason="")
        assert header(validity=value, reason="why").reason == "why"


def test_reason_must_be_absent_when_validity_is_ok():
    with pytest.raises(ValueError):
        header(reason="why")


@pytest.mark.parametrize(
    "bad",
    [
        "openrobot.sensor.point_cloud",   # no version
        "openrobot.sensor.point_cloud/",  # empty version — a bare '/' test lets this through
        "",
    ],
)
def test_schema_must_be_a_full_reference(bad):
    with pytest.raises(ValueError):
        header(schema=bad)


def test_schema_must_be_concrete_not_a_constraint():
    """Only a declaration may carry a caret; a message states what it is."""
    with pytest.raises(ValueError):
        header(schema="openrobot.sensor.point_cloud/^1.0")


@pytest.mark.parametrize("bad", ["", None])
def test_frame_id_must_be_present(bad):
    with pytest.raises(ValueError):
        header(frame_id=bad)


@pytest.mark.parametrize("bad", ["", None])
def test_source_must_be_present(bad):
    with pytest.raises(ValueError):
        header(source=bad)


@pytest.mark.parametrize("bad", [-1, 1.0, True, None, float("nan")])
def test_seq_must_be_a_non_negative_int(bad):
    with pytest.raises(ValueError):
        header(seq=bad)


def test_seq_zero_is_the_first_legal_value():
    assert header(seq=0).seq == 0


@pytest.mark.parametrize(
    "bad", [0, -1, 1.0, True, None, float("nan"), float("inf")]
)
def test_stamp_ns_must_be_a_positive_int(bad):
    with pytest.raises(ValueError):
        header(stamp_ns=bad)


def test_bool_is_not_accepted_as_an_int():
    """bool subclasses int, so an isinstance check alone lets True through."""
    with pytest.raises(ValueError):
        header(seq=True)
    with pytest.raises(ValueError):
        header(stamp_ns=True)


def test_the_header_is_immutable():
    h = header()
    with pytest.raises(Exception):
        h.frame_id = "other"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd packages/open-robot-operator && python3 -m pytest tests/test_envelope.py -q`
Expected: collection error — `No module named 'open_robot_operator.envelope'`

- [ ] **Step 3: Write the implementation**

`packages/open-robot-operator/open_robot_operator/envelope.py`:

```python
"""The message envelope.

The header splits along the line that blind metadata pass-through gets wrong.
`stamp_ns` and `source` propagate verbatim through every operator; `schema`,
`frame_id`, `seq`, `validity` and `reason` are restated by whoever produces
the message. Copying a restated field from an input is a contract violation,
which is why operators construct headers through this module instead of
building dicts by hand.
"""

from dataclasses import dataclass
from typing import Optional

from open_robot_operator.schemaref import parse_ref

VALIDITY = ("ok", "missing", "stale", "unpaired", "low_confidence", "rejected")


def _positive_int(name: str, value: object, floor: int) -> int:
    # bool subclasses int, so an isinstance check alone would accept True.
    if isinstance(value, bool) or not isinstance(value, int) or value < floor:
        raise ValueError(f"{name} must be an int >= {floor}, got {value!r}")
    return value


@dataclass(frozen=True)
class Header:
    """The envelope header carried in dora metadata as flat scalars."""

    schema: str
    frame_id: str
    seq: int
    stamp_ns: int
    source: str
    validity: str = "ok"
    reason: Optional[str] = None

    def __post_init__(self) -> None:
        _, spec = parse_ref(self.schema)
        if spec.startswith("^"):
            raise ValueError(
                f"a message states a concrete schema version, not a constraint: {self.schema!r}"
            )
        if not isinstance(self.frame_id, str) or not self.frame_id:
            raise ValueError(f"frame_id must be a non-empty str, got {self.frame_id!r}")
        if not isinstance(self.source, str) or not self.source:
            raise ValueError(f"source must be a non-empty str, got {self.source!r}")
        _positive_int("seq", self.seq, 0)
        _positive_int("stamp_ns", self.stamp_ns, 1)
        if self.validity not in VALIDITY:
            raise ValueError(
                f"unknown validity {self.validity!r}; expected one of {VALIDITY}"
            )
        if self.validity == "ok":
            if self.reason is not None:
                raise ValueError("reason must be None when validity is ok")
        elif not self.reason:
            raise ValueError(
                f"validity {self.validity!r} requires a non-empty reason"
            )
```

Note `float("nan")` and `float("inf")` are rejected by the `isinstance(value, int)`
test, so no separate finiteness check is needed here.

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd packages/open-robot-operator && python3 -m pytest tests/test_envelope.py -q`
Expected: PASS, 32 tests

- [ ] **Step 5: Export the new names**

Replace `packages/open-robot-operator/open_robot_operator/__init__.py` with:

```python
"""Operator contract for Open Robot Stack capability packs."""

__all__ = ["VALIDITY", "Header", "parse_ref", "satisfies"]

from open_robot_operator.envelope import VALIDITY, Header
from open_robot_operator.schemaref import parse_ref, satisfies
```

- [ ] **Step 6: Run the whole suite**

Run: `cd packages/open-robot-operator && python3 -m pytest -q`
Expected: PASS, 56 tests

- [ ] **Step 7: Commit**

```bash
git add packages/open-robot-operator
git commit -m "feat(operator): the envelope header and its field rules"
```

---

## Task 3: Header derivation, the two invariants, and the counters

**Files:**
- Modify: `packages/open-robot-operator/open_robot_operator/envelope.py`
- Create: `packages/open-robot-operator/open_robot_operator/counters.py`
- Modify: `packages/open-robot-operator/open_robot_operator/__init__.py`
- Test: `packages/open-robot-operator/tests/test_derive.py`
- Test: `packages/open-robot-operator/tests/test_counters.py`

- [ ] **Step 1: Write the failing counters test**

`packages/open-robot-operator/tests/test_counters.py`:

```python
import pytest

from open_robot_operator.counters import Counters


def test_a_fresh_counter_set_is_all_zero():
    c = Counters()
    assert c.in_items == 0
    assert c.out_items == 0
    assert c.in_bytes == 0
    assert c.out_bytes == 0
    assert c.proc_ns == 0
    assert c.drops_by_reason == {}
    assert c.upgrades_by_reason == {}


def test_counts_accumulate_rather_than_overwrite():
    """A saturating `=` in place of `+=` passes any single-call test."""
    c = Counters()
    for _ in range(3):
        c.observe_in(items=2, nbytes=100)
        c.observe_out(items=1, nbytes=40)
        c.observe_proc(ns=5)
    assert c.in_items == 6
    assert c.out_items == 3
    assert c.in_bytes == 300
    assert c.out_bytes == 120
    assert c.proc_ns == 15


def test_drop_reasons_are_counted_independently():
    """Item 16 must distinguish missing from outlier from disorder from duplicate."""
    c = Counters()
    c.count_drop("missing", 2)
    c.count_drop("duplicate", 1)
    c.count_drop("missing", 3)
    assert c.drops_by_reason == {"missing": 5, "duplicate": 1}
    assert c.total_drops == 6


def test_a_drop_in_one_bucket_does_not_touch_another():
    c = Counters()
    c.count_drop("outlier", 4)
    assert c.drops_by_reason == {"outlier": 4}
    assert "disorder" not in c.drops_by_reason


def test_upgrades_are_counted_separately_from_drops():
    c = Counters()
    c.count_drop("duplicate", 1)
    c.count_upgrade("dropped_duplicate")
    assert c.drops_by_reason == {"duplicate": 1}
    assert c.upgrades_by_reason == {"dropped_duplicate": 1}
    assert c.total_upgrades == 1


@pytest.mark.parametrize("bad", ["", None])
def test_a_drop_needs_a_reason(bad):
    with pytest.raises(ValueError):
        Counters().count_drop(bad, 1)


@pytest.mark.parametrize("bad", ["", None])
def test_an_upgrade_needs_a_reason(bad):
    with pytest.raises(ValueError):
        Counters().count_upgrade(bad)


@pytest.mark.parametrize("bad", [0, -1, 1.5, True])
def test_a_drop_count_must_be_a_positive_int(bad):
    with pytest.raises(ValueError):
        Counters().count_drop("missing", bad)


def test_reduction_ratio_is_out_over_in():
    c = Counters()
    c.observe_in(items=10, nbytes=1000)
    c.observe_out(items=4, nbytes=250)
    assert c.byte_ratio == pytest.approx(0.25)
    assert c.item_ratio == pytest.approx(0.4)


def test_ratios_are_none_before_any_input():
    """Zero input is not a 100% reduction; it is no measurement."""
    c = Counters()
    assert c.byte_ratio is None
    assert c.item_ratio is None


def test_snapshot_is_a_plain_dict_with_copies():
    c = Counters()
    c.observe_in(items=1, nbytes=10)
    c.count_drop("missing", 1)
    snap = c.snapshot()
    assert snap["in_items"] == 1
    assert snap["drops_by_reason"] == {"missing": 1}
    snap["drops_by_reason"]["missing"] = 99
    assert c.drops_by_reason == {"missing": 1}
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd packages/open-robot-operator && python3 -m pytest tests/test_counters.py -q`
Expected: collection error — `No module named 'open_robot_operator.counters'`

- [ ] **Step 3: Write the counters**

`packages/open-robot-operator/open_robot_operator/counters.py`:

```python
"""Per-operator diagnostic counters.

The chain-level reduction ratio of contract item 16 is the product of these
per-stage ratios, which is why no per-message correlation is built. Drop
reasons are kept in separate buckets because item 16's "对被丢弃的数据计数并
上报" has to distinguish a missing value from an outlier from a disordered
timestamp from a duplicate frame.
"""

from dataclasses import dataclass, field
from typing import Dict, Optional


def _reason(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"a reason must be a non-empty str, got {value!r}")
    return value


def _count(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"a count must be an int >= 1, got {value!r}")
    return value


@dataclass
class Counters:
    in_items: int = 0
    out_items: int = 0
    in_bytes: int = 0
    out_bytes: int = 0
    proc_ns: int = 0
    drops_by_reason: Dict[str, int] = field(default_factory=dict)
    upgrades_by_reason: Dict[str, int] = field(default_factory=dict)

    def observe_in(self, *, items: int, nbytes: int) -> None:
        self.in_items += items
        self.in_bytes += nbytes

    def observe_out(self, *, items: int, nbytes: int) -> None:
        self.out_items += items
        self.out_bytes += nbytes

    def observe_proc(self, *, ns: int) -> None:
        self.proc_ns += ns

    def count_drop(self, reason: object, count: object = 1) -> None:
        key = _reason(reason)
        self.drops_by_reason[key] = self.drops_by_reason.get(key, 0) + _count(count)

    def count_upgrade(self, reason: object) -> None:
        key = _reason(reason)
        self.upgrades_by_reason[key] = self.upgrades_by_reason.get(key, 0) + 1

    @property
    def total_drops(self) -> int:
        return sum(self.drops_by_reason.values())

    @property
    def total_upgrades(self) -> int:
        return sum(self.upgrades_by_reason.values())

    @property
    def byte_ratio(self) -> Optional[float]:
        return None if self.in_bytes == 0 else self.out_bytes / self.in_bytes

    @property
    def item_ratio(self) -> Optional[float]:
        return None if self.in_items == 0 else self.out_items / self.in_items

    def snapshot(self) -> dict:
        return {
            "in_items": self.in_items,
            "out_items": self.out_items,
            "in_bytes": self.in_bytes,
            "out_bytes": self.out_bytes,
            "proc_ns": self.proc_ns,
            "drops_by_reason": dict(self.drops_by_reason),
            "upgrades_by_reason": dict(self.upgrades_by_reason),
            "byte_ratio": self.byte_ratio,
            "item_ratio": self.item_ratio,
        }
```

- [ ] **Step 4: Run it to verify it passes**

Run: `cd packages/open-robot-operator && python3 -m pytest tests/test_counters.py -q`
Expected: PASS, 16 tests

- [ ] **Step 5: Write the failing derivation test**

`packages/open-robot-operator/tests/test_derive.py`:

```python
import pytest

from open_robot_operator.counters import Counters
from open_robot_operator.envelope import Header, Upgrade, derive, originate

PC = "openrobot.sensor.point_cloud/1.0.0"


def parent(**overrides):
    base = dict(
        schema=PC,
        frame_id="rslidar",
        seq=1,
        stamp_ns=1_000,
        source="lidar.front",
    )
    return originate(**{**base, **overrides})


def test_originate_builds_a_header_for_a_source_operator():
    h = parent()
    assert isinstance(h, Header)
    assert h.stamp_ns == 1_000
    assert h.source == "lidar.front"


def test_derive_restates_schema_frame_and_seq():
    out = derive([parent()], schema=PC, frame_id="base_link", seq=7)
    assert out.schema == PC
    assert out.frame_id == "base_link"
    assert out.seq == 7


def test_derive_propagates_stamp_and_source_verbatim():
    """Item 16: compression and conversion must preserve capture time and origin."""
    out = derive([parent(stamp_ns=4_242)], schema=PC, frame_id="base_link", seq=2)
    assert out.stamp_ns == 4_242
    assert out.source == "lidar.front"


def test_derive_needs_at_least_one_parent():
    with pytest.raises(ValueError):
        derive([], schema=PC, frame_id="base_link", seq=1)


def test_fusion_takes_the_oldest_capture_time():
    """A fused frame must not claim a freshness no ingredient had."""
    out = derive(
        [parent(stamp_ns=5_000, source="camera.front"), parent(stamp_ns=1_000)],
        schema="openrobot.perception.fused/1.0.0",
        frame_id="base_link",
        seq=9,
    )
    assert out.stamp_ns == 1_000


def test_fusion_joins_sources_sorted_and_deduplicated():
    out = derive(
        [parent(source="b.x"), parent(source="a.y"), parent(source="b.x")],
        schema="openrobot.perception.fused/1.0.0",
        frame_id="base_link",
        seq=1,
    )
    assert out.source == "a.y+b.x"


def test_a_single_shared_source_stays_unjoined():
    out = derive(
        [parent(stamp_ns=7_000), parent(stamp_ns=3_000)],
        schema=PC,
        frame_id="base_link",
        seq=1,
    )
    assert out.source == "lidar.front"


# --- invariant 2 -----------------------------------------------------------


def degraded(**overrides):
    return parent(validity="stale", reason="age 300ms > 200ms", **overrides)


def test_an_ok_output_from_a_degraded_input_needs_a_counted_upgrade():
    with pytest.raises(ValueError, match="invariant 2"):
        derive([degraded()], schema=PC, frame_id="base_link", seq=2)


def test_an_upgrade_is_granted_and_counted_by_the_library():
    c = Counters()
    out = derive(
        [degraded()],
        schema=PC,
        frame_id="base_link",
        seq=2,
        upgrade=Upgrade("dropped_stale", c),
    )
    assert out.validity == "ok"
    assert c.upgrades_by_reason == {"dropped_stale": 1}


def test_each_granted_upgrade_is_counted_once():
    c = Counters()
    for seq in range(3):
        derive(
            [degraded()],
            schema=PC,
            frame_id="base_link",
            seq=seq,
            upgrade=Upgrade("dropped_stale", c),
        )
    assert c.upgrades_by_reason == {"dropped_stale": 3}


def test_a_degraded_output_needs_no_upgrade():
    out = derive(
        [degraded()],
        schema=PC,
        frame_id="base_link",
        seq=2,
        validity="unpaired",
        reason="no partner within 50ms",
    )
    assert out.validity == "unpaired"


def test_non_ok_values_are_not_ordered_among_themselves():
    """A stale input may legally yield a low_confidence output."""
    out = derive(
        [degraded()],
        schema=PC,
        frame_id="base_link",
        seq=2,
        validity="low_confidence",
        reason="0.3 < 0.5 threshold",
    )
    assert out.validity == "low_confidence"


def test_an_upgrade_on_a_non_ok_output_is_rejected():
    with pytest.raises(ValueError):
        derive(
            [degraded()],
            schema=PC,
            frame_id="base_link",
            seq=2,
            validity="stale",
            reason="still stale",
            upgrade=Upgrade("pointless", Counters()),
        )


def test_an_upgrade_with_all_ok_parents_is_rejected():
    """Granting an upgrade nobody needed would inflate the counter."""
    with pytest.raises(ValueError):
        derive(
            [parent()],
            schema=PC,
            frame_id="base_link",
            seq=2,
            upgrade=Upgrade("unnecessary", Counters()),
        )


def test_one_degraded_parent_among_several_still_requires_an_upgrade():
    with pytest.raises(ValueError, match="invariant 2"):
        derive(
            [parent(), degraded(), parent()],
            schema=PC,
            frame_id="base_link",
            seq=2,
        )


def test_the_error_names_the_offending_validity_values():
    with pytest.raises(ValueError, match="stale"):
        derive([degraded()], schema=PC, frame_id="base_link", seq=2)


@pytest.mark.parametrize("bad", ["", None])
def test_an_upgrade_needs_a_reason(bad):
    with pytest.raises(ValueError):
        derive(
            [degraded()],
            schema=PC,
            frame_id="base_link",
            seq=2,
            upgrade=Upgrade(bad, Counters()),
        )


def test_a_rejected_upgrade_does_not_increment_the_counter():
    """A raise must leave the counter untouched, not half-applied."""
    c = Counters()
    with pytest.raises(ValueError):
        derive(
            [parent()],
            schema=PC,
            frame_id="base_link",
            seq=2,
            upgrade=Upgrade("unnecessary", c),
        )
    assert c.upgrades_by_reason == {}
```

- [ ] **Step 6: Run it to verify it fails**

Run: `cd packages/open-robot-operator && python3 -m pytest tests/test_derive.py -q`
Expected: collection error — `cannot import name 'Upgrade' from 'open_robot_operator.envelope'`

- [ ] **Step 7: Append the derivation API to `envelope.py`**

Add to the imports at the top of `packages/open-robot-operator/open_robot_operator/envelope.py`:

```python
from typing import Optional, Sequence
```

Then append:

```python
@dataclass(frozen=True)
class Upgrade:
    """Permission to raise a degraded input to an `ok` output.

    The library counts the upgrade itself, inside `derive()`. If the operator
    had to increment the counter, deleting that increment would be an
    undetectable mutation; here the count is a side effect of being granted
    the upgrade at all.
    """

    reason: str
    counters: "object"


def originate(
    *,
    schema: str,
    frame_id: str,
    seq: int,
    stamp_ns: int,
    source: str,
    validity: str = "ok",
    reason: Optional[str] = None,
) -> Header:
    """Build a header for a source operator, which has no parent message."""
    return Header(
        schema=schema,
        frame_id=frame_id,
        seq=seq,
        stamp_ns=stamp_ns,
        source=source,
        validity=validity,
        reason=reason,
    )


def derive(
    parents: Sequence[Header],
    *,
    schema: str,
    frame_id: str,
    seq: int,
    validity: str = "ok",
    reason: Optional[str] = None,
    upgrade: Optional[Upgrade] = None,
) -> Header:
    """Build a header from the messages that contributed to it.

    `schema`, `frame_id`, `seq`, `validity` and `reason` are restated by the
    caller. `stamp_ns` and `source` are taken from the parents: the oldest
    capture time, and the sorted set of origins.
    """
    if not parents:
        raise ValueError(
            "derive() needs at least one parent; source operators use originate()"
        )
    degraded = sorted({p.validity for p in parents if p.validity != "ok"})
    if validity == "ok":
        if degraded and upgrade is None:
            raise ValueError(
                "invariant 2: the output cannot be ok while its inputs are "
                f"{degraded} without a counted upgrade"
            )
        if upgrade is not None and not degraded:
            raise ValueError(
                "an upgrade was offered but every input is already ok"
            )
    elif upgrade is not None:
        raise ValueError("an upgrade is only meaningful when the output is ok")

    header = Header(
        schema=schema,
        frame_id=frame_id,
        seq=seq,
        stamp_ns=min(p.stamp_ns for p in parents),
        source="+".join(sorted({p.source for p in parents})),
        validity=validity,
        reason=reason,
    )
    # Count only once the header has been accepted, so a rejected derivation
    # leaves the counters untouched.
    if upgrade is not None:
        upgrade.counters.count_upgrade(upgrade.reason)
    return header
```

- [ ] **Step 8: Run it to verify it passes**

Run: `cd packages/open-robot-operator && python3 -m pytest tests/test_derive.py -q`
Expected: PASS, 19 tests

- [ ] **Step 9: Export the new names and run the whole suite**

Replace `packages/open-robot-operator/open_robot_operator/__init__.py` with:

```python
"""Operator contract for Open Robot Stack capability packs."""

__all__ = [
    "VALIDITY",
    "Counters",
    "Header",
    "Upgrade",
    "derive",
    "originate",
    "parse_ref",
    "satisfies",
]

from open_robot_operator.counters import Counters
from open_robot_operator.envelope import VALIDITY, Header, Upgrade, derive, originate
from open_robot_operator.schemaref import parse_ref, satisfies
```

Run: `cd packages/open-robot-operator && python3 -m pytest -q`
Expected: PASS, 91 tests

- [ ] **Step 10: Commit**

```bash
git add packages/open-robot-operator
git commit -m "feat(operator): header derivation, both invariants, and the counters"
```

---

## Task 4: Port declarations

**Files:**
- Create: `packages/open-robot-operator/open_robot_operator/declare.py`
- Test: `packages/open-robot-operator/tests/test_declare.py`

- [ ] **Step 1: Write the failing test**

`packages/open-robot-operator/tests/test_declare.py`:

```python
import pytest
from open_robot_operator.declare import load_operators, parse_operators

PC = "openrobot.sensor.point_cloud"


def doc(
    *,
    contract_version="1.0.0",
    name="point_cloud_filter",
    module="open_robot_dataproc.filter.point_cloud_op",
    in_schema=f"{PC}/^1.0",
    in_frame="any",
    in_extra=(),
    out_schema=f"{PC}/1.0.0",
    out_frame="same_as:cloud",
    out_frame_quoted=True,
    out_extra=(),
    outputs_empty=False,
    with_diag=False,
    diagnostics=None,
    extra_operators="",
):
    """Build an operators.yaml document. Every negative case varies one field."""
    lines = []
    if contract_version is not None:
        lines.append(f"contract_version: {contract_version}")
    lines.append("operators:")
    first = "  - "
    if name is not None:
        lines.append(f"{first}name: {name}")
        first = "    "
    if module is not None:
        lines.append(f"{first}module: {module}")
        first = "    "
    lines.append("    inputs:")
    lines.append("      cloud:")
    lines.append(f"        schema: {in_schema}")
    lines.append(f'        frame: "{in_frame}"')
    lines.extend(f"        {line}" for line in in_extra)
    if outputs_empty:
        lines.append("    outputs: {}")
    else:
        lines.append("    outputs:")
        lines.append("      cloud:")
        lines.append(f"        schema: {out_schema}")
        rendered = f'"{out_frame}"' if out_frame_quoted else out_frame
        lines.append(f"        frame: {rendered}")
        lines.extend(f"        {line}" for line in out_extra)
        if with_diag:
            lines.append("      diag:")
            lines.append("        schema: openrobot.diag.counters/1.0.0")
            lines.append('        frame: "none"')
    if with_diag and diagnostics is None:
        diagnostics = "diag"
    if diagnostics is not None:
        lines.append(f"    diagnostics: {diagnostics}")
    return "\n".join(lines) + "\n" + extra_operators


def test_a_minimal_declaration_parses():
    decls = parse_operators(doc())
    assert list(decls) == ["point_cloud_filter"]
    op = decls["point_cloud_filter"]
    assert op.module == "open_robot_dataproc.filter.point_cloud_op"
    assert op.diagnostics is None


def test_input_ports_carry_schema_frame_and_age():
    op = parse_operators(doc(in_extra=["max_age_ms: 200"]))["point_cloud_filter"]
    port = op.inputs["cloud"]
    assert port.schema_id == PC
    assert port.version_spec == "^1.0"
    assert port.frame == "any"
    assert port.max_age_ms == 200
    assert port.required is True


def test_output_ports_record_the_same_as_target():
    port = parse_operators(doc())["point_cloud_filter"].outputs["cloud"]
    assert port.frame == "same_as:cloud"
    assert port.same_as == "cloud"


def test_a_literal_frame_has_no_same_as_target():
    op = parse_operators(doc(out_frame="base_link"))["point_cloud_filter"]
    assert op.outputs["cloud"].same_as is None


def test_an_input_may_be_declared_optional():
    op = parse_operators(doc(in_extra=["required: false"]))["point_cloud_filter"]
    assert op.inputs["cloud"].required is False


def test_max_age_ms_defaults_to_none():
    op = parse_operators(doc())["point_cloud_filter"]
    assert op.inputs["cloud"].max_age_ms is None


def test_diagnostics_is_optional():
    assert parse_operators(doc())["point_cloud_filter"].diagnostics is None


@pytest.mark.parametrize(
    "kwargs,needle",
    [
        (dict(contract_version=None), "contract_version"),
        (dict(name=None), "name"),
        (dict(module=None), "module"),
    ],
)
def test_required_keys_are_enforced(kwargs, needle):
    with pytest.raises(ValueError, match=needle):
        parse_operators(doc(**kwargs))


@pytest.mark.parametrize("bad", [PC, f"{PC}/", f"{PC}/~1.0", ""])
def test_a_malformed_schema_reference_is_rejected_at_load_time(bad):
    with pytest.raises(ValueError):
        parse_operators(doc(in_schema=bad))


def test_an_output_may_not_be_declared_with_a_max_age():
    """Age is a property of what you receive, not of what you publish."""
    with pytest.raises(ValueError, match="max_age_ms"):
        parse_operators(doc(out_extra=["max_age_ms: 10"]))


@pytest.mark.parametrize("bad", [0, -1, "1.5", "true"])
def test_max_age_ms_must_be_a_positive_int(bad):
    with pytest.raises(ValueError, match="max_age_ms"):
        parse_operators(doc(in_extra=[f"max_age_ms: {bad}"]))


def test_required_must_be_a_bool():
    with pytest.raises(ValueError, match="required"):
        parse_operators(doc(in_extra=["required: yes-please"]))


def test_same_as_must_name_an_input_of_the_same_operator():
    with pytest.raises(ValueError, match="nope"):
        parse_operators(doc(out_frame="same_as:nope"))


def test_duplicate_operator_names_are_rejected():
    second = (
        "  - name: point_cloud_filter\n"
        "    module: other.module\n"
        "    inputs: {}\n"
        "    outputs:\n"
        "      cloud:\n"
        f"        schema: {PC}/1.0.0\n"
        '        frame: "base_link"\n'
    )
    with pytest.raises(ValueError, match="point_cloud_filter"):
        parse_operators(doc(extra_operators=second))


def test_an_output_must_state_a_concrete_version():
    """A consumer may say ^1.0; a producer says what it actually emits."""
    with pytest.raises(ValueError, match="concrete"):
        parse_operators(doc(out_schema=f"{PC}/^1.0"))


def test_an_input_may_not_use_same_as():
    """same_as names an input port, so it is only meaningful on an output."""
    with pytest.raises(ValueError, match="same_as"):
        parse_operators(doc(in_frame="same_as:cloud"))


def test_an_operator_with_no_outputs_is_rejected():
    with pytest.raises(ValueError, match="outputs"):
        parse_operators(doc(outputs_empty=True))


@pytest.mark.parametrize("bad", ["same_as:", ""])
def test_a_frame_must_be_a_literal_any_or_a_same_as_target(bad):
    """A bare 'same_as:' names no port, and an empty frame names nothing."""
    with pytest.raises(ValueError):
        parse_operators(doc(out_frame=bad))


@pytest.mark.parametrize("bad", ["7", "true", "[]"])
def test_a_non_string_frame_is_rejected(bad):
    """YAML would hand us an int, a bool or a list; a frame is a name."""
    with pytest.raises(ValueError):
        parse_operators(doc(out_frame=bad, out_frame_quoted=False))


def test_operators_must_be_a_non_empty_list():
    with pytest.raises(ValueError, match="operators"):
        parse_operators("contract_version: 1.0.0\noperators: []\n")


def test_the_document_must_be_a_mapping():
    with pytest.raises(ValueError, match="mapping"):
        parse_operators("- just\n- a\n- list\n")


def test_load_operators_reads_a_file(tmp_path):
    path = tmp_path / "operators.yaml"
    path.write_text(doc(), encoding="utf-8")
    assert "point_cloud_filter" in load_operators(path)


def test_diagnostics_must_name_a_declared_output_port():
    """Otherwise the field names a port nothing can wire to."""
    with pytest.raises(ValueError, match="declares no output by that name"):
        parse_operators(doc(diagnostics="diag"))


def test_diagnostics_is_accepted_when_the_output_exists():
    op = parse_operators(doc(with_diag=True))["point_cloud_filter"]
    assert op.diagnostics == "diag"
    assert "diag" in op.outputs
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd packages/open-robot-operator && python3 -m pytest tests/test_declare.py -q`
Expected: collection error — `No module named 'open_robot_operator.declare'`

- [ ] **Step 3: Write the implementation**

`packages/open-robot-operator/open_robot_operator/declare.py`:

```python
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Union

import yaml

from open_robot_operator.schemaref import parse_ref

_SAME_AS = "same_as:"


@dataclass(frozen=True)
class PortDecl:
    name: str
    schema_id: str
    version_spec: str
    frame: str
    max_age_ms: Optional[int] = None
    required: bool = True

    @property
    def same_as(self) -> Optional[str]:
        return self.frame[len(_SAME_AS):] if self.frame.startswith(_SAME_AS) else None


@dataclass(frozen=True)
class OperatorDecl:
    name: str
    module: str
    inputs: Dict[str, PortDecl]
    outputs: Dict[str, PortDecl]
    diagnostics: Optional[str] = None


def _require(mapping: dict, key: str, where: str):
    if key not in mapping:
        raise ValueError(f"{where} is missing the required key {key!r}")
    return mapping[key]


def _port(name: str, body: object, *, where: str, is_output: bool) -> PortDecl:
    if not isinstance(body, dict):
        raise ValueError(f"{where} port {name!r} must be a mapping, got {body!r}")
    schema_id, version_spec = parse_ref(_require(body, "schema", f"{where} port {name!r}"))
    frame = _require(body, "frame", f"{where} port {name!r}")
    if not isinstance(frame, str) or not frame or frame == _SAME_AS:
        raise ValueError(
            f"{where} port {name!r}: frame must be 'any', a literal name, or "
            f"'same_as:<input port>', got {frame!r}")
    if is_output and version_spec.startswith("^"):
        raise ValueError(
            f"{where} output port {name!r} declares the constraint {version_spec!r}; "
            "an output states the concrete version it produces")
    if not is_output and frame.startswith(_SAME_AS):
        raise ValueError(
            f"{where} input port {name!r} declares {frame!r}; same_as names an "
            "input port and is therefore only meaningful on an output")
    max_age_ms = body.get("max_age_ms")
    if is_output and max_age_ms is not None:
        raise ValueError(
            f"{where} output port {name!r} declares max_age_ms, which only "
            "applies to what an operator receives")
    if max_age_ms is not None and (
        isinstance(max_age_ms, bool) or not isinstance(max_age_ms, int) or max_age_ms < 1
    ):
        raise ValueError(f"{where} port {name!r}: max_age_ms must be an int >= 1, got {max_age_ms!r}")
    required = body.get("required", True)
    if not isinstance(required, bool):
        raise ValueError(f"{where} port {name!r}: required must be a bool, got {required!r}")
    return PortDecl(name=name, schema_id=schema_id, version_spec=version_spec,
                    frame=frame, max_age_ms=max_age_ms, required=required)


def parse_operators(text: str) -> Dict[str, OperatorDecl]:
    doc = yaml.safe_load(text)
    if not isinstance(doc, dict):
        raise ValueError(f"operators.yaml must be a mapping, got {type(doc).__name__}")
    _require(doc, "contract_version", "operators.yaml")
    body = _require(doc, "operators", "operators.yaml")
    if not isinstance(body, list) or not body:
        raise ValueError("operators.yaml: 'operators' must be a non-empty list")

    decls: Dict[str, OperatorDecl] = {}
    for entry in body:
        if not isinstance(entry, dict):
            raise ValueError(f"operators.yaml: each operator must be a mapping, got {entry!r}")
        name = _require(entry, "name", "an operator entry")
        where = f"operator {name!r}"
        if name in decls:
            raise ValueError(f"operators.yaml declares {name!r} more than once")
        module = _require(entry, "module", where)
        inputs = {p: _port(p, s, where=where, is_output=False)
                  for p, s in (entry.get("inputs") or {}).items()}
        raw_outputs = entry.get("outputs") or {}
        if not raw_outputs:
            raise ValueError(f"{where} declares no outputs")
        outputs = {p: _port(p, s, where=where, is_output=True) for p, s in raw_outputs.items()}
        for port in outputs.values():
            target = port.same_as
            if target is not None and target not in inputs:
                raise ValueError(
                    f"{where} output {port.name!r} says same_as:{target}, which is "
                    f"not an input of {name!r}")
        diagnostics = entry.get("diagnostics")
        if diagnostics is not None and diagnostics not in outputs:
            raise ValueError(
                f"{where} names {diagnostics!r} as its diagnostics port, but "
                f"declares no output by that name; a diagnostics port is an "
                f"ordinary output that this field merely points at")
        decls[name] = OperatorDecl(name=name, module=module, inputs=inputs,
                                   outputs=outputs, diagnostics=diagnostics)
    return decls


def load_operators(path: Union[str, Path]) -> Dict[str, OperatorDecl]:
    return parse_operators(Path(path).read_text(encoding="utf-8"))
```

- [ ] **Step 4: Run it to verify it passes**

Run: `cd packages/open-robot-operator && python3 -m pytest tests/test_declare.py -q`
Expected: PASS, 35 tests (cumulative 126)

- [ ] **Step 5: Commit**

```bash
git add packages/open-robot-operator
git commit -m "feat(operator): operators.yaml port declarations"
```

---

## Task 5: Frame resolution across the dataflow

**Files:**
- Create: `packages/open-robot-operator/open_robot_operator/resolve.py`
- Test: `packages/open-robot-operator/tests/test_resolve.py`

- [ ] **Step 1: Write the failing test**

`packages/open-robot-operator/tests/test_resolve.py`:

```python
import textwrap
import pytest
from open_robot_operator.declare import parse_operators
from open_robot_operator.resolve import Graph, resolve_frame

PC_IN = "openrobot.sensor.point_cloud/^1.0"
PC_OUT = "openrobot.sensor.point_cloud/1.0.0"

DECLS = parse_operators(
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
          - name: cleaner
            module: m.cleaner
            inputs:
              cloud:
                schema: {PC_IN}
                frame: any
            outputs:
              cloud:
                schema: {PC_OUT}
                frame: same_as:cloud
          - name: transformer
            module: m.transformer
            inputs:
              cloud:
                schema: {PC_IN}
                frame: any
            outputs:
              cloud:
                schema: {PC_OUT}
                frame: base_link
          - name: anyop
            module: m.anyop
            inputs:
              cloud:
                schema: {PC_IN}
                frame: any
            outputs:
              cloud:
                schema: {PC_OUT}
                frame: any
        """
    )
)

NODES = {"drv": "driver", "pt": "passthrough", "cl": "cleaner",
         "tf": "transformer", "an": "anyop"}
EDGES = {("pt", "cloud"): ("drv", "cloud"), ("cl", "cloud"): ("pt", "cloud"),
         ("tf", "cloud"): ("cl", "cloud"), ("an", "cloud"): ("drv", "cloud")}
GRAPH = Graph(nodes=NODES, edges=EDGES, decls=DECLS)


def test_a_literal_frame_resolves_to_itself():
    assert resolve_frame(GRAPH, "drv", "cloud") == "rslidar"

def test_same_as_follows_one_hop():
    assert resolve_frame(GRAPH, "pt", "cloud") == "rslidar"

def test_same_as_follows_a_three_hop_chain():
    assert resolve_frame(GRAPH, "cl", "cloud") == "rslidar"

def test_a_literal_output_stops_the_chain():
    assert resolve_frame(GRAPH, "tf", "cloud") == "base_link"

def test_any_resolves_to_any():
    assert resolve_frame(GRAPH, "an", "cloud") == "any"

def test_an_unwired_same_as_input_is_reported():
    graph = Graph(nodes=NODES, edges={}, decls=DECLS)
    with pytest.raises(ValueError, match="unwired"):
        resolve_frame(graph, "pt", "cloud")

def test_a_cycle_terminates_and_names_the_path():
    edges = dict(EDGES); edges[("pt", "cloud")] = ("cl", "cloud")
    graph = Graph(nodes=NODES, edges=edges, decls=DECLS)
    with pytest.raises(ValueError, match="cycle") as excinfo:
        resolve_frame(graph, "cl", "cloud")
    message = str(excinfo.value)
    assert "cl.cloud" in message and "pt.cloud" in message

def test_a_self_loop_terminates():
    edges = dict(EDGES); edges[("pt", "cloud")] = ("pt", "cloud")
    graph = Graph(nodes=NODES, edges=edges, decls=DECLS)
    with pytest.raises(ValueError, match="cycle"):
        resolve_frame(graph, "pt", "cloud")

def test_an_unknown_node_is_reported():
    with pytest.raises(ValueError, match="ghost"):
        resolve_frame(GRAPH, "ghost", "cloud")

def test_an_unknown_output_port_is_reported():
    with pytest.raises(ValueError, match="nope"):
        resolve_frame(GRAPH, "drv", "nope")

def test_a_node_bound_to_an_undeclared_operator_is_reported():
    graph = Graph(nodes={"x": "no_such_operator"}, edges={}, decls=DECLS)
    with pytest.raises(ValueError, match="no_such_operator"):
        resolve_frame(graph, "x", "cloud")
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd packages/open-robot-operator && python3 -m pytest tests/test_resolve.py -q`
Expected: collection error — `No module named 'open_robot_operator.resolve'`

- [ ] **Step 3: Write the implementation**

`packages/open-robot-operator/open_robot_operator/resolve.py`:

```python
"""Resolve a declared output frame to a concrete one.

An output declared `same_as:<input port>` inherits the frame of whatever is
wired into that input, so resolution walks the dataflow graph rather than
staying inside one operator. dora dataflows may contain cycles, so the walk
carries its visited path and reports it instead of recursing forever.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from open_robot_operator.declare import OperatorDecl

Endpoint = Tuple[str, str]


@dataclass(frozen=True)
class Graph:
    """A dataflow, reduced to what frame resolution needs.

    nodes: node id -> operator name
    edges: (node id, input port) -> (upstream node id, upstream output port)
    decls: operator name -> declaration
    """

    nodes: Dict[str, str]
    edges: Dict[Endpoint, Endpoint]
    decls: Dict[str, OperatorDecl]

    def decl_for(self, node: str) -> OperatorDecl:
        if node not in self.nodes:
            raise ValueError(f"node {node!r} is not in the dataflow")
        operator = self.nodes[node]
        if operator not in self.decls:
            raise ValueError(
                f"node {node!r} is bound to operator {operator!r}, which no "
                "operators.yaml declares"
            )
        return self.decls[operator]


def resolve_frame(
    graph: Graph, node: str, port: str, _seen: Optional[List[Endpoint]] = None
) -> str:
    """Resolve the frame published on `node`'s output `port`."""
    seen = list(_seen or [])
    here: Endpoint = (node, port)
    if here in seen:
        path = " -> ".join(f"{n}.{p}" for n, p in seen + [here])
        raise ValueError(f"frame resolution cycle: {path}")

    decl = graph.decl_for(node)
    if port not in decl.outputs:
        raise ValueError(f"operator {decl.name!r} declares no output port {port!r}")

    target = decl.outputs[port].same_as
    if target is None:
        return decl.outputs[port].frame

    upstream = graph.edges.get((node, target))
    if upstream is None:
        raise ValueError(
            f"{node}.{target} is unwired, so {node}.{port} cannot resolve "
            f"same_as:{target}"
        )
    return resolve_frame(graph, upstream[0], upstream[1], seen + [here])
```

- [ ] **Step 4: Run it to verify it passes**

Run: `cd packages/open-robot-operator && python3 -m pytest tests/test_resolve.py -q`
Expected: PASS, 11 tests (cumulative 137)

- [ ] **Step 5: Commit**

```bash
git add packages/open-robot-operator
git commit -m "feat(operator): frame resolution with cycle detection"
```

---

## Task 6: The pre-launch validator

This is the task that makes the declarations load-bearing. v1.3 §8.4 wants
"Missing requirements fail before motion", so every blocking violation makes
the command exit non-zero.

**Files:**
- Create: `packages/open-robot-operator/open_robot_operator/validate.py`
- Test: `packages/open-robot-operator/tests/test_validate.py`

- [ ] **Step 1: Write the failing test**

`packages/open-robot-operator/tests/test_validate.py`:

```python
import pytest
from open_robot_operator.declare import parse_operators
from open_robot_operator.validate import (
    Violation, load_dataflow, parse_dataflow, validate_dataflow,
)

PC = "openrobot.sensor.point_cloud"

DECLS = parse_operators(f"""
contract_version: 1.0.0
operators:
  - name: driver
    module: m.driver
    inputs: {{}}
    outputs:
      cloud:
        schema: {PC}/1.0.0
        frame: rslidar
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
      diag:
        schema: openrobot.diag.counters/1.0.0
        frame: none
    diagnostics: diag
  - name: needs_base_link
    module: m.needs
    inputs:
      cloud:
        schema: {PC}/^1.0
        frame: base_link
    outputs:
      ok:
        schema: openrobot.diag.counters/1.0.0
        frame: base_link
  - name: wants_image
    module: m.image
    inputs:
      image:
        schema: openrobot.sensor.image/^1.0
        frame: any
    outputs:
      out:
        schema: openrobot.sensor.image/1.0.0
        frame: same_as:image
  - name: wants_v2
    module: m.v2
    inputs:
      cloud:
        schema: {PC}/^2.0
        frame: any
    outputs:
      out:
        schema: {PC}/2.0.0
        frame: same_as:cloud
  - name: two_inputs
    module: m.two
    inputs:
      a:
        schema: {PC}/^1.0
        frame: any
      b:
        schema: {PC}/^1.0
        frame: any
        required: false
    outputs:
      out:
        schema: {PC}/1.0.0
        frame: same_as:a
""")


def flow(text):
    return parse_dataflow(text)


GOOD = """
nodes:
  - id: driver
    path: m.driver
    outputs: [cloud]
  - id: filt
    path: m.filt
    inputs:
      cloud: driver/cloud
    outputs: [cloud, diag]
"""


def test_a_clean_dataflow_has_no_violations():
    assert validate_dataflow(flow(GOOD), DECLS) == []


def test_nodes_bind_to_operators_by_id():
    assert flow(GOOD).nodes == {"driver": "driver", "filt": "filt"}


def test_env_operator_overrides_the_id():
    text = """
nodes:
  - id: voxel_stage
    path: m.filt
    env:
      OPERATOR: filt
    inputs:
      cloud: driver/cloud
    outputs: [cloud, diag]
  - id: driver
    path: m.driver
    outputs: [cloud]
"""
    assert flow(text).nodes["voxel_stage"] == "filt"
    assert validate_dataflow(flow(text), DECLS) == []


def checks(violations):
    return sorted(v.check for v in violations)


# --- check 1: schema ---------------------------------------------------------

def test_a_schema_id_mismatch_is_blocking():
    text = """
nodes:
  - id: driver
    path: m.driver
    outputs: [cloud]
  - id: wants_image
    path: m.image
    inputs:
      image: driver/cloud
    outputs: [out]
"""
    found = validate_dataflow(flow(text), DECLS)
    assert checks(found) == ["schema"]
    assert found[0].blocking is True
    assert "openrobot.sensor.image" in found[0].message
    assert PC in found[0].message


def test_an_unsatisfied_caret_is_blocking():
    text = """
nodes:
  - id: driver
    path: m.driver
    outputs: [cloud]
  - id: wants_v2
    path: m.v2
    inputs:
      cloud: driver/cloud
    outputs: [out]
"""
    found = validate_dataflow(flow(text), DECLS)
    assert checks(found) == ["schema"]
    assert "^2.0" in found[0].message


# --- check 2: frame ----------------------------------------------------------

def test_a_frame_mismatch_is_blocking():
    text = """
nodes:
  - id: driver
    path: m.driver
    outputs: [cloud]
  - id: needs_base_link
    path: m.needs
    inputs:
      cloud: driver/cloud
    outputs: [ok]
"""
    found = validate_dataflow(flow(text), DECLS)
    assert checks(found) == ["frame"]
    assert "base_link" in found[0].message and "rslidar" in found[0].message


def test_a_same_as_chain_satisfies_a_literal_requirement():
    """driver publishes rslidar, filt passes it through, so a consumer
    demanding rslidar is satisfied two hops away."""
    decls = parse_operators(f"""
contract_version: 1.0.0
operators:
  - name: driver
    module: m.driver
    inputs: {{}}
    outputs:
      cloud:
        schema: {PC}/1.0.0
        frame: rslidar
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
  - name: needs_rslidar
    module: m.needs
    inputs:
      cloud:
        schema: {PC}/^1.0
        frame: rslidar
    outputs:
      ok:
        schema: openrobot.diag.counters/1.0.0
        frame: rslidar
""")
    text = """
nodes:
  - id: driver
    path: m.driver
    outputs: [cloud]
  - id: filt
    path: m.filt
    inputs:
      cloud: driver/cloud
    outputs: [cloud]
  - id: needs_rslidar
    path: m.needs
    inputs:
      cloud: filt/cloud
    outputs: [ok]
"""
    found = [v for v in validate_dataflow(flow(text), decls) if v.check != "diagnostics"]
    assert found == []


def test_an_unresolvable_any_cannot_satisfy_a_literal_frame():
    decls = parse_operators(f"""
contract_version: 1.0.0
operators:
  - name: anyout
    module: m.anyout
    inputs: {{}}
    outputs:
      cloud:
        schema: {PC}/1.0.0
        frame: any
  - name: needs_base_link
    module: m.needs
    inputs:
      cloud:
        schema: {PC}/^1.0
        frame: base_link
    outputs:
      ok:
        schema: openrobot.diag.counters/1.0.0
        frame: base_link
""")
    text = """
nodes:
  - id: anyout
    path: m.anyout
    outputs: [cloud]
  - id: needs_base_link
    path: m.needs
    inputs:
      cloud: anyout/cloud
    outputs: [ok]
"""
    found = validate_dataflow(flow(text), decls)
    assert checks(found) == ["frame"]
    assert "cannot be checked before launch" in found[0].message


# --- check 3: unknown ports --------------------------------------------------

def test_a_mistyped_consumer_port_is_blocking():
    """The most common failure in dataflows of this shape."""
    text = """
nodes:
  - id: driver
    path: m.driver
    outputs: [cloud]
  - id: filt
    path: m.filt
    inputs:
      clouds: driver/cloud
    outputs: [cloud, diag]
"""
    found = validate_dataflow(flow(text), DECLS)
    assert "unknown_port" in checks(found)
    assert any("clouds" in v.message for v in found)


def test_a_mistyped_producer_port_is_blocking():
    text = """
nodes:
  - id: driver
    path: m.driver
    outputs: [cloud]
  - id: filt
    path: m.filt
    inputs:
      cloud: driver/clouds
    outputs: [cloud, diag]
"""
    found = validate_dataflow(flow(text), DECLS)
    assert "unknown_port" in checks(found)
    assert any("clouds" in v.message for v in found)


# --- check 4: unwired required inputs ----------------------------------------

def test_an_unwired_required_input_is_blocking():
    text = """
nodes:
  - id: driver
    path: m.driver
    outputs: [cloud]
  - id: filt
    path: m.filt
    outputs: [cloud, diag]
"""
    found = validate_dataflow(flow(text), DECLS)
    assert checks(found) == ["unwired_input"]
    assert found[0].port == "cloud"


def test_an_unwired_optional_input_is_not_a_violation():
    text = """
nodes:
  - id: driver
    path: m.driver
    outputs: [cloud]
  - id: two_inputs
    path: m.two
    inputs:
      a: driver/cloud
    outputs: [out]
"""
    assert validate_dataflow(flow(text), DECLS) == []


# --- check 5: diagnostics ----------------------------------------------------

def test_an_unpublished_diagnostics_port_warns_but_does_not_block():
    text = """
nodes:
  - id: driver
    path: m.driver
    outputs: [cloud]
  - id: filt
    path: m.filt
    inputs:
      cloud: driver/cloud
    outputs: [cloud]
"""
    found = validate_dataflow(flow(text), DECLS)
    assert checks(found) == ["diagnostics"]
    assert found[0].blocking is False


# --- unknown operators -------------------------------------------------------

def test_a_node_with_no_declaration_is_blocking_and_reported_once():
    text = """
nodes:
  - id: ghost
    path: m.ghost
    outputs: [cloud]
"""
    found = validate_dataflow(flow(text), DECLS)
    assert checks(found) == ["unknown_operator"]
    assert "ghost" in found[0].message


def test_an_edge_from_an_unknown_operator_does_not_double_report():
    text = """
nodes:
  - id: ghost
    path: m.ghost
    outputs: [cloud]
  - id: filt
    path: m.filt
    inputs:
      cloud: ghost/cloud
    outputs: [cloud, diag]
"""
    found = validate_dataflow(flow(text), DECLS)
    assert checks(found) == ["unknown_operator"]


# --- dataflow parsing --------------------------------------------------------

@pytest.mark.parametrize("text", [
    "nodes: []\n",
    "nodes: {}\n",
    "something: else\n",
    "- a\n- list\n",
])
def test_a_malformed_dataflow_is_rejected(text):
    with pytest.raises(ValueError):
        parse_dataflow(text)


def test_a_node_without_an_id_is_rejected():
    with pytest.raises(ValueError, match="id"):
        parse_dataflow("nodes:\n  - path: m.x\n")


def test_a_duplicate_node_id_is_rejected():
    with pytest.raises(ValueError, match="more than once"):
        parse_dataflow("nodes:\n  - id: a\n    path: x\n  - id: a\n    path: y\n")


@pytest.mark.parametrize("wire", ["driver", "''"])
def test_an_input_must_be_wired_as_node_slash_output(wire):
    text = f"nodes:\n  - id: filt\n    path: x\n    inputs:\n      cloud: {wire}\n"
    with pytest.raises(ValueError, match="<node>/<output>"):
        parse_dataflow(text)


def test_an_input_wired_to_a_missing_node_is_blocking():
    """A mistyped node name must not slip through as silently skipped edge."""
    text = """
nodes:
  - id: filt
    path: m.filt
    inputs:
      cloud: drivr/cloud
    outputs: [cloud, diag]
"""
    found = validate_dataflow(flow(text), DECLS)
    assert "unknown_node" in checks(found)
    offender = [v for v in found if v.check == "unknown_node"][0]
    assert offender.blocking is True
    assert "drivr" in offender.message


def test_a_missing_upstream_node_is_reported_once_per_edge():
    text = """
nodes:
  - id: two_inputs
    path: m.two
    inputs:
      a: ghost/cloud
      b: ghost/cloud
    outputs: [out]
"""
    found = [v for v in validate_dataflow(flow(text), DECLS) if v.check == "unknown_node"]
    assert len(found) == 2
    assert sorted(v.port for v in found) == ["a", "b"]


def test_violation_renders_with_a_severity_tag():
    assert str(Violation("schema", True, "n", "p", "boom")).startswith("ERROR [schema] n.p:")
    assert str(Violation("diagnostics", False, "n", "p", "meh")).startswith("WARN  [diagnostics] n.p:")


def test_load_dataflow_reads_a_file(tmp_path):
    path = tmp_path / "flow.yml"
    path.write_text(GOOD, encoding="utf-8")
    assert validate_dataflow(load_dataflow(path), DECLS) == []
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd packages/open-robot-operator && python3 -m pytest tests/test_validate.py -q`
Expected: collection error — `No module named 'open_robot_operator.validate'`

- [ ] **Step 3: Write the implementation**

`packages/open-robot-operator/open_robot_operator/validate.py`:

```python
"""Pre-launch validation of a dora dataflow against the port declarations.

v1.3 §8.4 requires that "Missing requirements fail before motion", so any
blocking violation makes this exit non-zero before the dataflow is started.

A node is bound to an operator by its `id`, or by `env.OPERATOR` when one
dataflow runs the same operator more than once.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import yaml

from open_robot_operator.declare import OperatorDecl, load_operators
from open_robot_operator.resolve import Graph, resolve_frame
from open_robot_operator.schemaref import satisfies

Endpoint = Tuple[str, str]


@dataclass(frozen=True)
class Violation:
    check: str
    blocking: bool
    node: str
    port: str
    message: str

    def __str__(self) -> str:
        tag = "ERROR" if self.blocking else "WARN "
        return f"{tag} [{self.check}] {self.node}.{self.port}: {self.message}"


@dataclass(frozen=True)
class Dataflow:
    """A dora dataflow reduced to node bindings and edges."""

    nodes: Dict[str, str]
    edges: Dict[Endpoint, Endpoint]
    declared_outputs: Dict[str, List[str]]


def parse_dataflow(text: str) -> Dataflow:
    doc = yaml.safe_load(text)
    if not isinstance(doc, dict) or "nodes" not in doc:
        raise ValueError("a dataflow must be a mapping with a 'nodes' key")
    entries = doc["nodes"]
    if not isinstance(entries, list) or not entries:
        raise ValueError("a dataflow needs a non-empty list of nodes")

    nodes: Dict[str, str] = {}
    edges: Dict[Endpoint, Endpoint] = {}
    declared_outputs: Dict[str, List[str]] = {}
    for entry in entries:
        if not isinstance(entry, dict) or "id" not in entry:
            raise ValueError(f"each node needs an id, got {entry!r}")
        node = entry["id"]
        if node in nodes:
            raise ValueError(f"the dataflow declares node {node!r} more than once")
        env = entry.get("env") or {}
        nodes[node] = env.get("OPERATOR", node)
        declared_outputs[node] = list(entry.get("outputs") or [])
        for port, wire in (entry.get("inputs") or {}).items():
            if not isinstance(wire, str) or "/" not in wire:
                raise ValueError(
                    f"{node}.{port} must be wired as '<node>/<output>', got {wire!r}"
                )
            upstream, upstream_port = wire.split("/", 1)
            edges[(node, port)] = (upstream, upstream_port)
    return Dataflow(nodes=nodes, edges=edges, declared_outputs=declared_outputs)


def _decl(graph: Graph, node: str) -> Optional[OperatorDecl]:
    try:
        return graph.decl_for(node)
    except ValueError:
        return None


def validate_dataflow(
    dataflow: Dataflow, decls: Dict[str, OperatorDecl]
) -> List[Violation]:
    """Run the five checks. Returns every violation found, blocking or not."""
    graph = Graph(nodes=dataflow.nodes, edges=dataflow.edges, decls=decls)
    found: List[Violation] = []

    for node, operator in dataflow.nodes.items():
        if operator not in decls:
            found.append(
                Violation(
                    "unknown_operator", True, node, "-",
                    f"bound to operator {operator!r}, which no operators.yaml declares",
                )
            )

    # checks 1-3, per edge
    for (node, port), (up_node, up_port) in sorted(dataflow.edges.items()):
        if up_node not in dataflow.nodes:
            # A mistyped node name is as common as a mistyped port name, and
            # without this the edge would be skipped without any report.
            found.append(
                Violation(
                    "unknown_node", True, node, port,
                    f"wired to {up_node}/{up_port}, but the dataflow has no node "
                    f"{up_node!r}",
                )
            )
            continue
        consumer = _decl(graph, node)
        producer = _decl(graph, up_node)
        if consumer is None or producer is None:
            continue  # already reported as unknown_operator
        if port not in consumer.inputs:
            found.append(
                Violation(
                    "unknown_port", True, node, port,
                    f"operator {consumer.name!r} declares no input port {port!r}",
                )
            )
            continue
        if up_port not in producer.outputs:
            found.append(
                Violation(
                    "unknown_port", True, node, port,
                    f"wired to {up_node}/{up_port}, but operator "
                    f"{producer.name!r} declares no output port {up_port!r}",
                )
            )
            continue

        want = consumer.inputs[port]
        give = producer.outputs[up_port]
        if want.schema_id != give.schema_id:
            found.append(
                Violation(
                    "schema", True, node, port,
                    f"expects {want.schema_id!r} but {up_node}/{up_port} "
                    f"produces {give.schema_id!r}",
                )
            )
        elif not satisfies(give.version_spec, want.version_spec):
            found.append(
                Violation(
                    "schema", True, node, port,
                    f"expects {want.schema_id}/{want.version_spec} but "
                    f"{up_node}/{up_port} produces {give.version_spec}",
                )
            )

        if want.frame != "any":
            try:
                actual = resolve_frame(graph, up_node, up_port)
            except ValueError as error:
                found.append(Violation("frame", True, node, port, str(error)))
            else:
                if actual == "any":
                    found.append(
                        Violation(
                            "frame", True, node, port,
                            f"requires frame {want.frame!r} but {up_node}/{up_port} "
                            "declares 'any', which cannot be checked before launch",
                        )
                    )
                elif actual != want.frame:
                    found.append(
                        Violation(
                            "frame", True, node, port,
                            f"requires frame {want.frame!r} but {up_node}/{up_port} "
                            f"resolves to {actual!r}",
                        )
                    )

    # check 4: required inputs must be wired
    for node, operator in sorted(dataflow.nodes.items()):
        decl = decls.get(operator)
        if decl is None:
            continue
        for port, want in sorted(decl.inputs.items()):
            if want.required and (node, port) not in dataflow.edges:
                found.append(
                    Violation(
                        "unwired_input", True, node, port,
                        f"is declared required by operator {decl.name!r} but nothing is wired to it",
                    )
                )
        # check 5: a declared diagnostics port should be published
        if decl.diagnostics and decl.diagnostics not in dataflow.declared_outputs.get(node, []):
            found.append(
                Violation(
                    "diagnostics", False, node, decl.diagnostics,
                    f"operator {decl.name!r} declares a diagnostics port that this "
                    "node does not publish; per-stage statistics will be missing",
                )
            )
    return found


def load_dataflow(path: Union[str, Path]) -> Dataflow:
    return parse_dataflow(Path(path).read_text(encoding="utf-8"))


def _collect_decls(pack_dirs) -> Dict[str, OperatorDecl]:
    merged: Dict[str, OperatorDecl] = {}
    for directory in pack_dirs:
        manifest = Path(directory) / "operators.yaml"
        if not manifest.is_file():
            raise ValueError(f"{directory} contains no operators.yaml")
        for name, decl in load_operators(manifest).items():
            if name in merged:
                raise ValueError(f"operator {name!r} is declared by two packs")
            merged[name] = decl
    return merged


def main(argv=None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog="python -m open_robot_operator.validate",
        description="Check a dora dataflow against the operator port declarations.",
    )
    parser.add_argument("dataflow", help="path to the dataflow YAML")
    parser.add_argument(
        "--pack", action="append", default=[], metavar="DIR",
        help="a capability pack directory holding operators.yaml; repeatable",
    )
    args = parser.parse_args(argv)

    packs = args.pack or sorted(str(p.parent) for p in Path("capabilities").glob("*/operators.yaml"))
    if not packs:
        print("no packs given and none found under capabilities/*/operators.yaml")
        return 2

    violations = validate_dataflow(load_dataflow(args.dataflow), _collect_decls(packs))
    for violation in violations:
        print(violation)
    blocking = [v for v in violations if v.blocking]
    if blocking:
        print(f"\n{len(blocking)} blocking violation(s); not safe to launch")
        return 1
    print(f"{args.dataflow}: OK" + (f" ({len(violations)} warning(s))" if violations else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run it to verify it passes**

Run: `cd packages/open-robot-operator && python3 -m pytest tests/test_validate.py -q`
Expected: PASS, 27 tests (cumulative 164)

- [ ] **Step 5: Exercise the command-line entry by hand**

The library is the interface the conformance tests use; the command is what a
developer runs. Check both work before trusting either.

```bash
cd packages/open-robot-operator
mkdir -p /tmp/orc-demo/pack /tmp/orc-demo/flows
cat > /tmp/orc-demo/pack/operators.yaml <<'YAML'
contract_version: 1.0.0
operators:
  - name: driver
    module: m.driver
    inputs: {}
    outputs:
      cloud:
        schema: openrobot.sensor.point_cloud/1.0.0
        frame: rslidar
  - name: filt
    module: m.filt
    inputs:
      cloud:
        schema: openrobot.sensor.point_cloud/^1.0
        frame: any
        max_age_ms: 200
    outputs:
      cloud:
        schema: openrobot.sensor.point_cloud/1.0.0
        frame: same_as:cloud
    diagnostics: diag
YAML
cat > /tmp/orc-demo/flows/bad.yml <<'YAML'
nodes:
  - id: driver
    path: m.driver
    outputs: [cloud]
  - id: filt
    path: m.filt
    inputs:
      clouds: drivr/cloud
    outputs: [cloud]
YAML
python3 -m open_robot_operator.validate /tmp/orc-demo/flows/bad.yml --pack /tmp/orc-demo/pack
echo "exit=$?"
```

Expected output, and an exit status of 1:

```text
ERROR [unknown_node] filt.clouds: wired to drivr/cloud, but the dataflow has no node 'drivr'
ERROR [unwired_input] filt.cloud: is declared required by operator 'filt' but nothing is wired to it
WARN  [diagnostics] filt.diag: operator 'filt' declares a diagnostics port that this node does not publish; per-stage statistics will be missing

2 blocking violation(s); not safe to launch
exit=1
```

Note the mistyped node name is reported instead of the mistyped port name on
the same edge: one root cause gets one message, and the unresolvable upstream
is the root cause. The `unwired_input` line is the same typo seen from the
other side.

- [ ] **Step 6: Commit**

```bash
git add packages/open-robot-operator
git commit -m "feat(operator): the pre-launch dataflow validator"
```

---

## Task 7: The wire form, sequence numbers, and the age rule

**Files:**
- Create: `packages/open-robot-operator/open_robot_operator/wire.py`
- Modify: `packages/open-robot-operator/open_robot_operator/__init__.py`
- Test: `packages/open-robot-operator/tests/test_wire.py`

- [ ] **Step 1: Write the failing test**

`packages/open-robot-operator/tests/test_wire.py`:

```python
import numpy as np
import pyarrow as pa
import pytest

from open_robot_operator.envelope import Header, originate
from open_robot_operator.wire import (
    RESERVED, SeqSource, age_ns, header_to_metadata, is_stale,
    metadata_to_header, payload_nbytes,
)

PC = "openrobot.sensor.point_cloud/1.0.0"


def head(**o):
    base = dict(schema=PC, frame_id="rslidar", seq=3, stamp_ns=1_000_000_000, source="lidar.front")
    return originate(**{**base, **o})


def test_the_reserved_key_set_is_the_header_fields():
    assert RESERVED == ("schema", "frame_id", "seq", "stamp_ns", "source", "validity", "reason")


def test_metadata_holds_only_flat_scalars():
    md = header_to_metadata(head())
    assert all(isinstance(v, (str, int, bool)) for v in md.values()), md


def test_an_ok_header_round_trips():
    h = head()
    assert metadata_to_header(header_to_metadata(h)) == h


def test_a_degraded_header_round_trips_with_its_reason():
    h = head(validity="stale", reason="age 300ms > 200ms")
    back = metadata_to_header(header_to_metadata(h))
    assert back == h
    assert back.reason == "age 300ms > 200ms"


def test_reason_is_omitted_rather_than_sent_as_none():
    """dora metadata carries scalars and has no null."""
    assert "reason" not in header_to_metadata(head())


def test_a_missing_reason_reads_back_as_none():
    md = header_to_metadata(head())
    assert metadata_to_header(md).reason is None


def test_extras_pass_through():
    md = header_to_metadata(head(), encoding="jointstate", success=True)
    assert md["encoding"] == "jointstate"
    assert md["success"] is True
    assert metadata_to_header(md) == head()


@pytest.mark.parametrize("key", RESERVED)
def test_extras_may_not_shadow_a_reserved_key(key):
    with pytest.raises(ValueError, match="reserved"):
        header_to_metadata(head(), **{key: "hijacked"})


@pytest.mark.parametrize("drop", [k for k in RESERVED if k != "reason"])
def test_a_header_missing_any_required_key_is_rejected(drop):
    md = header_to_metadata(head())
    del md[drop]
    with pytest.raises(ValueError, match=drop):
        metadata_to_header(md)


def test_the_error_points_at_the_upstream_node():
    with pytest.raises(ValueError, match="header_to_metadata"):
        metadata_to_header({"encoding": "jointstate"})


@pytest.mark.parametrize("bad", [None, [], "schema", 7])
def test_non_mapping_metadata_is_rejected(bad):
    with pytest.raises(ValueError):
        metadata_to_header(bad)


def test_a_corrupt_value_is_caught_by_the_header_rules():
    md = header_to_metadata(head())
    md["stamp_ns"] = 0
    with pytest.raises(ValueError, match="stamp_ns"):
        metadata_to_header(md)


# --- sequence numbers --------------------------------------------------------

def test_sequence_numbers_start_at_zero_and_increase():
    seq = SeqSource()
    assert [seq.take() for _ in range(4)] == [0, 1, 2, 3]


def test_each_port_keeps_its_own_sequence():
    a, b = SeqSource(), SeqSource()
    a.take(); a.take()
    assert b.take() == 0


# --- the same-host age rule --------------------------------------------------

def test_age_is_now_minus_capture():
    assert age_ns(head(stamp_ns=1_000), now_ns=1_500) == 500


def test_a_port_with_no_limit_is_never_stale():
    assert is_stale(head(stamp_ns=1), None, now_ns=10**18) is False


def test_staleness_compares_against_the_declared_limit():
    h = head(stamp_ns=1_000_000_000)
    at_199ms = 1_000_000_000 + 199_000_000
    at_201ms = 1_000_000_000 + 201_000_000
    assert is_stale(h, 200, now_ns=at_199ms) is False
    assert is_stale(h, 200, now_ns=at_201ms) is True


def test_exactly_at_the_limit_is_not_yet_stale():
    """The boundary is inclusive, so a 200ms budget tolerates exactly 200ms."""
    h = head(stamp_ns=1_000_000_000)
    assert is_stale(h, 200, now_ns=1_000_000_000 + 200_000_000) is False


def test_a_capture_from_the_future_is_not_stale():
    assert is_stale(head(stamp_ns=2_000), 200, now_ns=1_000) is False


def test_age_uses_the_wall_clock_when_no_now_is_given():
    assert age_ns(head(stamp_ns=1)) > 0


# --- payload sizing ----------------------------------------------------------

def test_arrow_arrays_are_sized():
    array = pa.array(np.zeros(100, dtype=np.float32))
    assert payload_nbytes(array) == array.nbytes


def test_numpy_arrays_are_sized():
    assert payload_nbytes(np.zeros(10, dtype=np.float64)) == 80


def test_bytes_are_sized():
    assert payload_nbytes(b"abcd") == 4


def test_none_sizes_to_zero():
    assert payload_nbytes(None) == 0


def test_an_unsizable_payload_raises():
    with pytest.raises(TypeError):
        payload_nbytes({"not": "sizable"})


def test_the_module_does_not_import_dora():
    """Operators must stay testable on a host without the runtime installed.

    This walks the AST rather than grepping the source: a substring scan
    cannot tell a real import from the word appearing in a docstring, which
    is how the equivalent check went wrong once already.
    """
    import ast
    import pathlib

    import open_robot_operator.wire as wire

    tree = ast.parse(pathlib.Path(wire.__file__).read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert "dora" not in imported, f"wire.py imports {sorted(imported)}"


def test_the_ast_scan_would_catch_a_real_import(tmp_path):
    """Pin the scan itself: it must fail on an import and pass on a mention."""
    import ast

    def imports(source):
        found = set()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Import):
                found.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                found.add(node.module.split(".")[0])
        return found

    assert "dora" in imports("import dora\n")
    assert "dora" in imports("from dora import Node\n")
    assert "dora" not in imports('"""Operators import dora inside main()."""\n')
    assert "dora" not in imports('# import dora would go here\n')


# --- runtime frame resolution ------------------------------------------------

def test_output_frame_returns_a_literal_unchanged():
    from open_robot_operator.wire import output_frame
    assert output_frame("base_link", {"cloud": head()}) == "base_link"


def test_output_frame_follows_same_as_to_the_named_port():
    from open_robot_operator.wire import output_frame
    parents = {"cloud": head(frame_id="rslidar"), "other": head(frame_id="camera_front")}
    assert output_frame("same_as:cloud", parents) == "rslidar"
    assert output_frame("same_as:other", parents) == "camera_front"


def test_output_frame_ignores_the_inbound_frame_when_a_literal_is_declared():
    """The mutation this pins: publishing the input's frame where the
    declaration names a literal one."""
    from open_robot_operator.wire import output_frame
    assert output_frame("base_link", {"cloud": head(frame_id="rslidar")}) == "base_link"


def test_output_frame_reports_a_same_as_port_that_received_nothing():
    from open_robot_operator.wire import output_frame
    with pytest.raises(ValueError, match="no header was received"):
        output_frame("same_as:cloud", {"other": head()})


def test_output_frame_rejects_a_bare_same_as():
    from open_robot_operator.wire import output_frame
    with pytest.raises(ValueError, match="names no input port"):
        output_frame("same_as:", {"cloud": head()})


def test_output_frame_refuses_to_publish_any():
    from open_robot_operator.wire import output_frame
    with pytest.raises(ValueError, match="none"):
        output_frame("any", {"cloud": head()})


@pytest.mark.parametrize("bad", ["", None, 7])
def test_output_frame_rejects_a_malformed_declaration(bad):
    from open_robot_operator.wire import output_frame
    with pytest.raises(ValueError):
        output_frame(bad, {"cloud": head()})


def test_none_is_publishable_for_a_frameless_payload():
    from open_robot_operator.wire import output_frame
    assert output_frame("none", {}) == "none"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd packages/open-robot-operator && python3 -m pytest tests/test_wire.py -q`
Expected: collection error — `No module named 'open_robot_operator.wire'`

- [ ] **Step 3: Write the implementation**

`packages/open-robot-operator/open_robot_operator/wire.py`:

```python
"""Carrying the header on the wire, and reading it back.

The header travels as flat scalars in dora metadata while the payload stays in
the arrow array. Flat is not a preference: every metadata value in the
existing dora-nav and dora-moveit2 nodes is a str, bool or int, and nested
dicts are not known to survive. The ROS 2 `{sec, nanosec}` split therefore
happens in the format-conversion operator, not here.

`dora` is never imported by this module. Operators import it inside `main()`
so that their pure functions remain testable on a host without the runtime.
"""

import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

from open_robot_operator.envelope import Header

RESERVED = ("schema", "frame_id", "seq", "stamp_ns", "source", "validity", "reason")


def header_to_metadata(header: Header, **extras: Any) -> Dict[str, Any]:
    """Flatten a header into dora metadata.

    `reason` is omitted when it is None, because dora metadata carries scalars
    and has no null. Extras such as the pre-existing `encoding` key are passed
    through untouched, but may not shadow a reserved name.
    """
    collisions = sorted(set(extras) & set(RESERVED))
    if collisions:
        raise ValueError(f"extras may not shadow reserved header keys: {collisions}")
    metadata: Dict[str, Any] = {
        "schema": header.schema,
        "frame_id": header.frame_id,
        "seq": header.seq,
        "stamp_ns": header.stamp_ns,
        "source": header.source,
        "validity": header.validity,
    }
    if header.reason is not None:
        metadata["reason"] = header.reason
    metadata.update(extras)
    return metadata


def metadata_to_header(metadata: Optional[Dict[str, Any]]) -> Header:
    """Read a header back out of dora metadata."""
    if not isinstance(metadata, dict):
        raise ValueError(f"metadata must be a mapping, got {metadata!r}")
    missing = [k for k in RESERVED if k != "reason" and k not in metadata]
    if missing:
        raise ValueError(
            f"metadata carries no contract header; missing {missing}. An upstream "
            "node is publishing without open_robot_operator.wire.header_to_metadata"
        )
    return Header(
        schema=metadata["schema"],
        frame_id=metadata["frame_id"],
        seq=metadata["seq"],
        stamp_ns=metadata["stamp_ns"],
        source=metadata["source"],
        validity=metadata["validity"],
        reason=metadata.get("reason"),
    )


@dataclass
class SeqSource:
    """Monotonic sequence numbers for one output port.

    A gap in `seq` reveals messages lost on the edge between two adjacent
    operators. It is not a duplicate-detection key: every producer restates it,
    so a duplicated capture arrives with a fresh number. Duplicates are found
    by `stamp_ns` paired with `source`.
    """

    _next: int = 0

    def take(self) -> int:
        value = self._next
        self._next += 1
        return value


def age_ns(header: Header, now_ns: Optional[int] = None) -> int:
    """How old the capture is, by the local clock.

    Well-defined only when capture and consumption happen on the same host;
    cross-host staleness needs a two-sided age rule and is out of scope.
    """
    now = time.time_ns() if now_ns is None else now_ns
    return now - header.stamp_ns


def is_stale(header: Header, max_age_ms: Optional[int], now_ns: Optional[int] = None) -> bool:
    """Is this message older than its port allows? A port with no limit never is."""
    if max_age_ms is None:
        return False
    return age_ns(header, now_ns) > max_age_ms * 1_000_000


def payload_nbytes(payload: Any) -> int:
    """Size a payload for the counters, for arrow arrays, numpy arrays or bytes."""
    if payload is None:
        return 0
    for attr in ("nbytes",):
        if hasattr(payload, attr):
            return int(getattr(payload, attr))
    if isinstance(payload, (bytes, bytearray, memoryview)):
        return len(payload)
    raise TypeError(f"cannot size a payload of type {type(payload).__name__}")


SAME_AS = "same_as:"


def output_frame(declared: str, parents: Dict[str, Header]) -> str:
    """Resolve a declared output frame at run time.

    The declaration is the authority, not the inbound metadata. Under
    `same_as:<port>` the result does equal that input's frame, but it is
    reached by looking up the named port, so an output declared with a literal
    frame can never accidentally publish its input's frame instead.

    `parents` maps input port name to the header received on it.
    """
    if not isinstance(declared, str) or not declared:
        raise ValueError(f"a declared frame must be a non-empty str, got {declared!r}")
    if declared.startswith(SAME_AS):
        port = declared[len(SAME_AS):]
        if not port:
            raise ValueError("same_as names no input port")
        if port not in parents:
            raise ValueError(
                f"the declaration says {declared!r} but no header was received on "
                f"input port {port!r}; available: {sorted(parents)}"
            )
        return parents[port].frame_id
    if declared == "any":
        raise ValueError(
            "an output declared 'any' has no frame to publish; declare a literal "
            "frame, or 'none' for a payload with no spatial meaning such as "
            "diagnostic counters"
        )
    return declared
```

- [ ] **Step 4: Run it to verify it passes**

Run: `cd packages/open-robot-operator && python3 -m pytest tests/test_wire.py -q`
Expected: PASS, 51 tests

- [ ] **Step 5: Export the wire API**

Replace `packages/open-robot-operator/open_robot_operator/__init__.py` with:

```python
"""Operator contract for Open Robot Stack capability packs."""

__all__ = [
    "RESERVED",
    "SAME_AS",
    "VALIDITY",
    "Counters",
    "Header",
    "SeqSource",
    "Upgrade",
    "age_ns",
    "derive",
    "header_to_metadata",
    "is_stale",
    "metadata_to_header",
    "originate",
    "output_frame",
    "parse_ref",
    "payload_nbytes",
    "satisfies",
]

from open_robot_operator.counters import Counters
from open_robot_operator.envelope import VALIDITY, Header, Upgrade, derive, originate
from open_robot_operator.schemaref import parse_ref, satisfies
from open_robot_operator.wire import (
    RESERVED,
    SAME_AS,
    SeqSource,
    age_ns,
    header_to_metadata,
    is_stale,
    metadata_to_header,
    output_frame,
    payload_nbytes,
)
```

- [ ] **Step 6: Run the whole suite**

Run: `cd packages/open-robot-operator && python3 -m pytest -q`
Expected: PASS, 215 tests

- [ ] **Step 7: Commit**

```bash
git add packages/open-robot-operator
git commit -m "feat(operator): the wire form, sequence numbers, and the age rule"
```

---

## Task 8: The normative artifacts

These are the artifacts contract items 13, 14 and 16 name by hand: the
data-structure description, the frame dictionary and the unit dictionary. The
tests keep the dictionaries consistent with each other, which is what actually
drifts in practice; nothing here validates payloads per frame.

**Files:**
- Create: `specs/operators/units.yaml`, `specs/operators/frames.yaml`
- Create: `specs/operators/schemas/_meta.schema.json` and eight payload schemas
- Test: `tests/test_specs.py`
- [ ] **Step 1: Write the unit dictionary**

`specs/operators/units.yaml`:

```yaml
# Unit dictionary. Contract item 14 promises a 端口与坐标系字典; this is its
# unit half. Units are declared here and referenced from a payload schema's
# fields, never carried per message -- a message states only its schema id and
# version, and the schema fixes the units for every field in it.
#
# Symbols are ASCII so they survive every transport and editor in the fleet.
contract_version: 1.0.0
units:
  - symbol: m
    quantity: length
    description: metre
  - symbol: rad
    quantity: angle
    description: radian, and quaternion components are dimensionless
  - symbol: m/s
    quantity: linear_velocity
    description: metre per second
  - symbol: rad/s
    quantity: angular_velocity
    description: radian per second
  - symbol: m/s^2
    quantity: linear_acceleration
    description: metre per second squared
  - symbol: rad/s^2
    quantity: angular_acceleration
    description: radian per second squared
  - symbol: N
    quantity: force
    description: newton
  - symbol: N*m
    quantity: torque
    description: newton metre
  - symbol: s
    quantity: time
    description: second
  - symbol: ns
    quantity: time
    description: nanosecond, the unit of stamp_ns
  - symbol: count
    quantity: cardinality
    description: a non-negative integer tally
  - symbol: byte
    quantity: data_size
    description: one octet
  - symbol: ratio
    quantity: dimensionless
    description: a bounded fraction, normally 0.0 to 1.0
  - symbol: dimensionless
    quantity: dimensionless
    description: a pure number with no unit, such as an intensity or a class id
```
- [ ] **Step 2: Write the frame dictionary**

`specs/operators/frames.yaml`:

```yaml
# Frame dictionary. The other half of contract item 14's 端口与坐标系字典.
#
# The `parent` field is documentation for integrators: it records the tree the
# fleet intends. The contract layer NEVER transforms between frames. It checks
# that a producer's declared frame matches what the consumer requires, and a
# mismatch is a blocking violation rather than an implicit conversion.
# Transformation is the business of the perception and control operators.
contract_version: 1.0.0
frames:
  - name: none
    parent: null
    description: >-
      No spatial meaning. For payloads that are not in any frame, such as the
      diagnostic counters. A Header still needs a frame_id, so frame-less
      payloads name this one rather than leaving it blank or using 'any'.
  - name: map
    parent: null
    description: The fixed world frame a map is expressed in.
  - name: odom
    parent: map
    description: Continuous odometric frame; drifts, never jumps.
  - name: base_link
    parent: odom
    description: Robot body frame, origin at the chassis centre, x forward, y left, z up.
  - name: rslidar
    parent: base_link
    description: Mechanical lidar frame as mounted; the name matches the existing dora-nav nodes.
  - name: camera_front
    parent: base_link
    description: Front camera optical frame, z along the optical axis.
  - name: imu_link
    parent: base_link
    description: IMU frame, axes as mounted.
  - name: tool0
    parent: base_link
    description: Manipulator flange frame, for the control operators' IK and force ports.
```
- [ ] **Step 3: Write the meta-schema**

`specs/operators/schemas/_meta.schema.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "openrobot.operator.payload-schema/1.0.0",
  "title": "Meta-schema for operator payload schemas",
  "description": "A payload schema is descriptive, not a per-frame validator: the pre-launch check already reconciled schemas, and validating a point cloud per frame at 30 Hz is not acceptable. It fixes the field order, the arrow encoding and the unit of every field.",
  "type": "object",
  "additionalProperties": false,
  "required": ["id", "version", "title", "description", "payload"],
  "properties": {
    "id": {"type": "string", "pattern": "^[a-z0-9_]+(\\.[a-z0-9_]+)*$"},
    "version": {"type": "string", "pattern": "^\\d+\\.\\d+\\.\\d+$"},
    "title": {"type": "string", "minLength": 1},
    "description": {"type": "string", "minLength": 1},
    "payload": {
      "type": "object",
      "additionalProperties": false,
      "required": ["encoding", "fields"],
      "properties": {
        "encoding": {
          "type": "string",
          "enum": ["arrow.float32.flat", "arrow.float64.flat", "arrow.uint8.flat", "arrow.uint8.blob"]
        },
        "item_step": {"type": "integer", "minimum": 1},
        "fields": {
          "type": "array",
          "minItems": 1,
          "items": {
            "type": "object",
            "additionalProperties": false,
            "required": ["name", "unit", "description"],
            "properties": {
              "name": {"type": "string", "pattern": "^[a-z0-9_]+$"},
              "unit": {"type": "string", "minLength": 1},
              "description": {"type": "string", "minLength": 1}
            }
          }
        }
      }
    }
  }
}
```
- [ ] **Step 4: Write `openrobot.diag.chain_report-1.0.0.json`**

`specs/operators/schemas/openrobot.diag.chain_report-1.0.0.json`:

```json
{
  "id": "openrobot.diag.chain_report",
  "version": "1.0.0",
  "title": "Chain diagnostic report",
  "description": "The combined per-stage statistics for one preprocessing chain, as UTF-8 JSON in a uint8 arrow array: the chain_report mapping from open_robot_dataproc.tools.diag_collector. It is separate from a single operator's counters because the chain ratio is a product across stages and has no meaning for one stage alone.",
  "payload": {
    "encoding": "arrow.uint8.blob",
    "fields": [
      {"name": "json", "unit": "byte", "description": "UTF-8 JSON with stages, chain_byte_ratio, chain_item_ratio, chain_byte_reduction, total_proc_ns, drops_by_stage, upgrades_by_stage and total_drops."}
    ]
  }
}
```
- [ ] **Step 5: Write `openrobot.diag.counters-1.0.0.json`**

`specs/operators/schemas/openrobot.diag.counters-1.0.0.json`:

```json
{
  "id": "openrobot.diag.counters",
  "version": "1.0.0",
  "title": "Diagnostic counters",
  "description": "One operator's rolling counters, serialised as UTF-8 JSON in a uint8 arrow array: the snapshot() mapping from open_robot_operator.counters. The chain reduction ratio of contract item 16 is the product of the per-stage ratios collected from these, which is why no per-message correlation exists.",
  "payload": {
    "encoding": "arrow.uint8.blob",
    "fields": [
      {"name": "json", "unit": "byte", "description": "UTF-8 JSON holding in_items, out_items, in_bytes, out_bytes, proc_ns, drops_by_reason, upgrades_by_reason, byte_ratio and item_ratio."}
    ]
  }
}
```
- [ ] **Step 6: Write `openrobot.interop.ros2_message-1.0.0.json`**

`specs/operators/schemas/openrobot.interop.ros2_message-1.0.0.json`:

```json
{
  "id": "openrobot.interop.ros2_message",
  "version": "1.0.0",
  "title": "ROS 2 message",
  "description": "A ROS 2 message rendered as UTF-8 JSON in a uint8 arrow array: a standard header holding frame_id and a sec/nanosec stamp, a contract block holding the envelope fields ROS 2 has no home for, and the data. A plain ROS 2 subscriber reads header and data and ignores the contract block.",
  "payload": {
    "encoding": "arrow.uint8.blob",
    "fields": [
      {"name": "json", "unit": "byte", "description": "UTF-8 JSON with the keys header, contract and data, plus any message-specific extras such as height or point_step."}
    ]
  }
}
```
- [ ] **Step 7: Write `openrobot.sensor.image-1.0.0.json`**

`specs/operators/schemas/openrobot.sensor.image-1.0.0.json`:

```json
{
  "id": "openrobot.sensor.image",
  "version": "1.0.0",
  "title": "Image",
  "description": "A uint8 arrow array holding height*width*channels samples in row-major order, with the geometry carried as metadata extras named height, width and channels. Encoded files are a separate schema, openrobot.sensor.image_compressed, so that the two cannot be wired interchangeably.",
  "payload": {
    "encoding": "arrow.uint8.flat",
    "fields": [
      {
        "name": "sample",
        "unit": "dimensionless",
        "description": "One 8-bit channel sample; interleaved across channels within a pixel."
      }
    ]
  }
}
```
- [ ] **Step 8: Write `openrobot.sensor.image_compressed-1.0.0.json`**

`specs/operators/schemas/openrobot.sensor.image_compressed-1.0.0.json`:

```json
{
  "id": "openrobot.sensor.image_compressed",
  "version": "1.0.0",
  "title": "Compressed image",
  "description": "An encoded image file in a uint8 arrow array, JPEG when lossy and PNG when lossless. Separate from the raw image schema because the payload layout is a file rather than samples, so mixing the two is caught before launch. The metadata extras carry codec, lossy, height, width and channels.",
  "payload": {
    "encoding": "arrow.uint8.blob",
    "fields": [
      {"name": "blob", "unit": "byte", "description": "A complete JPEG or PNG file as produced by Pillow."}
    ]
  }
}
```
- [ ] **Step 9: Write `openrobot.sensor.point_cloud-1.0.0.json`**

`specs/operators/schemas/openrobot.sensor.point_cloud-1.0.0.json`:

```json
{
  "id": "openrobot.sensor.point_cloud",
  "version": "1.0.0",
  "title": "Point cloud",
  "description": "A flat float32 arrow array holding item_step values per point in the declared field order. Flat rather than a struct array because it is cheaper and matches the existing pa.array(np.array(...), type=pa.float32()) idiom in dora-nav and dora-moveit2.",
  "payload": {
    "encoding": "arrow.float32.flat",
    "item_step": 4,
    "fields": [
      {"name": "x", "unit": "m", "description": "Along the frame's x axis."},
      {"name": "y", "unit": "m", "description": "Along the frame's y axis."},
      {"name": "z", "unit": "m", "description": "Along the frame's z axis."},
      {"name": "intensity", "unit": "dimensionless", "description": "Sensor return strength, uncalibrated and sensor-specific."}
    ]
  }
}
```
- [ ] **Step 10: Write `openrobot.sensor.point_cloud_compressed-1.0.0.json`**

`specs/operators/schemas/openrobot.sensor.point_cloud_compressed-1.0.0.json`:

```json
{
  "id": "openrobot.sensor.point_cloud_compressed",
  "version": "1.0.0",
  "title": "Compressed point cloud",
  "description": "A zstd blob in a uint8 arrow array, holding either float32 points or int32 quantised ones. It is a separate schema from the uncompressed cloud rather than another version of it, so that wiring a compressed stream into an operator expecting raw points is a blocking pre-launch violation instead of a run-time crash. The metadata extras carry lossy, shape and, when lossy, precision.",
  "payload": {
    "encoding": "arrow.uint8.blob",
    "fields": [
      {"name": "blob", "unit": "byte", "description": "zstd frame; decompresses to float32 points, or to int32 quanta that multiply back by precision."}
    ]
  }
}
```
- [ ] **Step 11: Write `openrobot.state.vector-1.0.0.json`**

`specs/operators/schemas/openrobot.state.vector-1.0.0.json`:

```json
{
  "id": "openrobot.state.vector",
  "version": "1.0.0",
  "title": "State vector",
  "description": "A flat float64 arrow array of named scalars in the declared field order, used for the filtered state quantities the control operators consume. A state vector has no spatial extent, which is why state filtering offers temporal modes only.",
  "payload": {
    "encoding": "arrow.float64.flat",
    "item_step": 1,
    "fields": [
      {"name": "value", "unit": "dimensionless", "description": "One scalar. The concrete quantity and unit are fixed by the port's own documentation, because a state vector carries whatever the port declares."}
    ]
  }
}
```
- [ ] **Step 12: Write the consistency tests**

`tests/test_specs.py`:

```python
"""Keep the normative artifacts consistent with each other.

These are the artifacts contract items 13, 14 and 16 name: the data-structure
description, the frame dictionary and the unit dictionary. Nothing validates
payloads per frame here -- this checks that the dictionaries agree, which is
what drifts in practice.
"""

import json
import re
from pathlib import Path

import jsonschema
import pytest
import yaml

SPECS = Path(__file__).resolve().parents[1] / "specs" / "operators"
SCHEMA_DIR = SPECS / "schemas"
META = json.loads((SCHEMA_DIR / "_meta.schema.json").read_text(encoding="utf-8"))

SCHEMA_FILES = sorted(p for p in SCHEMA_DIR.glob("*.json") if not p.name.startswith("_"))
UNITS = yaml.safe_load((SPECS / "units.yaml").read_text(encoding="utf-8"))
FRAMES = yaml.safe_load((SPECS / "frames.yaml").read_text(encoding="utf-8"))


def test_the_expected_schemas_are_present():
    assert [p.name for p in SCHEMA_FILES] == [
        "openrobot.diag.chain_report-1.0.0.json",
        "openrobot.diag.counters-1.0.0.json",
        "openrobot.interop.ros2_message-1.0.0.json",
        "openrobot.sensor.image-1.0.0.json",
        "openrobot.sensor.image_compressed-1.0.0.json",
        "openrobot.sensor.point_cloud-1.0.0.json",
        "openrobot.sensor.point_cloud_compressed-1.0.0.json",
        "openrobot.state.vector-1.0.0.json",
    ]


def test_a_compressed_payload_is_its_own_schema_not_a_version():
    """Wiring a compressed stream into an operator expecting raw samples must
    be a blocking pre-launch violation, which needs distinct ids."""
    ids = {json.loads(p.read_text(encoding="utf-8"))["id"] for p in SCHEMA_FILES}
    for raw in ("openrobot.sensor.point_cloud", "openrobot.sensor.image"):
        assert raw in ids
        assert f"{raw}_compressed" in ids


def test_a_blob_schema_declares_a_blob_encoding():
    for path in SCHEMA_FILES:
        doc = json.loads(path.read_text(encoding="utf-8"))
        if doc["id"].endswith("_compressed") or doc["id"].startswith("openrobot.diag.") \
                or doc["id"] == "openrobot.interop.ros2_message":
            assert doc["payload"]["encoding"] == "arrow.uint8.blob", doc["id"]


@pytest.mark.parametrize("path", SCHEMA_FILES, ids=lambda p: p.name)
def test_every_schema_satisfies_the_meta_schema(path):
    jsonschema.validate(json.loads(path.read_text(encoding="utf-8")), META)


@pytest.mark.parametrize("path", SCHEMA_FILES, ids=lambda p: p.name)
def test_the_filename_matches_the_id_and_version(path):
    doc = json.loads(path.read_text(encoding="utf-8"))
    assert path.name == f"{doc['id']}-{doc['version']}.json"


@pytest.mark.parametrize("path", SCHEMA_FILES, ids=lambda p: p.name)
def test_every_field_unit_is_in_the_unit_dictionary(path):
    known = {u["symbol"] for u in UNITS["units"]}
    doc = json.loads(path.read_text(encoding="utf-8"))
    for field in doc["payload"]["fields"]:
        assert field["unit"] in known, f"{path.name}: unknown unit {field['unit']!r}"


@pytest.mark.parametrize("path", SCHEMA_FILES, ids=lambda p: p.name)
def test_field_names_are_unique_within_a_schema(path):
    doc = json.loads(path.read_text(encoding="utf-8"))
    names = [f["name"] for f in doc["payload"]["fields"]]
    assert len(names) == len(set(names))


@pytest.mark.parametrize("path", SCHEMA_FILES, ids=lambda p: p.name)
def test_a_flat_encoding_declares_its_item_step(path):
    doc = json.loads(path.read_text(encoding="utf-8"))
    payload = doc["payload"]
    if payload["encoding"].endswith(".flat") and payload["encoding"] != "arrow.uint8.flat":
        assert "item_step" in payload, f"{path.name} is flat but declares no item_step"
        assert payload["item_step"] == len(payload["fields"])


def test_unit_symbols_are_unique():
    symbols = [u["symbol"] for u in UNITS["units"]]
    assert len(symbols) == len(set(symbols))


def test_unit_symbols_are_ascii():
    """They have to survive every transport and editor in the fleet."""
    for unit in UNITS["units"]:
        unit["symbol"].encode("ascii")


def test_the_units_item_14_names_are_all_present():
    """Item 14 promises 统一位置、姿态、速度与力的单位."""
    symbols = {u["symbol"] for u in UNITS["units"]}
    assert {"m", "rad", "m/s", "rad/s", "N", "N*m"} <= symbols


def test_frame_names_are_unique():
    names = [f["name"] for f in FRAMES["frames"]]
    assert len(names) == len(set(names))


def test_every_frame_parent_is_a_known_frame_or_null():
    names = {f["name"] for f in FRAMES["frames"]}
    for frame in FRAMES["frames"]:
        parent = frame["parent"]
        assert parent is None or parent in names, f"{frame['name']} -> {parent!r}"


def test_the_spatial_tree_has_exactly_one_root():
    """'none' is a sentinel for frame-less payloads, not a spatial root."""
    roots = [
        f["name"] for f in FRAMES["frames"]
        if f["parent"] is None and f["name"] != "none"
    ]
    assert roots == ["map"]


def test_the_frame_less_sentinel_exists():
    """A Header needs a frame_id, so a counters payload needs a name for
    'not in any frame' rather than a blank or 'any'."""
    assert "none" in {f["name"] for f in FRAMES["frames"]}


def test_the_frame_tree_has_no_cycle():
    parents = {f["name"]: f["parent"] for f in FRAMES["frames"]}
    for start in parents:
        seen, node = [], start
        while node is not None:
            assert node not in seen, f"cycle through {node!r}: {seen}"
            seen.append(node)
            node = parents[node]


@pytest.mark.parametrize("name", ["base_link", "rslidar", "tool0", "map", "odom"])
def test_the_frames_the_operators_reference_are_declared(name):
    assert name in {f["name"] for f in FRAMES["frames"]}


@pytest.mark.parametrize("doc", [UNITS, FRAMES], ids=["units", "frames"])
def test_each_dictionary_declares_a_contract_version(doc):
    assert re.fullmatch(r"\d+\.\d+\.\d+", str(doc["contract_version"]))


@pytest.mark.parametrize("path", SCHEMA_FILES, ids=lambda p: p.name)
def test_every_description_is_a_sentence_not_a_placeholder(path):
    doc = json.loads(path.read_text(encoding="utf-8"))
    texts = [doc["description"]] + [f["description"] for f in doc["payload"]["fields"]]
    for text in texts:
        assert len(text) > 20, f"{path.name}: {text!r} is too short to be a description"
        assert not re.search(r"\bTBD\b|\bTODO\b", text)
```
- [ ] **Step 13: Run them**

Run: `python3 -m pytest tests/test_specs.py -q`
Expected: PASS, 66 tests

There are eight payload schemas, not the four an early draft of the design
assumed, and the reason matters. A compressed payload is a different layout
from the samples it came from, so `point_cloud_compressed` and
`image_compressed` are separate ids rather than later versions of the raw
ones; that way wiring a compressed stream into an operator expecting raw
points is a blocking pre-launch violation instead of a run-time crash. The
codec needs `interop.ros2_message`, and the collector's chain report is a
product across stages with no meaning for a single stage, so it is separate
from one operator's `diag.counters`.

- [ ] **Step 14: Commit**

```bash
git add specs/operators tests/test_specs.py
git commit -m "feat(specs): the operator contract's frame, unit and payload dictionaries"
```

---

## Task 9: The data-processing pack skeleton and its manifests

**Files:**
- Create: `capabilities/data-processing/pyproject.toml`, `conftest.py`
- Create: `capabilities/data-processing/open_robot_dataproc/` package markers
- Create: `capabilities/data-processing/pack.yaml`, `operators.yaml`
- Test: `capabilities/data-processing/tests/test_manifests.py`
- [ ] **Step 1: Write the package metadata**

`capabilities/data-processing/pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=68.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "open-robot-dataproc"
version = "0.1.0"
description = "Data-processing operators for Open Robot Stack: filtering, compression, cleaning and ROS 2 format conversion on the operator contract"
requires-python = ">=3.10"
license = { text = "Apache-2.0" }
dependencies = [
  "numpy>=1.24",
  "pyarrow>=14",
  "scipy>=1.10",
  "Pillow>=10.0",
  "zstandard>=0.21",
  "pyyaml>=6.0",
]

[project.optional-dependencies]
dev = ["pytest>=7.0", "pytest-cov>=4.0"]

[tool.setuptools.packages.find]
include = ["open_robot_dataproc*"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

`scipy` and `Pillow` are hard dependencies rather than extras: three of the
seven data operators cannot run without them. `cv2` appears nowhere, which is
why there is no bilateral filter mode.
- [ ] **Step 2: Write the conftest**

`capabilities/data-processing/conftest.py`:

```python
"""Make the pack and the contract package importable from a bare checkout.

The real pack resolves open_robot_operator from packages/open-robot-operator;
both roots go at the FRONT of sys.path because a global open_robot_sdk on this
machine resolves to an unrelated project of the same name, and nothing here
may depend on a shared editable install.
"""

import sys
from pathlib import Path

_PACK = Path(__file__).resolve().parent
_CONTRACT = _PACK.parents[1] / "packages" / "open-robot-operator"
for root in (_PACK, _CONTRACT):
    if root.is_dir() and str(root) not in sys.path:
        sys.path.insert(0, str(root))
```
- [ ] **Step 3: Create the package markers**

```bash
cd capabilities/data-processing
for d in . filter compress clean convert tools mocks; do
  mkdir -p "open_robot_dataproc/$d"
  printf '"""Data-processing operators for the Open Robot Stack."""\n' \
    > "open_robot_dataproc/$d/__init__.py"
done
printf '"""Mock sources and sinks for the orchestration examples.\n\nThey exist so the examples form a complete, checkable graph. Nothing here is\ndeployed, and nothing here imports dora at module level.\n"""\n' \
  > open_robot_dataproc/mocks/__init__.py
```

Each `__init__.py` holds exactly its docstring. These are package markers,
not modules with behaviour.
- [ ] **Step 4: Write the capability pack manifest**

`capabilities/data-processing/pack.yaml`:

```yaml
# Capability Pack (v1.3 §7.3). camelCase, because a distribution manifest is
# camelCase per §8.5; the runtime port descriptors live in operators.yaml.
#
# The capability ids are deliberately coarse: a preprocessing chain is one
# capability an application asks for, not one per filter mode. The per-operator
# detail is in operators.yaml, which is the registry.
apiVersion: openrobot.dev/v1alpha1
kind: CapabilityPack

metadata:
  name: data-processing
  version: 0.1.0

provides:
  capabilities:
    - id: robot.data.preprocess
      version: 1.0.0
      operations:
        configure:
          protocol: robot-control-v1
          verb: provider.dataproc.preprocess.configure
          safetyTier: observe
    - id: robot.data.diagnostics
      version: 1.0.0
      operations:
        read:
          protocol: robot-control-v1
          verb: provider.dataproc.diagnostics.read
          safetyTier: observe

requires:
  packages:
    - id: open-robot-operator
      version: ^0.1
```
- [ ] **Step 5: Write the port declarations**

`capabilities/data-processing/operators.yaml`:

```yaml
# Port declarations for the data-processing operators.
#
# snake_case per v1.3 §8.5: "Runtime/wire envelopes and descriptors use
# snake_case", and a port descriptor is a wire descriptor. pack.yaml next to
# this file is the camelCase distribution manifest.
#
# This file is also the operator registry contract item 15 promises. There is
# no run-time registry service: a declarative manifest satisfies a 机制, and a
# resident process with its own lifecycle does not belong in this scope.
contract_version: 1.0.0

operators:
  # --- filtering -----------------------------------------------------------
  - name: point_cloud_filter
    module: open_robot_dataproc.filter.point_cloud_op
    inputs:
      cloud:
        schema: openrobot.sensor.point_cloud/^1.0
        frame: any
        max_age_ms: 200
    outputs:
      cloud:
        schema: openrobot.sensor.point_cloud/1.0.0
        frame: same_as:cloud
      diag:
        schema: openrobot.diag.counters/1.0.0
        frame: none
    diagnostics: diag

  - name: image_filter
    module: open_robot_dataproc.filter.image_op
    inputs:
      image:
        schema: openrobot.sensor.image/^1.0
        frame: any
        max_age_ms: 200
    outputs:
      image:
        schema: openrobot.sensor.image/1.0.0
        frame: same_as:image
      diag:
        schema: openrobot.diag.counters/1.0.0
        frame: none
    diagnostics: diag

  - name: state_filter
    module: open_robot_dataproc.filter.state_op
    inputs:
      state:
        schema: openrobot.state.vector/^1.0
        frame: any
        max_age_ms: 100
    outputs:
      state:
        schema: openrobot.state.vector/1.0.0
        frame: same_as:state
      diag:
        schema: openrobot.diag.counters/1.0.0
        frame: none
    diagnostics: diag

  # --- compression ---------------------------------------------------------
  - name: point_cloud_compress
    module: open_robot_dataproc.compress.point_cloud_op
    inputs:
      cloud:
        schema: openrobot.sensor.point_cloud/^1.0
        frame: any
    outputs:
      blob:
        schema: openrobot.sensor.point_cloud_compressed/1.0.0
        frame: same_as:cloud
      diag:
        schema: openrobot.diag.counters/1.0.0
        frame: none
    diagnostics: diag

  - name: image_compress
    module: open_robot_dataproc.compress.image_op
    inputs:
      image:
        schema: openrobot.sensor.image/^1.0
        frame: any
    outputs:
      blob:
        schema: openrobot.sensor.image_compressed/1.0.0
        frame: same_as:image
      diag:
        schema: openrobot.diag.counters/1.0.0
        frame: none
    diagnostics: diag

  # --- cleaning ------------------------------------------------------------
  - name: data_cleaner
    module: open_robot_dataproc.clean.cleaner_op
    inputs:
      data:
        schema: openrobot.state.vector/^1.0
        frame: any
        max_age_ms: 500
    outputs:
      data:
        schema: openrobot.state.vector/1.0.0
        frame: same_as:data
      diag:
        schema: openrobot.diag.counters/1.0.0
        frame: none
    diagnostics: diag

  # --- format conversion ---------------------------------------------------
  # Both directions in one operator, and both inputs optional: a given
  # dataflow wires the direction it needs.
  - name: ros2_codec
    module: open_robot_dataproc.convert.ros2_codec_op
    inputs:
      native:
        schema: openrobot.sensor.point_cloud/^1.0
        frame: any
        required: false
      ros:
        schema: openrobot.interop.ros2_message/^1.0
        frame: any
        required: false
    outputs:
      ros:
        schema: openrobot.interop.ros2_message/1.0.0
        frame: same_as:native
      native:
        schema: openrobot.sensor.point_cloud/1.0.0
        frame: same_as:ros
      diag:
        schema: openrobot.diag.counters/1.0.0
        frame: none
    diagnostics: diag

  # --- chain tooling -------------------------------------------------------
  # A node rather than a script, because it has to subscribe to the live
  # diagnostics ports. Four optional stages is a bounded, checkable shape; a
  # chain longer than that splits into two collectors.
  - name: diag_collector
    module: open_robot_dataproc.tools.diag_collector
    inputs:
      stage_1:
        schema: openrobot.diag.counters/^1.0
        frame: none
        required: false
      stage_2:
        schema: openrobot.diag.counters/^1.0
        frame: none
        required: false
      stage_3:
        schema: openrobot.diag.counters/^1.0
        frame: none
        required: false
      stage_4:
        schema: openrobot.diag.counters/^1.0
        frame: none
        required: false
    outputs:
      report:
        schema: openrobot.diag.chain_report/1.0.0
        frame: none
```
- [ ] **Step 6: Write the manifest tests**

`capabilities/data-processing/tests/test_manifests.py`:

```python
"""Parse-level checks on the pack's two manifests.

Whether each declared module actually imports belongs with the conformance
suite, once the modules exist.
"""

from pathlib import Path

import pytest
import yaml

from open_robot_operator.declare import load_operators

PACK = Path(__file__).resolve().parents[1]
DECLS = load_operators(PACK / "operators.yaml")
PACK_YAML = yaml.safe_load((PACK / "pack.yaml").read_text(encoding="utf-8"))

EXPECTED = (
    "point_cloud_filter",
    "image_filter",
    "state_filter",
    "point_cloud_compress",
    "image_compress",
    "data_cleaner",
    "ros2_codec",
    "diag_collector",
)


def test_the_pack_declares_the_expected_operators():
    assert tuple(DECLS) == EXPECTED


def test_the_contract_operator_families_are_all_present():
    """Item 16 promises filtering, compression, cleaning and conversion."""
    assert {"point_cloud_filter", "image_filter", "state_filter"} <= set(DECLS)
    assert {"point_cloud_compress", "image_compress"} <= set(DECLS)
    assert "data_cleaner" in DECLS
    assert "ros2_codec" in DECLS


def test_no_mock_leaks_into_the_registry():
    """The registry is what the pack provides; a mock lidar is not that."""
    assert not any(name.startswith("mock_") for name in DECLS)


@pytest.mark.parametrize("name", EXPECTED)
def test_every_output_states_a_concrete_version(name):
    for port in DECLS[name].outputs.values():
        assert not port.version_spec.startswith("^"), f"{name}.{port.name}"


@pytest.mark.parametrize("name", EXPECTED)
def test_a_declared_diagnostics_port_is_a_real_output(name):
    decl = DECLS[name]
    if decl.diagnostics is not None:
        assert decl.diagnostics in decl.outputs
        assert decl.outputs[decl.diagnostics].schema_id == "openrobot.diag.counters"
        assert decl.outputs[decl.diagnostics].frame == "none"


def test_the_collector_has_no_diagnostics_of_its_own():
    """It reports on others; a report about its own reporting is noise."""
    assert DECLS["diag_collector"].diagnostics is None


def test_compressed_outputs_use_the_compressed_schemas():
    """Otherwise a compressed stream could be wired into an operator that
    expects raw samples, and the pre-launch check would not catch it."""
    assert DECLS["point_cloud_compress"].outputs["blob"].schema_id == (
        "openrobot.sensor.point_cloud_compressed"
    )
    assert DECLS["image_compress"].outputs["blob"].schema_id == (
        "openrobot.sensor.image_compressed"
    )


def test_both_codec_directions_are_optional():
    """A dataflow wires the direction it needs."""
    codec = DECLS["ros2_codec"]
    assert codec.inputs["native"].required is False
    assert codec.inputs["ros"].required is False


def test_every_input_that_can_go_stale_declares_a_budget():
    for name in ("point_cloud_filter", "image_filter", "state_filter", "data_cleaner"):
        port = next(iter(DECLS[name].inputs.values()))
        assert port.max_age_ms is not None, name


def test_pack_yaml_is_a_capability_pack():
    assert PACK_YAML["apiVersion"] == "openrobot.dev/v1alpha1"
    assert PACK_YAML["kind"] == "CapabilityPack"
    assert PACK_YAML["metadata"]["name"] == "data-processing"


def test_every_capability_declares_the_observe_tier():
    """Preprocessing reads and reshapes data; it never commands motion."""
    for capability in PACK_YAML["provides"]["capabilities"]:
        for name, operation in capability["operations"].items():
            assert operation["safetyTier"] == "observe", (capability["id"], name)


def test_the_pack_requires_the_contract_package():
    required = {r["id"]: r["version"] for r in PACK_YAML["requires"]["packages"]}
    assert required["open-robot-operator"].startswith("^")
```

These only parse the manifests. Whether each declared module imports belongs
in Task 16, once the modules exist.
- [ ] **Step 7: Run them**

Run: `cd capabilities/data-processing && python3 -m pytest tests/test_manifests.py -q`
Expected: PASS, 26 tests

- [ ] **Step 8: Commit**

```bash
git add capabilities/data-processing
git commit -m "feat(dataproc): the pack skeleton, its manifests and the operator registry"
```

---

## Task 10: Point-cloud filtering

Downsampling, cropping, outlier rejection and temporal accumulation. These
live here rather than in the perception pack: they appear in both contract
items 13 and 16, they carry no perception semantics, and "降低数据冗余" is the
definition of downsampling. The perception pack depends on them and wires
them in its own example, so item 13's promise is met without a second
implementation.

**Files:**
- Create: `capabilities/data-processing/open_robot_dataproc/filter/point_cloud_op.py`
- Test: `capabilities/data-processing/tests/test_point_cloud_filter.py`

- [ ] **Step 1: Write the failing test**

`capabilities/data-processing/tests/test_point_cloud_filter.py`:

```python
import numpy as np
import pytest

from open_robot_dataproc.filter.point_cloud_op import (
    MODES, Accumulator, apply, as_points, outlier, passthrough, to_flat, voxel,
)

RNG = np.random.default_rng(7)


def cloud(n=400, step=4):
    return RNG.uniform(-5, 5, n * step).astype(np.float32).reshape(-1, step)


def test_the_four_modes_are_declared():
    assert MODES == ("voxel", "passthrough", "outlier", "accumulate")


# --- payload reshaping -------------------------------------------------------

def test_as_points_reshapes_a_flat_payload():
    assert as_points(np.arange(12, dtype=np.float32), 4).shape == (3, 4)


def test_as_points_rejects_a_ragged_payload():
    with pytest.raises(ValueError, match="multiple of item_step"):
        as_points(np.arange(5, dtype=np.float32), 4)


def test_as_points_rejects_a_non_positive_item_step():
    with pytest.raises(ValueError, match="item_step"):
        as_points(np.arange(4, dtype=np.float32), 0)


def test_flat_and_points_round_trip():
    points = cloud(10)
    assert np.array_equal(as_points(to_flat(points), 4), points)


def test_an_empty_payload_reshapes_to_no_points():
    assert as_points(np.zeros(0, dtype=np.float32), 4).shape == (0, 4)


# --- voxel -------------------------------------------------------------------

def test_voxel_reduces_the_point_count():
    points = cloud()
    assert len(voxel(points, 1.0)) < len(points)


def test_voxel_is_deterministic():
    points = cloud()
    assert np.array_equal(voxel(points, 1.0), voxel(points, 1.0))


def test_voxel_keeps_one_point_per_cell():
    """Three points in one cell plus one far away leaves two."""
    points = np.array(
        [[0.1, 0.1, 0.1, 1], [0.2, 0.2, 0.2, 1], [0.3, 0.3, 0.3, 1], [9.0, 9.0, 9.0, 1]],
        dtype=np.float32,
    )
    assert len(voxel(points, 1.0)) == 2


def test_voxel_keeps_the_earliest_point_of_each_cell():
    points = np.array([[0.1, 0, 0, 11], [0.2, 0, 0, 22]], dtype=np.float32)
    assert voxel(points, 1.0)[0][3] == 11


def test_voxel_preserves_the_extra_columns():
    points = cloud(50)
    kept = voxel(points, 1.0)
    assert kept.shape[1] == points.shape[1]


@pytest.mark.parametrize("bad", [0.0, -1.0, float("nan"), float("inf")])
def test_voxel_rejects_a_non_positive_leaf(bad):
    with pytest.raises(ValueError, match="leaf_size"):
        voxel(cloud(10), bad)


def test_voxel_on_an_empty_cloud_returns_it_unchanged():
    assert voxel(cloud(0), 1.0).shape == (0, 4)


# --- passthrough -------------------------------------------------------------

def test_passthrough_keeps_only_points_inside_the_box():
    kept = passthrough(cloud(), [-1, -1, -1], [1, 1, 1])
    assert np.all(np.abs(kept[:, :3]) <= 1)


def test_passthrough_bounds_are_inclusive():
    points = np.array([[1.0, 1.0, 1.0, 0]], dtype=np.float32)
    assert len(passthrough(points, [0, 0, 0], [1, 1, 1])) == 1


def test_passthrough_rejects_inverted_bounds():
    with pytest.raises(ValueError, match="exceeds"):
        passthrough(cloud(10), [1, 1, 1], [0, 0, 0])


@pytest.mark.parametrize("bounds", [([0, 0], [1, 1, 1]), ([0, 0, 0], [1, 1])])
def test_passthrough_needs_three_bounds_each(bounds):
    with pytest.raises(ValueError, match="three values"):
        passthrough(cloud(10), *bounds)


def test_passthrough_on_an_empty_cloud_returns_it_unchanged():
    assert passthrough(cloud(0), [-1, -1, -1], [1, 1, 1]).shape == (0, 4)


# --- outlier -----------------------------------------------------------------

def test_outlier_removes_planted_far_points():
    base = RNG.normal(0, 0.3, (500, 4)).astype(np.float32)
    far = np.array([[50, 50, 50, 1], [-60, 10, 0, 1], [0, 0, 99, 1]], dtype=np.float32)
    kept, dropped = outlier(np.vstack([base, far]), 8, 1.0)
    assert dropped >= 3
    for planted in far:
        assert not any(np.allclose(planted, row) for row in kept)


def test_outlier_reports_what_it_dropped():
    points = cloud(200)
    kept, dropped = outlier(points, 8, 1.0)
    assert dropped == len(points) - len(kept)


def test_outlier_agrees_with_a_brute_force_reference():
    points = cloud(300)
    kept, dropped = outlier(points, 8, 1.0)
    xyz = points[:, :3].astype(np.float64)
    distances = np.linalg.norm(xyz[:, None, :] - xyz[None, :, :], axis=2)
    np.fill_diagonal(distances, np.inf)
    mean_distance = np.sort(distances, axis=1)[:, :8].mean(axis=1)
    keep = mean_distance <= mean_distance.mean() + mean_distance.std()
    assert np.array_equal(kept, points[keep])
    assert dropped == int((~keep).sum())


def test_outlier_scales_to_a_realistic_cloud():
    """A pairwise matrix would need 10^10 entries here."""
    points = RNG.uniform(-20, 20, 100_000 * 4).astype(np.float32).reshape(-1, 4)
    kept, dropped = outlier(points, 8, 1.0)
    assert dropped > 0
    assert len(kept) + dropped == len(points)


def test_outlier_leaves_a_cloud_too_small_to_judge_alone():
    points = cloud(5)
    kept, dropped = outlier(points, 8, 1.0)
    assert dropped == 0
    assert np.array_equal(kept, points)


def test_outlier_on_an_empty_cloud_returns_it_unchanged():
    kept, dropped = outlier(cloud(0), 8, 1.0)
    assert kept.shape == (0, 4) and dropped == 0


@pytest.mark.parametrize("bad", [0, -1])
def test_outlier_rejects_a_non_positive_neighbour_count(bad):
    with pytest.raises(ValueError, match="neighbours"):
        outlier(cloud(100), bad, 1.0)


@pytest.mark.parametrize("bad", [-0.1, float("nan")])
def test_outlier_rejects_a_bad_sigma(bad):
    with pytest.raises(ValueError, match="sigma"):
        outlier(cloud(100), 8, bad)


# --- accumulate --------------------------------------------------------------

def test_accumulate_grows_until_the_window_is_full():
    acc = Accumulator(3)
    sizes = [len(acc.push(cloud(10))) for _ in range(5)]
    assert sizes == [10, 20, 30, 30, 30]


def test_accumulate_reports_its_depth():
    acc = Accumulator(2)
    acc.push(cloud(5))
    assert acc.depth == 1
    acc.push(cloud(5))
    acc.push(cloud(5))
    assert acc.depth == 2


def test_accumulate_drops_the_oldest_frame_first():
    acc = Accumulator(2)
    first = np.full((1, 4), 1.0, dtype=np.float32)
    second = np.full((1, 4), 2.0, dtype=np.float32)
    third = np.full((1, 4), 3.0, dtype=np.float32)
    acc.push(first)
    acc.push(second)
    out = acc.push(third)
    assert sorted(out[:, 0].tolist()) == [2.0, 3.0]


@pytest.mark.parametrize("bad", [0, -1])
def test_accumulate_rejects_an_empty_window(bad):
    with pytest.raises(ValueError, match="max_frames"):
        Accumulator(bad)


# --- apply -------------------------------------------------------------------

def test_apply_voxel_tallies_what_it_removed():
    points = cloud()
    kept, drops = apply(points, {"mode": "voxel", "leaf_size": 1.0})
    assert drops == {"downsampled": len(points) - len(kept)}


def test_apply_passthrough_tallies_out_of_range_points():
    points = cloud()
    kept, drops = apply(points, {"mode": "passthrough", "min": [-1] * 3, "max": [1] * 3})
    assert drops == {"out_of_range": len(points) - len(kept)}


def test_apply_outlier_tallies_under_its_own_reason():
    kept, drops = apply(cloud(200), {"mode": "outlier", "neighbours": 8, "sigma": 1.0})
    assert set(drops) == {"outlier"}


def test_apply_reports_no_drops_when_nothing_was_removed():
    points = np.array([[0.0, 0.0, 0.0, 1.0]], dtype=np.float32)
    _, drops = apply(points, {"mode": "voxel", "leaf_size": 1.0})
    assert drops == {}


def test_apply_accumulate_needs_a_window():
    with pytest.raises(ValueError, match="Accumulator"):
        apply(cloud(10), {"mode": "accumulate", "max_frames": 3})


def test_apply_accumulate_uses_the_window_it_is_given():
    acc = Accumulator(2)
    apply(cloud(10), {"mode": "accumulate"}, acc)
    kept, drops = apply(cloud(10), {"mode": "accumulate"}, acc)
    assert len(kept) == 20 and drops == {}


@pytest.mark.parametrize("bad", [None, "", "VOXEL", "downsample"])
def test_apply_rejects_an_unknown_mode(bad):
    with pytest.raises(ValueError, match="mode"):
        apply(cloud(10), {"mode": bad})
```
- [ ] **Step 2: Run to verify they fail**

Run: `cd capabilities/data-processing && python3 -m pytest tests/test_point_cloud_filter.py -q`
Expected: collection error — the module under test does not exist yet

- [ ] **Step 3: Write `point_cloud_op.py`**

`capabilities/data-processing/open_robot_dataproc/filter/point_cloud_op.py`:

```python
"""Point-cloud filtering: spatial downsampling, cropping, outlier rejection
and temporal accumulation.

Downsampling and outlier rejection live here rather than in the perception
pack. They appear in both contract items 13 and 16, they carry no perception
semantics, and "降低数据冗余" is the definition of downsampling. The
perception pack depends on these and wires them in its own example, so item
13's promise is met without a second implementation.
"""

from collections import deque
from typing import Dict, Optional, Tuple

import numpy as np

MODES = ("voxel", "passthrough", "outlier", "accumulate")


def as_points(flat, item_step: int = 4) -> np.ndarray:
    """Reshape a flat float32 payload into one row per point."""
    if item_step < 1:
        raise ValueError(f"item_step must be >= 1, got {item_step}")
    array = np.asarray(flat, dtype=np.float32).reshape(-1)
    if array.size % item_step:
        raise ValueError(
            f"payload of {array.size} values is not a multiple of item_step {item_step}"
        )
    return array.reshape(-1, item_step)


def to_flat(points: np.ndarray) -> np.ndarray:
    return np.asarray(points, dtype=np.float32).reshape(-1)


def voxel(points: np.ndarray, leaf_size: float) -> np.ndarray:
    """Keep the first point in each cubic cell of side `leaf_size`."""
    if not np.isfinite(leaf_size) or leaf_size <= 0:
        raise ValueError(f"leaf_size must be a positive finite number, got {leaf_size!r}")
    if len(points) == 0:
        return points
    keys = np.floor(points[:, :3] / leaf_size).astype(np.int64)
    _, index = np.unique(keys, axis=0, return_index=True)
    # Sorting the kept indices makes the output order deterministic and keeps
    # the earliest point of each cell, which np.unique does not promise.
    return points[np.sort(index)]


def passthrough(points: np.ndarray, minimum, maximum) -> np.ndarray:
    """Keep points inside an axis-aligned box, bounds inclusive."""
    low = np.asarray(minimum, dtype=np.float32).reshape(-1)
    high = np.asarray(maximum, dtype=np.float32).reshape(-1)
    if low.size != 3 or high.size != 3:
        raise ValueError("passthrough bounds must each hold three values")
    if np.any(low > high):
        raise ValueError(f"passthrough minimum {low.tolist()} exceeds maximum {high.tolist()}")
    if len(points) == 0:
        return points
    inside = np.all((points[:, :3] >= low) & (points[:, :3] <= high), axis=1)
    return points[inside]


def outlier(points: np.ndarray, neighbours: int, sigma: float) -> Tuple[np.ndarray, int]:
    """Drop points whose mean k-nearest-neighbour distance is far from typical.

    A KD-tree, not a pairwise distance matrix: the matrix is O(n^2), which at a
    realistic 100k-point cloud would be 10^10 entries. Measured at 66 ms for
    100k points.
    """
    from scipy.spatial import cKDTree

    if neighbours < 1:
        raise ValueError(f"neighbours must be >= 1, got {neighbours}")
    if not np.isfinite(sigma) or sigma < 0:
        raise ValueError(f"sigma must be a non-negative finite number, got {sigma!r}")
    count = len(points)
    if count == 0 or count <= neighbours:
        return points, 0  # too few points to judge any of them
    xyz = points[:, :3].astype(np.float64)
    distances, _ = cKDTree(xyz).query(xyz, k=neighbours + 1, workers=-1)
    mean_distance = distances[:, 1:].mean(axis=1)  # column 0 is the point itself
    threshold = mean_distance.mean() + sigma * mean_distance.std()
    keep = mean_distance <= threshold
    return points[keep], int((~keep).sum())


class Accumulator:
    """Temporal accumulation over a bounded window of recent frames."""

    def __init__(self, max_frames: int) -> None:
        if max_frames < 1:
            raise ValueError(f"max_frames must be >= 1, got {max_frames}")
        self._frames = deque(maxlen=max_frames)

    @property
    def depth(self) -> int:
        return len(self._frames)

    def push(self, points: np.ndarray) -> np.ndarray:
        self._frames.append(np.asarray(points, dtype=np.float32))
        return np.concatenate(list(self._frames), axis=0)


def apply(
    points: np.ndarray, config: Dict, accumulator: Optional[Accumulator] = None
) -> Tuple[np.ndarray, Dict[str, int]]:
    """Run one configured mode. Returns the points kept and the drop tally."""
    mode = config.get("mode")
    if mode not in MODES:
        raise ValueError(f"unknown mode {mode!r}; expected one of {MODES}")
    before = len(points)
    if mode == "voxel":
        kept = voxel(points, float(config["leaf_size"]))
        return kept, {"downsampled": before - len(kept)} if before > len(kept) else {}
    if mode == "passthrough":
        kept = passthrough(points, config["min"], config["max"])
        return kept, {"out_of_range": before - len(kept)} if before > len(kept) else {}
    if mode == "outlier":
        kept, dropped = outlier(points, int(config["neighbours"]), float(config["sigma"]))
        return kept, {"outlier": dropped} if dropped else {}
    if accumulator is None:
        raise ValueError("the accumulate mode needs an Accumulator to hold its window")
    return accumulator.push(points), {}
```
- [ ] **Step 4: Run to verify they pass**

Run: `cd capabilities/data-processing && python3 -m pytest tests/test_point_cloud_filter.py -q`
Expected: PASS, 47 tests (pack cumulative 73)

Two things in here are not arbitrary. `outlier` uses `scipy.spatial.cKDTree`
rather than a pairwise distance matrix, because the matrix is O(n^2) and a
realistic 100k-point cloud would need 10^10 entries; the KD-tree form was
measured at 66 ms for 100k points and `test_outlier_agrees_with_a_brute_force_reference`
pins it against the naive version on a small input. And `voxel` sorts the
indices `np.unique` returns, because `np.unique` does not promise which
member of a group it keeps, and a filter whose output order wobbles between
runs is not debuggable.

- [ ] **Step 5: Commit**

```bash
git add capabilities/data-processing
git commit -m "feat(dataproc): point-cloud filtering by voxel, range, outlier and window"
```

---

## Task 11: Image and state filtering

Spatial and temporal image filtering, and temporal state filtering. A state
vector has no spatial extent, so there is no spatial state mode; the
interface documentation says so explicitly, because at acceptance a missing
mode and an inapplicable one look identical.

**Files:**
- Create: `capabilities/data-processing/open_robot_dataproc/filter/image_op.py`
- Create: `capabilities/data-processing/open_robot_dataproc/filter/state_op.py`
- Test: `capabilities/data-processing/tests/test_image_and_state_filter.py`

- [ ] **Step 1: Write the failing test**

`capabilities/data-processing/tests/test_image_and_state_filter.py`:

```python
import numpy as np
import pytest

from open_robot_dataproc.filter import image_op, state_op
from open_robot_dataproc.filter.image_op import TemporalAverage, as_image, gaussian, median
from open_robot_dataproc.filter.state_op import LowPass, MovingAverage

RNG = np.random.default_rng(11)


def img(h=8, w=8, c=3):
    return RNG.integers(0, 256, (h, w, c), dtype=np.uint8)


# --- image: reshaping --------------------------------------------------------

def test_as_image_reshapes_a_flat_payload():
    assert as_image(np.zeros(8 * 8 * 3, dtype=np.uint8), 8, 8, 3).shape == (8, 8, 3)


def test_as_image_rejects_a_payload_of_the_wrong_size():
    with pytest.raises(ValueError, match="does not fill"):
        as_image(np.zeros(10, dtype=np.uint8), 8, 8, 3)


@pytest.mark.parametrize("geometry", [(0, 8, 3), (8, 0, 3), (8, 8, 0)])
def test_as_image_rejects_a_degenerate_geometry(geometry):
    with pytest.raises(ValueError):
        as_image(np.zeros(1, dtype=np.uint8), *geometry)


def test_image_flat_and_shaped_round_trip():
    image = img()
    assert np.array_equal(as_image(image_op.to_flat(image), 8, 8, 3), image)


# --- image: gaussian ---------------------------------------------------------

def test_gaussian_preserves_shape_and_dtype():
    out = gaussian(img(), 1.0)
    assert out.shape == (8, 8, 3) and out.dtype == np.uint8


def test_gaussian_reduces_variance():
    noisy = img(32, 32, 1)
    assert gaussian(noisy, 2.0).var() < noisy.var()


def test_gaussian_does_not_blur_across_channels():
    """A red-only image must stay red; bleeding would tint the other channels."""
    image = np.zeros((8, 8, 3), dtype=np.uint8)
    image[:, :, 0] = 200
    out = gaussian(image, 2.0)
    assert out[:, :, 1].max() == 0
    assert out[:, :, 2].max() == 0
    assert out[:, :, 0].min() > 0


@pytest.mark.parametrize("bad", [0.0, -1.0, float("nan"), float("inf")])
def test_gaussian_rejects_a_bad_sigma(bad):
    with pytest.raises(ValueError, match="sigma"):
        gaussian(img(), bad)


# --- image: median -----------------------------------------------------------

def test_median_removes_salt_and_pepper():
    image = np.full((9, 9, 1), 100, dtype=np.uint8)
    image[4, 4, 0] = 255
    assert median(image, 3)[4, 4, 0] == 100


def test_median_does_not_mix_channels():
    image = np.zeros((9, 9, 3), dtype=np.uint8)
    image[:, :, 0] = 150
    out = median(image, 3)
    assert out[:, :, 1].max() == 0 and out[:, :, 0].min() == 150


@pytest.mark.parametrize("bad", [1, 0, -3])
def test_median_rejects_a_size_that_filters_nothing(bad):
    with pytest.raises(ValueError, match="size"):
        median(img(), bad)


# --- image: temporal average -------------------------------------------------

def test_temporal_average_of_one_frame_is_that_frame():
    image = img()
    assert np.array_equal(TemporalAverage(3).push(image), image)


def test_temporal_average_averages_the_window():
    window = TemporalAverage(2)
    window.push(np.full((2, 2, 1), 100, dtype=np.uint8))
    out = window.push(np.full((2, 2, 1), 200, dtype=np.uint8))
    assert np.all(out == 150)


def test_temporal_average_forgets_beyond_the_window():
    window = TemporalAverage(2)
    for value in (0, 100, 200):
        out = window.push(np.full((2, 2, 1), value, dtype=np.uint8))
    assert np.all(out == 150)  # the 0 frame has fallen out


def test_temporal_average_reports_its_depth():
    window = TemporalAverage(2)
    window.push(img()); window.push(img()); window.push(img())
    assert window.depth == 2


def test_temporal_average_rejects_a_geometry_change_mid_stream():
    window = TemporalAverage(3)
    window.push(img(8, 8, 3))
    with pytest.raises(ValueError, match="geometry changed"):
        window.push(img(4, 4, 3))


@pytest.mark.parametrize("bad", [0, -1])
def test_temporal_average_rejects_an_empty_window(bad):
    with pytest.raises(ValueError, match="max_frames"):
        TemporalAverage(bad)


# --- image: apply ------------------------------------------------------------

def test_image_apply_dispatches_each_mode():
    assert image_op.apply(img(), {"mode": "gaussian", "sigma": 1.0})[0].shape == (8, 8, 3)
    assert image_op.apply(img(), {"mode": "median", "size": 3})[0].shape == (8, 8, 3)
    window = TemporalAverage(2)
    assert image_op.apply(img(), {"mode": "temporal_average"}, window)[0].shape == (8, 8, 3)


def test_image_filtering_drops_nothing():
    _, drops = image_op.apply(img(), {"mode": "gaussian", "sigma": 1.0})
    assert drops == {}


def test_image_temporal_average_needs_a_window():
    with pytest.raises(ValueError, match="TemporalAverage"):
        image_op.apply(img(), {"mode": "temporal_average"})


@pytest.mark.parametrize("bad", [None, "bilateral", "GAUSSIAN"])
def test_image_apply_rejects_an_unknown_mode(bad):
    with pytest.raises(ValueError, match="mode"):
        image_op.apply(img(), {"mode": bad})


def test_there_is_no_bilateral_mode():
    """Recorded as a decision, not an oversight: no cv2, and the contract
    does not name it."""
    assert "bilateral" not in image_op.MODES


# --- state: moving average ---------------------------------------------------

def test_moving_average_of_one_sample_is_that_sample():
    assert MovingAverage(3).push([1.0, 2.0]).tolist() == [1.0, 2.0]


def test_moving_average_averages_the_window():
    filt = MovingAverage(2)
    filt.push([0.0])
    assert filt.push([10.0]).tolist() == [5.0]


def test_moving_average_forgets_beyond_the_window():
    filt = MovingAverage(2)
    for value in (0.0, 10.0, 20.0):
        out = filt.push([value])
    assert out.tolist() == [15.0]


def test_moving_average_rejects_a_width_change():
    filt = MovingAverage(3)
    filt.push([1.0, 2.0])
    with pytest.raises(ValueError, match="width"):
        filt.push([1.0])


@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
def test_moving_average_rejects_a_non_finite_sample(bad):
    with pytest.raises(ValueError, match="finite"):
        MovingAverage(3).push([bad])


@pytest.mark.parametrize("bad", [0, -1])
def test_moving_average_rejects_an_empty_window(bad):
    with pytest.raises(ValueError, match="window"):
        MovingAverage(bad)


# --- state: low pass ---------------------------------------------------------

def test_lowpass_passes_the_first_sample_through():
    filt = LowPass(cutoff_hz=1.0, sample_hz=100.0)
    assert not filt.primed
    assert filt.push([5.0]).tolist() == [5.0]
    assert filt.primed


def test_lowpass_converges_towards_a_step():
    filt = LowPass(cutoff_hz=5.0, sample_hz=100.0)
    filt.push([0.0])
    values = [filt.push([1.0])[0] for _ in range(200)]
    assert values[0] < values[10] < values[-1]
    assert values[-1] == pytest.approx(1.0, abs=1e-3)


def test_lowpass_attenuates_alternating_noise_more_than_a_slow_signal():
    noisy = LowPass(cutoff_hz=1.0, sample_hz=100.0)
    noisy.push([0.0])
    swing = [abs(noisy.push([10.0 if i % 2 else -10.0])[0]) for i in range(100)]
    assert max(swing[10:]) < 10.0


def test_lowpass_alpha_is_between_zero_and_one():
    assert 0.0 < LowPass(cutoff_hz=1.0, sample_hz=100.0).alpha < 1.0


def test_a_higher_cutoff_follows_the_input_more_closely():
    slow = LowPass(cutoff_hz=1.0, sample_hz=100.0)
    fast = LowPass(cutoff_hz=20.0, sample_hz=100.0)
    for filt in (slow, fast):
        filt.push([0.0])
    assert fast.push([1.0])[0] > slow.push([1.0])[0]


def test_lowpass_restarts_on_a_width_change():
    filt = LowPass(cutoff_hz=1.0, sample_hz=100.0)
    filt.push([1.0])
    assert filt.push([7.0, 8.0]).tolist() == [7.0, 8.0]


@pytest.mark.parametrize("bad", [0.0, -1.0, float("nan"), float("inf")])
def test_lowpass_rejects_a_bad_cutoff(bad):
    with pytest.raises(ValueError, match="cutoff_hz"):
        LowPass(cutoff_hz=bad, sample_hz=100.0)


@pytest.mark.parametrize("bad", [0.0, -1.0, float("nan")])
def test_lowpass_rejects_a_bad_sample_rate(bad):
    with pytest.raises(ValueError, match="sample_hz"):
        LowPass(cutoff_hz=1.0, sample_hz=bad)


@pytest.mark.parametrize("cutoff", [50.0, 60.0])
def test_lowpass_rejects_a_cutoff_at_or_above_nyquist(cutoff):
    with pytest.raises(ValueError, match="Nyquist"):
        LowPass(cutoff_hz=cutoff, sample_hz=100.0)


@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
def test_lowpass_rejects_a_non_finite_sample(bad):
    filt = LowPass(cutoff_hz=1.0, sample_hz=100.0)
    filt.push([0.0])
    with pytest.raises(ValueError, match="finite"):
        filt.push([bad])


# --- state: apply ------------------------------------------------------------

def test_state_apply_dispatches_each_mode():
    assert state_op.apply([1.0], {"mode": "moving_average"}, MovingAverage(2))[0].tolist() == [1.0]
    assert state_op.apply([1.0], {"mode": "lowpass"}, LowPass(1.0, 100.0))[0].tolist() == [1.0]


def test_state_filtering_drops_nothing():
    _, drops = state_op.apply([1.0], {"mode": "moving_average"}, MovingAverage(2))
    assert drops == {}


def test_state_apply_needs_a_filter_object():
    with pytest.raises(ValueError, match="state"):
        state_op.apply([1.0], {"mode": "moving_average"})


def test_there_is_no_spatial_state_mode():
    assert state_op.MODES == ("moving_average", "lowpass")
```
- [ ] **Step 2: Run to verify they fail**

Run: `cd capabilities/data-processing && python3 -m pytest tests/test_image_and_state_filter.py -q`
Expected: collection error — the module under test does not exist yet

- [ ] **Step 3: Write `image_op.py`**

`capabilities/data-processing/open_robot_dataproc/filter/image_op.py`:

```python
"""Image filtering: spatial smoothing and temporal averaging.

There is no bilateral mode. cv2 is not installed on the target hosts, neither
scipy.ndimage nor PIL.ImageFilter provides a bilateral filter, and the
contract asks only for "时域与空域滤波算子，滤波参数可配置" without naming
one.
"""

from collections import deque
from typing import Dict, Tuple

import numpy as np

MODES = ("gaussian", "median", "temporal_average")


def as_image(flat, height: int, width: int, channels: int) -> np.ndarray:
    """Reshape a flat uint8 payload into (height, width, channels)."""
    for name, value in (("height", height), ("width", width), ("channels", channels)):
        if value < 1:
            raise ValueError(f"{name} must be >= 1, got {value}")
    array = np.asarray(flat, dtype=np.uint8).reshape(-1)
    expected = height * width * channels
    if array.size != expected:
        raise ValueError(
            f"payload of {array.size} samples does not fill a "
            f"{height}x{width}x{channels} image, which needs {expected}"
        )
    return array.reshape(height, width, channels)


def to_flat(image: np.ndarray) -> np.ndarray:
    return np.asarray(image, dtype=np.uint8).reshape(-1)


def gaussian(image: np.ndarray, sigma: float) -> np.ndarray:
    """Smooth each channel independently; never blur across channels."""
    from scipy.ndimage import gaussian_filter

    if not np.isfinite(sigma) or sigma <= 0:
        raise ValueError(f"sigma must be a positive finite number, got {sigma!r}")
    return gaussian_filter(image, sigma=(sigma, sigma, 0), mode="nearest")


def median(image: np.ndarray, size: int) -> np.ndarray:
    """Median filter each channel independently."""
    from scipy.ndimage import median_filter

    if size < 2:
        raise ValueError(f"size must be >= 2 to filter anything, got {size}")
    return median_filter(image, size=(size, size, 1), mode="nearest")


class TemporalAverage:
    """Mean over a bounded window of recent frames, computed per pixel."""

    def __init__(self, max_frames: int) -> None:
        if max_frames < 1:
            raise ValueError(f"max_frames must be >= 1, got {max_frames}")
        self._frames = deque(maxlen=max_frames)

    @property
    def depth(self) -> int:
        return len(self._frames)

    def push(self, image: np.ndarray) -> np.ndarray:
        frame = np.asarray(image, dtype=np.uint8)
        if self._frames and frame.shape != self._frames[-1].shape:
            raise ValueError(
                f"frame shape {frame.shape} does not match the window's "
                f"{self._frames[-1].shape}; the geometry changed mid-stream"
            )
        self._frames.append(frame)
        stack = np.stack(list(self._frames)).astype(np.float32)
        return np.rint(stack.mean(axis=0)).astype(np.uint8)


def apply(image: np.ndarray, config: Dict, window=None) -> Tuple[np.ndarray, Dict[str, int]]:
    """Run one configured mode. Filtering drops nothing, so the tally is empty."""
    mode = config.get("mode")
    if mode not in MODES:
        raise ValueError(f"unknown mode {mode!r}; expected one of {MODES}")
    if mode == "gaussian":
        return gaussian(image, float(config["sigma"])), {}
    if mode == "median":
        return median(image, int(config["size"])), {}
    if window is None:
        raise ValueError("the temporal_average mode needs a TemporalAverage window")
    return window.push(image), {}
```
- [ ] **Step 4: Write `state_op.py`**

`capabilities/data-processing/open_robot_dataproc/filter/state_op.py`:

```python
"""State-vector filtering, temporal only.

A state vector has no spatial extent, so there is no spatial mode. The
interface documentation says so explicitly, because at acceptance a missing
mode and an inapplicable one look the same.
"""

from collections import deque
from typing import Dict, Tuple

import numpy as np

MODES = ("moving_average", "lowpass")


def as_state(flat) -> np.ndarray:
    return np.asarray(flat, dtype=np.float64).reshape(-1)


class MovingAverage:
    """Unweighted mean over a bounded window of recent samples."""

    def __init__(self, window: int) -> None:
        if window < 1:
            raise ValueError(f"window must be >= 1, got {window}")
        self._samples = deque(maxlen=window)

    @property
    def depth(self) -> int:
        return len(self._samples)

    def push(self, state: np.ndarray) -> np.ndarray:
        sample = as_state(state)
        if self._samples and sample.shape != self._samples[-1].shape:
            raise ValueError(
                f"state of width {sample.size} does not match the window's "
                f"{self._samples[-1].size}"
            )
        if not np.all(np.isfinite(sample)):
            raise ValueError("a state sample must be finite; NaN would poison the window")
        self._samples.append(sample)
        return np.stack(list(self._samples)).mean(axis=0)


class LowPass:
    """One-pole IIR low pass, as a streaming filter rather than a batch one.

    scipy.signal.butter would need the filter state threaded through every
    call; a one-pole recurrence carries its own and is what a per-sample dora
    node actually needs. alpha = 2*pi*fc*dt / (1 + 2*pi*fc*dt).
    """

    def __init__(self, cutoff_hz: float, sample_hz: float) -> None:
        for name, value in (("cutoff_hz", cutoff_hz), ("sample_hz", sample_hz)):
            if not np.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be a positive finite number, got {value!r}")
        if cutoff_hz >= sample_hz / 2:
            raise ValueError(
                f"cutoff_hz {cutoff_hz} is at or above the Nyquist frequency "
                f"{sample_hz / 2}, where the result is meaningless"
            )
        tau = 2.0 * np.pi * cutoff_hz / sample_hz
        self.alpha = float(tau / (1.0 + tau))
        self._state = None

    @property
    def primed(self) -> bool:
        return self._state is not None

    def push(self, state: np.ndarray) -> np.ndarray:
        sample = as_state(state)
        if not np.all(np.isfinite(sample)):
            raise ValueError("a state sample must be finite; NaN would latch the filter")
        if self._state is None or self._state.shape != sample.shape:
            # The first sample, or a width change, restarts the filter rather
            # than mixing two different quantities.
            self._state = sample.copy()
            return self._state.copy()
        self._state = self._state + self.alpha * (sample - self._state)
        return self._state.copy()


def apply(state: np.ndarray, config: Dict, filt=None) -> Tuple[np.ndarray, Dict[str, int]]:
    mode = config.get("mode")
    if mode not in MODES:
        raise ValueError(f"unknown mode {mode!r}; expected one of {MODES}")
    if filt is None:
        raise ValueError(f"the {mode} mode needs a filter object to hold its state")
    return filt.push(state), {}
```
- [ ] **Step 5: Run to verify they pass**

Run: `cd capabilities/data-processing && python3 -m pytest tests/test_image_and_state_filter.py -q`
Expected: PASS, 61 tests (pack cumulative 134)

`LowPass` is a one-pole IIR rather than `scipy.signal.butter`, because a
per-sample dora node needs a filter that carries its own state; a butter
filter would need `lfilter_zi` threaded through every call. The Nyquist guard
is not decoration: a cutoff at or above half the sample rate produces a
meaningless result rather than an error, which is the kind of defect that
ships.

The gaussian and median filters pass a per-axis size with `0` or `1` on the
channel axis, so they never blur across channels. `test_gaussian_does_not_blur_across_channels`
pins that with a red-only image: bleeding would tint the other two.

- [ ] **Step 6: Commit**

```bash
git add capabilities/data-processing
git commit -m "feat(dataproc): image and state filtering"
```

---

## Task 12: Compression

Lossless and lossy compression for point clouds and images. These two
operators are where contract item 16's "保留原始采集时间与来源标识" is
actually at risk, because a compressor replaces the payload completely and is
the natural place to accidentally mint a fresh timestamp. `process` derives
its header rather than building one, which makes that impossible without
deleting the derivation itself — which is mutation target 2.

**Files:**
- Create: `capabilities/data-processing/open_robot_dataproc/compress/point_cloud_op.py`
- Create: `capabilities/data-processing/open_robot_dataproc/compress/image_op.py`
- Test: `capabilities/data-processing/tests/test_compress.py`

- [ ] **Step 1: Write the failing test**

`capabilities/data-processing/tests/test_compress.py`:

```python
import numpy as np
import pytest

from open_robot_dataproc.compress import image_op, point_cloud_op
from open_robot_operator.envelope import originate

RNG = np.random.default_rng(23)
PC = "openrobot.sensor.point_cloud/1.0.0"
IMG = "openrobot.sensor.image/1.0.0"


def cloud(n=400):
    return RNG.uniform(-5, 5, n * 4).astype(np.float32).reshape(-1, 4)


def img(h=16, w=16, c=3):
    return RNG.integers(0, 256, (h, w, c), dtype=np.uint8)


def pc_header(**o):
    base = dict(schema=PC, frame_id="rslidar", seq=1, stamp_ns=1_700_000_000_000_000_000,
                source="lidar.front")
    return originate(**{**base, **o})


def img_header(**o):
    base = dict(schema=IMG, frame_id="camera_front", seq=1,
                stamp_ns=1_700_000_000_000_000_000, source="camera.front")
    return originate(**{**base, **o})


# --- point cloud: lossless ---------------------------------------------------

def test_lossless_point_cloud_round_trips_exactly():
    points = cloud()
    blob, info = point_cloud_op.encode(points, lossy=False)
    assert np.array_equal(point_cloud_op.decode(blob, info), points)


def test_lossless_point_cloud_shrinks_the_payload():
    points = cloud()
    blob, _ = point_cloud_op.encode(points, lossy=False)
    assert len(blob) < points.nbytes


def test_lossless_rejects_a_precision():
    with pytest.raises(ValueError, match="precision only applies"):
        point_cloud_op.encode(cloud(), lossy=False, precision=0.01)


# --- point cloud: lossy ------------------------------------------------------

def test_lossy_point_cloud_error_stays_within_half_a_step():
    """The bound is tight: the worst case reaches exactly precision/2."""
    points = cloud()
    precision = 0.01
    blob, info = point_cloud_op.encode(points, lossy=True, precision=precision)
    back = point_cloud_op.decode(blob, info)
    assert np.abs(back - points).max() <= precision / 2 + 1e-6


def test_lossy_point_cloud_beats_lossless_on_size():
    points = cloud()
    lossy, _ = point_cloud_op.encode(points, lossy=True, precision=0.01)
    lossless, _ = point_cloud_op.encode(points, lossy=False)
    assert len(lossy) < len(lossless)


def test_a_coarser_precision_compresses_further():
    points = cloud()
    fine, _ = point_cloud_op.encode(points, lossy=True, precision=0.001)
    coarse, _ = point_cloud_op.encode(points, lossy=True, precision=0.5)
    assert len(coarse) < len(fine)


def test_lossy_needs_a_precision():
    with pytest.raises(ValueError, match="needs a quantisation precision"):
        point_cloud_op.encode(cloud(), lossy=True)


@pytest.mark.parametrize("bad", [0.0, -0.1, float("nan"), float("inf")])
def test_lossy_rejects_a_bad_precision(bad):
    with pytest.raises(ValueError, match="precision"):
        point_cloud_op.encode(cloud(), lossy=True, precision=bad)


def test_the_info_records_how_to_read_the_blob_back():
    _, info = point_cloud_op.encode(cloud(10), lossy=True, precision=0.01)
    assert info["lossy"] is True
    assert info["precision"] == 0.01
    assert tuple(info["shape"]) == (10, 4)


def test_an_empty_cloud_round_trips():
    points = cloud(0)
    blob, info = point_cloud_op.encode(points, lossy=False)
    assert point_cloud_op.decode(blob, info).shape == (0, 4)


# --- point cloud: the header -------------------------------------------------

def test_compression_preserves_the_capture_time():
    """Item 16: 保留原始采集时间. Minting a fresh stamp here is mutation
    target 2."""
    header = pc_header(stamp_ns=1_234_567_890)
    _, _, out, _ = point_cloud_op.process(
        cloud(10), header, {"lossy": False}, seq=5, declared_frame="same_as:cloud"
    )
    assert out.stamp_ns == 1_234_567_890


def test_compression_preserves_the_source():
    header = pc_header(source="lidar.rear")
    _, _, out, _ = point_cloud_op.process(
        cloud(10), header, {"lossy": False}, seq=5, declared_frame="same_as:cloud"
    )
    assert out.source == "lidar.rear"


def test_compression_restates_the_sequence_number():
    header = pc_header(seq=1)
    _, _, out, _ = point_cloud_op.process(
        cloud(10), header, {"lossy": False}, seq=99, declared_frame="same_as:cloud"
    )
    assert out.seq == 99


def test_compression_takes_its_frame_from_the_declaration():
    header = pc_header(frame_id="rslidar")
    _, _, same, _ = point_cloud_op.process(
        cloud(10), header, {"lossy": False}, seq=1, declared_frame="same_as:cloud"
    )
    _, _, literal, _ = point_cloud_op.process(
        cloud(10), header, {"lossy": False}, seq=1, declared_frame="base_link"
    )
    assert same.frame_id == "rslidar"
    assert literal.frame_id == "base_link"


def test_compression_carries_a_degraded_validity_through():
    header = pc_header(validity="stale", reason="age 300ms > 200ms")
    _, _, out, _ = point_cloud_op.process(
        cloud(10), header, {"lossy": False}, seq=1, declared_frame="same_as:cloud"
    )
    assert out.validity == "stale"
    assert out.reason == "age 300ms > 200ms"


def test_compression_drops_nothing():
    _, _, _, drops = point_cloud_op.process(
        cloud(10), pc_header(), {"lossy": False}, seq=1, declared_frame="same_as:cloud"
    )
    assert drops == {}


# --- image -------------------------------------------------------------------

def test_png_round_trips_exactly():
    image = img()
    blob, info = image_op.encode(image, lossy=False)
    assert np.array_equal(image_op.decode(blob, info), image)


def test_jpeg_is_close_but_not_exact():
    image = np.tile(np.linspace(0, 255, 32, dtype=np.uint8), (32, 1))[:, :, None]
    image = np.repeat(image, 3, axis=2)
    blob, info = image_op.encode(image, lossy=True, quality=90)
    back = image_op.decode(blob, info)
    assert back.shape == image.shape
    assert not np.array_equal(back, image)
    assert np.abs(back.astype(int) - image.astype(int)).mean() < 10


def test_a_lower_jpeg_quality_compresses_further():
    image = img(64, 64, 3)
    high, _ = image_op.encode(image, lossy=True, quality=90)
    low, _ = image_op.encode(image, lossy=True, quality=20)
    assert len(low) < len(high)


def test_a_single_channel_image_round_trips():
    image = img(16, 16, 1)
    blob, info = image_op.encode(image, lossy=False)
    back = image_op.decode(blob, info)
    assert back.shape == (16, 16, 1)
    assert np.array_equal(back, image)


def test_the_info_names_the_codec_and_geometry():
    _, info = image_op.encode(img(8, 12, 3), lossy=True, quality=80)
    assert info["codec"] == "jpeg"
    assert (info["height"], info["width"], info["channels"]) == (8, 12, 3)


def test_png_is_recorded_as_lossless():
    _, info = image_op.encode(img(), lossy=False)
    assert info["lossy"] is False and info["codec"] == "png"


def test_lossy_image_needs_a_quality():
    with pytest.raises(ValueError, match="needs a quality"):
        image_op.encode(img(), lossy=True)


@pytest.mark.parametrize("bad", [0, 96, 100, -1])
def test_image_quality_is_bounded(bad):
    with pytest.raises(ValueError, match="quality"):
        image_op.encode(img(), lossy=True, quality=bad)


def test_lossless_image_rejects_a_quality():
    with pytest.raises(ValueError, match="quality only applies"):
        image_op.encode(img(), lossy=False, quality=80)


@pytest.mark.parametrize("shape", [(16, 16), (16, 16, 2), (16, 16, 4), (4, 4, 3, 2)])
def test_an_unsupported_image_shape_is_rejected(shape):
    with pytest.raises(ValueError, match="shape"):
        image_op.encode(np.zeros(shape, dtype=np.uint8), lossy=False)


def test_image_compression_preserves_the_capture_time_and_source():
    header = img_header(stamp_ns=999_111, source="camera.rear")
    _, _, out, _ = image_op.process(
        img(), header, {"lossy": False}, seq=3, declared_frame="same_as:image"
    )
    assert out.stamp_ns == 999_111
    assert out.source == "camera.rear"


def test_image_compression_takes_its_frame_from_the_declaration():
    header = img_header(frame_id="camera_front")
    _, _, out, _ = image_op.process(
        img(), header, {"lossy": False}, seq=1, declared_frame="base_link"
    )
    assert out.frame_id == "base_link"
```
- [ ] **Step 2: Run to verify they fail**

Run: `cd capabilities/data-processing && python3 -m pytest tests/test_compress.py -q`
Expected: collection error — the module under test does not exist yet

- [ ] **Step 3: Write `point_cloud_op.py`**

`capabilities/data-processing/open_robot_dataproc/compress/point_cloud_op.py`:

```python
"""Point-cloud compression, lossless or by quantisation.

This operator and its image sibling are where contract item 16's "保留原始
采集时间与来源标识" is actually at risk: a compressor rewrites the payload
completely, so it is the natural place to accidentally mint a fresh timestamp.
`process` derives its header instead of building one, which makes that
impossible without deleting the derivation itself.
"""

from typing import Dict, Tuple

import numpy as np
import zstandard as zstd

from open_robot_operator.envelope import Header, derive
from open_robot_operator.wire import output_frame

SCHEMA = "openrobot.sensor.point_cloud_compressed/1.0.0"
DEFAULT_LEVEL = 3


def encode(points: np.ndarray, *, lossy: bool, precision: float = None, level: int = DEFAULT_LEVEL):
    """Compress a point cloud. Returns the blob and the metadata to restore it."""
    array = np.asarray(points, dtype=np.float32)
    if lossy:
        if precision is None:
            raise ValueError("a lossy encode needs a quantisation precision")
        if not np.isfinite(precision) or precision <= 0:
            raise ValueError(f"precision must be a positive finite number, got {precision!r}")
        quantised = np.rint(array / precision).astype(np.int32)
        blob = zstd.ZstdCompressor(level=level).compress(quantised.tobytes())
        return blob, {"lossy": True, "precision": float(precision), "shape": array.shape}
    if precision is not None:
        raise ValueError(
            "precision only applies to a lossy encode; a lossless one would "
            "silently ignore it"
        )
    blob = zstd.ZstdCompressor(level=level).compress(array.tobytes())
    return blob, {"lossy": False, "shape": array.shape}


def decode(blob: bytes, info: Dict) -> np.ndarray:
    raw = zstd.ZstdDecompressor().decompress(blob)
    shape = tuple(info["shape"])
    if info["lossy"]:
        quantised = np.frombuffer(raw, dtype=np.int32).reshape(shape)
        return (quantised.astype(np.float32) * np.float32(info["precision"])).astype(np.float32)
    return np.frombuffer(raw, dtype=np.float32).reshape(shape).copy()


def process(
    points: np.ndarray, header: Header, config: Dict, seq: int, declared_frame: str
) -> Tuple[bytes, Dict, Header, Dict[str, int]]:
    """Compress one cloud and derive the outgoing header.

    `stamp_ns` and `source` come from the parent through `derive`, never from
    the clock. `frame_id` comes from the declaration through `output_frame`,
    never from the inbound metadata.
    """
    blob, info = encode(
        points,
        lossy=bool(config.get("lossy", False)),
        precision=config.get("precision"),
        level=int(config.get("level", DEFAULT_LEVEL)),
    )
    out = derive(
        [header],
        schema=SCHEMA,
        frame_id=output_frame(declared_frame, {"cloud": header}),
        seq=seq,
        validity=header.validity,
        reason=header.reason,
    )
    return blob, info, out, {}
```
- [ ] **Step 4: Write `image_op.py`**

`capabilities/data-processing/open_robot_dataproc/compress/image_op.py`:

```python
"""Image compression, lossy JPEG or lossless PNG.

Pillow rather than cv2, which is not installed on the target hosts.
"""

import io
from typing import Dict, Tuple

import numpy as np

from open_robot_operator.envelope import Header, derive
from open_robot_operator.wire import output_frame

SCHEMA = "openrobot.sensor.image_compressed/1.0.0"
CODECS = {True: "jpeg", False: "png"}


def encode(image: np.ndarray, *, lossy: bool, quality: int = None):
    """Compress an image. Returns the encoded bytes and how to read them back."""
    from PIL import Image

    array = np.asarray(image, dtype=np.uint8)
    if array.ndim != 3 or array.shape[2] not in (1, 3):
        raise ValueError(
            f"expected a (height, width, 1 or 3) image, got shape {array.shape}"
        )
    squeezed = array[:, :, 0] if array.shape[2] == 1 else array
    pillow = Image.fromarray(squeezed, mode="L" if array.shape[2] == 1 else "RGB")
    buffer = io.BytesIO()
    if lossy:
        if quality is None:
            raise ValueError("a lossy encode needs a quality setting")
        if not 1 <= int(quality) <= 95:
            raise ValueError(
                f"quality must be between 1 and 95, got {quality!r}; above 95 "
                "Pillow's JPEG output grows without a visible gain"
            )
        pillow.save(buffer, format="JPEG", quality=int(quality))
    else:
        if quality is not None:
            raise ValueError(
                "quality only applies to a lossy encode; a lossless one would "
                "silently ignore it"
            )
        pillow.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue(), {
        "lossy": lossy,
        "codec": CODECS[lossy],
        "height": int(array.shape[0]),
        "width": int(array.shape[1]),
        "channels": int(array.shape[2]),
    }


def decode(blob: bytes, info: Dict) -> np.ndarray:
    from PIL import Image

    decoded = np.asarray(Image.open(io.BytesIO(blob)), dtype=np.uint8)
    if decoded.ndim == 2:
        decoded = decoded[:, :, None]
    return decoded


def process(
    image: np.ndarray, header: Header, config: Dict, seq: int, declared_frame: str
) -> Tuple[bytes, Dict, Header, Dict[str, int]]:
    blob, info = encode(
        image, lossy=bool(config.get("lossy", False)), quality=config.get("quality")
    )
    out = derive(
        [header],
        schema=SCHEMA,
        frame_id=output_frame(declared_frame, {"image": header}),
        seq=seq,
        validity=header.validity,
        reason=header.reason,
    )
    return blob, info, out, {}
```
- [ ] **Step 5: Run to verify they pass**

Run: `cd capabilities/data-processing && python3 -m pytest tests/test_compress.py -q`
Expected: PASS, 37 tests (pack cumulative 171)

The quantisation error bound is tight: the worst case reaches exactly
`precision / 2`, so the assertion is `<= precision / 2 + 1e-6` and not `<`.
A strict comparison here passes on most seeds and fails on some, which is
worse than failing always.

Both operators refuse a parameter that does not apply to the chosen mode —
`precision` on a lossless encode, `quality` on a PNG — rather than ignoring
it. Silently ignoring a configured value is how a deployment ends up believing
it is compressing at a ratio it never set.

- [ ] **Step 6: Commit**

```bash
git add capabilities/data-processing
git commit -m "feat(dataproc): lossless and lossy compression for clouds and images"
```

---

## Task 13: Data cleaning

The four defect classes of contract item 16, counted in four separate
buckets. "对被丢弃的数据计数并上报" has to distinguish a missing value from an
outlier from a disordered timestamp from a duplicate frame, so a single total
would not answer the question at acceptance.

This is also the only operator in the library permitted to raise a degraded
input to an `ok` output, and only for the one defect it can actually repair.
Age, pairing, confidence and a refusal are not cleanable, so those validities
pass through untouched.

**Files:**
- Create: `capabilities/data-processing/open_robot_dataproc/clean/cleaner_op.py`
- Test: `capabilities/data-processing/tests/test_cleaner.py`

- [ ] **Step 1: Write the failing test**

`capabilities/data-processing/tests/test_cleaner.py`:

```python
import numpy as np
import pytest

from open_robot_dataproc.clean.cleaner_op import REASONS, Cleaner
from open_robot_operator.counters import Counters
from open_robot_operator.envelope import originate

SV = "openrobot.state.vector/1.0.0"
FRAME = "same_as:data"


def header(stamp_ns=1_000, source="lidar.front", **o):
    base = dict(schema=SV, frame_id="rslidar", seq=1, stamp_ns=stamp_ns, source=source)
    return originate(**{**base, **o})


def primed(**kwargs):
    """A cleaner that already holds one good 4-wide sample."""
    cleaner = Cleaner(**kwargs)
    cleaner.process([1.0, 1.0, 1.0, 1.0], header(stamp_ns=1_000), seq=0, declared_frame=FRAME)
    return cleaner


def test_the_four_defect_classes_are_named():
    assert REASONS == ("missing", "outlier", "disorder", "duplicate")


def test_clean_data_passes_through_untouched():
    out = Cleaner().process([1.0, 2.0, 3.0], header(), seq=0, declared_frame=FRAME)
    assert out.forwarded
    assert out.values.tolist() == [1.0, 2.0, 3.0]
    assert out.drops == {}
    assert out.header.validity == "ok"


# --- missing values are repaired in place, never removed --------------------

@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_a_non_finite_value_is_held_from_the_last_good_sample(bad):
    cleaner = primed()
    out = cleaner.process([9.0, bad, 9.0, 9.0], header(stamp_ns=2_000), seq=1, declared_frame=FRAME)
    assert out.values.tolist() == [9.0, 1.0, 9.0, 9.0]
    assert out.drops == {"missing": 1}
    assert cleaner.counters.drops_by_reason == {"missing": 1}


def test_the_payload_width_never_changes():
    """A state vector's elements are positional: joint 3, velocity x. Removing
    element 2 would silently shift the meaning of every element after it."""
    cleaner = primed()
    out = cleaner.process(
        [1.0, float("nan"), float("nan"), 4.0], header(stamp_ns=2_000), seq=1, declared_frame=FRAME
    )
    assert out.values.size == 4


def test_several_missing_values_are_each_counted():
    cleaner = primed()
    out = cleaner.process(
        [float("nan"), float("nan"), 3.0, 4.0], header(stamp_ns=2_000), seq=1, declared_frame=FRAME
    )
    assert out.drops == {"missing": 2}


def test_missing_counts_accumulate_across_messages():
    cleaner = primed()
    for stamp in (2_000, 3_000, 4_000):
        cleaner.process(
            [1.0, float("nan"), 3.0, 4.0], header(stamp_ns=stamp), seq=0, declared_frame=FRAME
        )
    assert cleaner.counters.drops_by_reason == {"missing": 3}


def test_the_held_value_tracks_the_most_recent_good_sample():
    cleaner = Cleaner()
    cleaner.process([1.0, 1.0], header(stamp_ns=1_000), seq=0, declared_frame=FRAME)
    cleaner.process([7.0, 7.0], header(stamp_ns=2_000), seq=1, declared_frame=FRAME)
    out = cleaner.process([5.0, float("nan")], header(stamp_ns=3_000), seq=2, declared_frame=FRAME)
    assert out.values.tolist() == [5.0, 7.0]


def test_with_no_history_the_defect_is_reported_rather_than_invented():
    """Holding a value that was never measured would be a fabrication."""
    cleaner = Cleaner()
    out = cleaner.process([float("nan"), 2.0], header(), seq=0, declared_frame=FRAME)
    assert out.forwarded
    assert out.header.validity == "missing"
    assert "no previous good sample" in out.header.reason
    assert np.isnan(out.values[0])
    assert cleaner.counters.drops_by_reason == {"missing": 1}


def test_an_unrepaired_sample_does_not_become_the_hold_buffer():
    cleaner = Cleaner()
    cleaner.process([float("nan"), 2.0], header(stamp_ns=1_000), seq=0, declared_frame=FRAME)
    assert cleaner.width is None
    cleaner.process([1.0, 2.0], header(stamp_ns=2_000), seq=1, declared_frame=FRAME)
    assert cleaner.width == 2


def test_a_width_change_resets_the_hold_buffer():
    """Holding across a width change would mix two unrelated quantities."""
    cleaner = primed()
    out = cleaner.process([float("nan"), 2.0], header(stamp_ns=2_000), seq=1, declared_frame=FRAME)
    assert out.header.validity == "missing"
    assert np.isnan(out.values[0])


def test_an_empty_payload_is_rejected_as_missing():
    cleaner = Cleaner()
    out = cleaner.process([], header(), seq=0, declared_frame=FRAME)
    assert not out.forwarded
    assert out.drops == {"missing": 1}


# --- outliers ---------------------------------------------------------------

def test_an_outlier_is_held_from_the_last_good_sample():
    cleaner = primed(sigma=1.0)
    out = cleaner.process(
        [2.0, 2.0, 2.0, 50.0], header(stamp_ns=2_000), seq=1, declared_frame=FRAME
    )
    assert out.values.tolist() == [2.0, 2.0, 2.0, 1.0]
    assert out.drops == {"outlier": 1}


def test_no_sigma_means_no_outlier_rejection():
    cleaner = primed()
    out = cleaner.process([1.0, 1.0, 1.0, 50.0], header(stamp_ns=2_000), seq=1, declared_frame=FRAME)
    assert out.values.tolist() == [1.0, 1.0, 1.0, 50.0]
    assert out.drops == {}


def test_constant_data_has_no_outliers():
    """A zero spread must not divide by itself and condemn everything."""
    cleaner = primed(sigma=1.0)
    out = cleaner.process([5.0] * 4, header(stamp_ns=2_000), seq=1, declared_frame=FRAME)
    assert out.values.tolist() == [5.0] * 4
    assert out.drops == {}


def test_a_single_value_is_never_an_outlier():
    cleaner = Cleaner(sigma=1.0)
    out = cleaner.process([42.0], header(), seq=0, declared_frame=FRAME)
    assert out.values.tolist() == [42.0]


def test_outlier_detection_is_skipped_while_a_value_is_unrepaired():
    """A NaN left in place would make the mean and spread meaningless."""
    cleaner = Cleaner(sigma=1.0)
    out = cleaner.process(
        [float("nan"), 1.0, 1.0, 50.0], header(), seq=0, declared_frame=FRAME
    )
    assert out.drops == {"missing": 1}
    assert "outlier" not in out.drops


@pytest.mark.parametrize("bad", [0.0, -1.0, float("nan")])
def test_a_bad_sigma_is_rejected_at_construction(bad):
    with pytest.raises(ValueError, match="sigma"):
        Cleaner(sigma=bad)


# --- duplicates -------------------------------------------------------------

def test_a_repeated_capture_is_dropped_and_counted():
    cleaner = Cleaner()
    first = cleaner.process([1.0], header(stamp_ns=1_000), seq=0, declared_frame=FRAME)
    second = cleaner.process([1.0], header(stamp_ns=1_000), seq=1, declared_frame=FRAME)
    assert first.forwarded and not second.forwarded
    assert second.drops == {"duplicate": 1}


def test_duplicates_are_keyed_on_source_as_well_as_time():
    """Two sensors may legitimately capture at the same instant."""
    cleaner = Cleaner()
    cleaner.process([1.0], header(stamp_ns=1_000, source="lidar.front"), seq=0, declared_frame=FRAME)
    other = cleaner.process(
        [1.0], header(stamp_ns=1_000, source="lidar.rear"), seq=1, declared_frame=FRAME
    )
    assert other.forwarded
    assert cleaner.counters.drops_by_reason == {}


def test_a_duplicate_is_not_detected_by_seq():
    """seq is restated by every producer, so a duplicated capture arrives with
    a fresh number; only stamp_ns paired with source reveals it."""
    cleaner = Cleaner()
    cleaner.process([1.0], header(stamp_ns=1_000, seq=1), seq=0, declared_frame=FRAME)
    again = cleaner.process([1.0], header(stamp_ns=1_000, seq=999), seq=1, declared_frame=FRAME)
    assert not again.forwarded


def test_duplicate_history_is_bounded():
    cleaner = Cleaner(history=2)
    for stamp in (1_000, 2_000, 3_000):
        cleaner.process([1.0], header(stamp_ns=stamp), seq=0, declared_frame=FRAME)
    # 1_000 has fallen out of the window, but it is still out of order, so the
    # disorder check catches it rather than the duplicate check
    out = cleaner.process([1.0], header(stamp_ns=1_000), seq=0, declared_frame=FRAME)
    assert out.drops == {"disorder": 1}


# --- disorder ---------------------------------------------------------------

def test_a_backwards_timestamp_is_dropped_and_counted():
    cleaner = Cleaner()
    cleaner.process([1.0], header(stamp_ns=2_000), seq=0, declared_frame=FRAME)
    late = cleaner.process([1.0], header(stamp_ns=1_000), seq=1, declared_frame=FRAME)
    assert not late.forwarded
    assert late.drops == {"disorder": 1}


def test_disorder_is_tracked_per_source():
    cleaner = Cleaner()
    cleaner.process([1.0], header(stamp_ns=5_000, source="a"), seq=0, declared_frame=FRAME)
    fresh = cleaner.process([1.0], header(stamp_ns=1_000, source="b"), seq=1, declared_frame=FRAME)
    assert fresh.forwarded


def test_a_rejected_frame_does_not_advance_the_watermark():
    cleaner = Cleaner()
    cleaner.process([1.0], header(stamp_ns=2_000), seq=0, declared_frame=FRAME)
    cleaner.process([1.0], header(stamp_ns=1_000), seq=1, declared_frame=FRAME)
    later = cleaner.process([1.0], header(stamp_ns=3_000), seq=2, declared_frame=FRAME)
    assert later.forwarded


# --- the four buckets stay separate -----------------------------------------

def test_each_defect_lands_in_its_own_bucket():
    cleaner = primed(sigma=1.0)
    cleaner.process([1.0, float("nan"), 1.0, 1.0], header(stamp_ns=2_000), seq=1, declared_frame=FRAME)
    cleaner.process([2.0, 2.0, 2.0, 99.0], header(stamp_ns=3_000), seq=2, declared_frame=FRAME)
    cleaner.process([1.0, 1.0, 1.0, 1.0], header(stamp_ns=3_000), seq=3, declared_frame=FRAME)
    cleaner.process([1.0, 1.0, 1.0, 1.0], header(stamp_ns=500), seq=4, declared_frame=FRAME)
    assert cleaner.counters.drops_by_reason == {
        "missing": 1, "outlier": 1, "duplicate": 1, "disorder": 1,
    }


def test_the_totals_are_never_merged_into_one_number():
    cleaner = primed()
    cleaner.process(
        [float("nan"), float("nan"), 3.0, 4.0], header(stamp_ns=2_000), seq=1, declared_frame=FRAME
    )
    cleaner.process([1.0, 1.0, 1.0, 1.0], header(stamp_ns=2_000), seq=2, declared_frame=FRAME)
    assert cleaner.counters.drops_by_reason == {"missing": 2, "duplicate": 1}
    assert cleaner.counters.total_drops == 3


# --- invariant 2: the only legal upgrade ------------------------------------

def test_a_real_repair_upgrades_the_validity_and_is_counted():
    cleaner = primed()
    degraded = header(stamp_ns=2_000, validity="missing", reason="1 of 4 absent upstream")
    out = cleaner.process([1.0, float("nan"), 3.0, 4.0], degraded, seq=1, declared_frame=FRAME)
    assert out.header.validity == "ok"
    assert out.header.reason is None
    assert cleaner.counters.upgrades_by_reason == {"repaired_missing": 1}


def test_an_upgrade_is_counted_separately_from_the_drops():
    cleaner = primed()
    degraded = header(stamp_ns=2_000, validity="missing", reason="absent upstream")
    cleaner.process([1.0, float("nan"), 3.0, 4.0], degraded, seq=1, declared_frame=FRAME)
    assert cleaner.counters.drops_by_reason == {"missing": 1}
    assert cleaner.counters.upgrades_by_reason == {"repaired_missing": 1}


def test_a_missing_validity_with_nothing_to_repair_is_not_upgraded():
    """Claiming a repair that did not happen would inflate the counter."""
    cleaner = primed()
    degraded = header(stamp_ns=2_000, validity="missing", reason="absent upstream")
    out = cleaner.process([1.0, 2.0, 3.0, 4.0], degraded, seq=1, declared_frame=FRAME)
    assert out.header.validity == "missing"
    assert cleaner.counters.upgrades_by_reason == {}


def test_a_repair_that_could_not_complete_is_not_an_upgrade():
    cleaner = Cleaner()
    degraded = header(validity="missing", reason="absent upstream")
    out = cleaner.process([float("nan"), 2.0], degraded, seq=0, declared_frame=FRAME)
    assert out.header.validity == "missing"
    assert cleaner.counters.upgrades_by_reason == {}


@pytest.mark.parametrize(
    "validity,reason",
    [
        ("stale", "age 300ms > 200ms"),
        ("unpaired", "no partner within 50ms"),
        ("low_confidence", "0.3 < 0.5 threshold"),
        ("rejected", "joint limit exceeded"),
    ],
)
def test_defects_the_cleaner_cannot_fix_are_forwarded_untouched(validity, reason):
    """Age, pairing, confidence and a refusal are not cleanable."""
    cleaner = primed()
    out = cleaner.process(
        [1.0, float("nan"), 3.0, 4.0],
        header(stamp_ns=2_000, validity=validity, reason=reason),
        seq=1,
        declared_frame=FRAME,
    )
    assert out.forwarded
    assert out.header.validity == validity
    assert out.header.reason == reason
    assert cleaner.counters.upgrades_by_reason == {}


# --- the header -------------------------------------------------------------

def test_cleaning_preserves_the_capture_time_and_source():
    out = Cleaner().process(
        [1.0], header(stamp_ns=777_111, source="lidar.rear"), seq=4, declared_frame=FRAME
    )
    assert out.header.stamp_ns == 777_111
    assert out.header.source == "lidar.rear"


def test_cleaning_restates_the_sequence_number():
    out = Cleaner().process([1.0], header(seq=1), seq=42, declared_frame=FRAME)
    assert out.header.seq == 42


def test_cleaning_takes_its_frame_from_the_declaration():
    cleaner = Cleaner()
    same = cleaner.process([1.0], header(stamp_ns=1_000), seq=0, declared_frame=FRAME)
    literal = cleaner.process([1.0], header(stamp_ns=2_000), seq=1, declared_frame="base_link")
    assert same.header.frame_id == "rslidar"
    assert literal.header.frame_id == "base_link"


def test_a_shared_counter_set_can_be_passed_in():
    shared = Counters()
    cleaner = Cleaner(counters=shared)
    cleaner.process([float("nan")], header(), seq=0, declared_frame=FRAME)
    assert shared.drops_by_reason == {"missing": 1}


@pytest.mark.parametrize("bad", [0, -1])
def test_a_non_positive_history_is_rejected(bad):
    with pytest.raises(ValueError, match="history"):
        Cleaner(history=bad)


def test_a_lone_gross_outlier_can_mask_itself_in_a_narrow_vector():
    """A documented limit, not a defect.

    An n-sigma test measures the spread of the very sample it is judging. One
    extreme value in a short vector inflates that spread enough to stay inside
    its own threshold, so the usable sigma depends on the vector width. The
    record generated in Task 17 uses sigma=2.0 for exactly this reason.
    """
    values = [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 500.0]
    lenient = primed(sigma=3.0)
    lenient.process([1.0] * 8, header(stamp_ns=1_500), seq=0, declared_frame=FRAME)
    missed = lenient.process(values, header(stamp_ns=2_000), seq=1, declared_frame=FRAME)
    assert missed.drops == {}, "3 sigma over width 8 cannot see a single gross outlier"

    strict = Cleaner(sigma=2.0)
    strict.process([1.0] * 8, header(stamp_ns=1_000), seq=0, declared_frame=FRAME)
    caught = strict.process(values, header(stamp_ns=2_000), seq=1, declared_frame=FRAME)
    assert caught.drops == {"outlier": 1}
    assert caught.values.tolist()[-1] == 1.0
```
- [ ] **Step 2: Run to verify they fail**

Run: `cd capabilities/data-processing && python3 -m pytest tests/test_cleaner.py -q`
Expected: collection error — the module under test does not exist yet

- [ ] **Step 3: Write `cleaner_op.py`**

`capabilities/data-processing/open_robot_dataproc/clean/cleaner_op.py`:

```python
"""Data cleaning: missing values, outliers, timestamp disorder, duplicate frames.

The four defect classes are counted in four separate buckets. Contract item
16's "对被丢弃的数据计数并上报" has to distinguish a missing value from an
outlier from a disordered timestamp from a duplicate frame, so a single total
would not answer the question at acceptance.

A value-level defect is **repaired in place, never removed**. The elements of
a state vector are positional -- joint 3, velocity x -- so deleting element 2
would silently shift the meaning of every element after it, which is a worse
failure than the defect being repaired and precisely the silent corruption the
contract forbids. The repair holds the last good value at that index, which is
also what makes this the one operator allowed to raise a degraded input to
`ok`: it really did fix the thing that was reported.
"""

from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, Optional, Set, Tuple

import numpy as np

from open_robot_operator.counters import Counters
from open_robot_operator.envelope import Header, Upgrade, derive
from open_robot_operator.wire import output_frame

REASONS = ("missing", "outlier", "disorder", "duplicate")
# A flat float64 scalar stream, which is what as_state gives: the value-level
# checks need one scalar per element, and the header-level checks (disorder,
# duplicate) are independent of the payload type.
SCHEMA = "openrobot.state.vector/1.0.0"
DEFAULT_HISTORY = 256


@dataclass
class Decision:
    """What the cleaner concluded about one message.

    `values` and `header` are None when the message is not forwarded. That is
    not a silent drop: the reason is counted and published on the diagnostics
    port. Invariant 1 governs *degraded* messages, which are always forwarded
    with their validity; a duplicate or disordered frame is *redundant* rather
    than degraded, and removing it is this operator's whole purpose.
    """

    values: Optional[np.ndarray]
    header: Optional[Header]
    drops: Dict[str, int] = field(default_factory=dict)

    @property
    def forwarded(self) -> bool:
        return self.header is not None


class Cleaner:
    def __init__(
        self,
        *,
        sigma: Optional[float] = None,
        counters: Optional[Counters] = None,
        history: int = DEFAULT_HISTORY,
    ) -> None:
        if sigma is not None and (not np.isfinite(sigma) or sigma <= 0):
            raise ValueError(f"sigma must be a positive finite number, got {sigma!r}")
        if history < 1:
            raise ValueError(f"history must be >= 1, got {history}")
        self.sigma = sigma
        self.counters = counters if counters is not None else Counters()
        self._recent: Deque[Tuple[str, int]] = deque(maxlen=history)
        self._recent_set: Set[Tuple[str, int]] = set()
        self._latest: Dict[str, int] = {}
        self._last_good: Optional[np.ndarray] = None

    @property
    def width(self) -> Optional[int]:
        """The payload width the hold buffer is currently sized for."""
        return None if self._last_good is None else int(self._last_good.size)

    def _remember(self, key: Tuple[str, int]) -> None:
        if len(self._recent) == self._recent.maxlen:
            self._recent_set.discard(self._recent[0])
        self._recent.append(key)
        self._recent_set.add(key)

    def _reject(self, reason: str) -> Decision:
        self.counters.count_drop(reason, 1)
        return Decision(None, None, {reason: 1})

    def _repair(self, values: np.ndarray, suspect: np.ndarray, reason: str,
                drops: Dict[str, int]) -> np.ndarray:
        """Hold the last good value wherever `suspect` is True."""
        count = int(suspect.sum())
        if not count:
            return values
        drops[reason] = drops.get(reason, 0) + count
        self.counters.count_drop(reason, count)
        if self._last_good is None:
            return values  # nothing to hold yet; the caller degrades instead
        repaired = values.copy()
        repaired[suspect] = self._last_good[suspect]
        return repaired

    def process(self, values, header: Header, seq: int, declared_frame: str) -> Decision:
        key = (header.source, header.stamp_ns)
        if key in self._recent_set:
            return self._reject("duplicate")

        latest = self._latest.get(header.source)
        if latest is not None and header.stamp_ns < latest:
            return self._reject("disorder")

        array = np.asarray(values, dtype=np.float64).reshape(-1)
        if array.size == 0:
            return self._reject("missing")
        if self._last_good is not None and self._last_good.size != array.size:
            # A width change means a different quantity; holding values across
            # it would mix two unrelated vectors.
            self._last_good = None
        drops: Dict[str, int] = {}

        suspect = ~np.isfinite(array)
        array = self._repair(array, suspect, "missing", drops)

        if self.sigma is not None and array.size > 1:
            finite = np.isfinite(array)
            if finite.all():
                spread = array.std()
                if spread > 0:
                    far = np.abs(array - array.mean()) > self.sigma * spread
                    array = self._repair(array, far, "outlier", drops)

        self._remember(key)
        self._latest[header.source] = header.stamp_ns

        unrepaired = ~np.isfinite(array)
        repaired_anything = bool(drops) and not unrepaired.any()
        if not unrepaired.any():
            self._last_good = array.copy()

        # The cleaner repairs value-level defects, and nothing else. Age,
        # pairing and confidence are not defects it can fix, so those
        # validities are forwarded untouched.
        upgrade = None
        validity, reason = header.validity, header.reason
        if unrepaired.any():
            validity = "missing"
            reason = (
                f"{int(unrepaired.sum())} of {array.size} values are not finite and "
                "no previous good sample exists to hold"
            )
        elif header.validity == "missing" and repaired_anything:
            validity, reason = "ok", None
            upgrade = Upgrade("repaired_missing", self.counters)

        out = derive(
            [header],
            schema=SCHEMA,
            frame_id=output_frame(declared_frame, {"data": header}),
            seq=seq,
            validity=validity,
            reason=reason,
            upgrade=upgrade,
        )
        return Decision(array, out, drops)
```
- [ ] **Step 4: Run to verify they pass**

Run: `cd capabilities/data-processing && python3 -m pytest tests/test_cleaner.py -q`
Expected: PASS, 45 tests (pack cumulative 216)

Two things here were got wrong first and are worth understanding before
touching the code.

**A value-level defect is repaired in place, never removed.** The first
version deleted the offending elements, which changed the payload width
between messages. A state vector's elements are positional — joint 3,
velocity x — so deleting element 2 silently shifts the meaning of every
element after it. That is a worse failure than the defect being repaired, and
it is exactly the silent corruption the contract forbids. The repair holds the
last good value at that index, which is also what makes this the one operator
allowed to raise a degraded input to `ok`: it really did fix the thing that
was reported. With no history to hold from, it says so and degrades instead of
inventing a measurement.

**`Decision(None, None, ...)` is not a breach of invariant 1.** That invariant
governs *degraded* messages, which are always forwarded with their validity. A
duplicate or disordered frame is *redundant* rather than degraded, and removing
it is this operator's purpose; the reason is counted and published on the
diagnostics port, so it is not a silent drop.

`test_a_rejected_frame_does_not_advance_the_watermark` is there because the
obvious implementation updates `_latest` before deciding, which would let one
late frame poison every later one. And
`test_a_lone_gross_outlier_can_mask_itself_in_a_narrow_vector` records a real
limit rather than a defect: an n-sigma test measures the spread of the sample
it is judging, so one extreme value in a short vector inflates that spread
enough to stay inside its own threshold.

- [ ] **Step 5: Commit**

```bash
git add capabilities/data-processing
git commit -m "feat(dataproc): cleaning, four defect classes and four counters"
```

---

## Task 14: ROS 2 format conversion

"通用机器人数据格式" resolves to ROS 2 messages: the only such format with an
existing implementation here, and the only one actually present in the
deployment. This starts from the hand-rolled conversions in
`dora-nav/peception/euclidean_cluster/` — `LidarRawObject_to_ros2.py` (208
lines) and `rgb_pointcloud_to_ros2.py` (95 lines) — whose `frame_id` was
hard-coded where it should have come from the declaration.

**Files:**
- Create: `capabilities/data-processing/open_robot_dataproc/convert/ros2_codec_op.py`
- Test: `capabilities/data-processing/tests/test_ros2_codec.py`

- [ ] **Step 1: Write the failing test**

`capabilities/data-processing/tests/test_ros2_codec.py`:

```python
import numpy as np
import pytest

from open_robot_dataproc.convert.ros2_codec_op import (
    NANOS, from_ros, join_stamp, split_stamp, to_ros,
)
from open_robot_operator.envelope import originate

PC = "openrobot.sensor.point_cloud/1.0.0"


def header(**o):
    base = dict(schema=PC, frame_id="rslidar", seq=7,
                stamp_ns=1_700_000_000_123_456_789, source="lidar.front")
    return originate(**{**base, **o})


# --- the stamp ---------------------------------------------------------------

def test_a_stamp_splits_into_the_ros_pair():
    assert split_stamp(1_500_000_000) == {"sec": 1, "nanosec": 500_000_000}


def test_the_stamp_round_trips_losslessly():
    for stamp_ns in (0, 1, NANOS - 1, NANOS, 1_700_000_000_123_456_789):
        assert join_stamp(split_stamp(stamp_ns)) == stamp_ns


def test_the_nanosecond_part_stays_below_one_second():
    assert split_stamp(1_999_999_999)["nanosec"] == 999_999_999


@pytest.mark.parametrize("bad", [-1, 1.5, True, None])
def test_split_rejects_a_bad_stamp(bad):
    with pytest.raises(ValueError, match="stamp_ns"):
        split_stamp(bad)


@pytest.mark.parametrize("bad", [{"sec": 1}, {"nanosec": 1}, {}, None, 7])
def test_join_rejects_a_malformed_pair(bad):
    with pytest.raises(ValueError):
        join_stamp(bad)


def test_join_rejects_an_overflowing_nanosecond_field():
    with pytest.raises(ValueError, match="nanosec"):
        join_stamp({"sec": 1, "nanosec": NANOS})


@pytest.mark.parametrize("bad", [{"sec": -1, "nanosec": 0}, {"sec": 0, "nanosec": -1}])
def test_join_rejects_negative_components(bad):
    with pytest.raises(ValueError):
        join_stamp(bad)


# --- the round trip, which is the contract promise ---------------------------

def test_every_header_field_survives_a_round_trip():
    """Item 16: 保证字段语义、单位与时间戳在转换前后一致."""
    original = header()
    back, _ = from_ros(to_ros(original, [1.0, 2.0]))
    assert back == original


def test_a_degraded_header_survives_a_round_trip():
    original = header(validity="stale", reason="age 300ms > 200ms")
    back, _ = from_ros(to_ros(original, [1.0]))
    assert back == original
    assert back.reason == "age 300ms > 200ms"


@pytest.mark.parametrize("payload", [[1.0, 2.0], [], None, b"blob"])
def test_the_payload_survives_a_round_trip(payload):
    _, data = from_ros(to_ros(header(), payload))
    assert data == payload


def test_a_numpy_payload_survives_a_round_trip():
    points = np.arange(12, dtype=np.float32)
    _, data = from_ros(to_ros(header(), points))
    assert np.array_equal(data, points)


def test_the_message_is_shaped_for_a_plain_ros_subscriber():
    message = to_ros(header(), [1.0])
    assert set(message) == {"header", "contract", "data"}
    assert set(message["header"]) == {"frame_id", "stamp"}
    assert set(message["header"]["stamp"]) == {"sec", "nanosec"}
    assert message["header"]["frame_id"] == "rslidar"


def test_the_frame_comes_from_the_header_not_a_literal():
    """dora-nav's LidarRawObject_to_ros2.py hard-coded 'rslidar' here."""
    message = to_ros(header(frame_id="camera_front"), [1.0])
    assert message["header"]["frame_id"] == "camera_front"


def test_reason_is_omitted_when_the_message_is_ok():
    assert "reason" not in to_ros(header(), [1.0])["contract"]


def test_extra_ros_fields_pass_through():
    message = to_ros(header(), [1.0], height=8, width=8, point_step=16)
    assert message["height"] == 8 and message["point_step"] == 16


@pytest.mark.parametrize("key", ["header", "contract", "data"])
def test_extra_fields_may_not_shadow_the_structural_keys(key):
    with pytest.raises(ValueError, match="shadow"):
        to_ros(header(), [1.0], **{key: "hijacked"})


# --- reading a foreign publisher --------------------------------------------

def test_a_foreign_message_needs_explicit_fallbacks():
    foreign = {"header": {"frame_id": "rslidar", "stamp": {"sec": 1, "nanosec": 0}}, "data": [1.0]}
    with pytest.raises(ValueError, match="no contract block"):
        from_ros(foreign)


def test_a_foreign_message_reads_with_fallbacks_supplied():
    foreign = {"header": {"frame_id": "rslidar", "stamp": {"sec": 2, "nanosec": 5}}, "data": [1.0]}
    head, data = from_ros(foreign, schema=PC, source="ros2.velodyne", seq=0)
    assert head.stamp_ns == 2 * NANOS + 5
    assert head.source == "ros2.velodyne"
    assert head.validity == "ok"
    assert data == [1.0]


def test_the_error_names_exactly_what_is_missing():
    foreign = {"header": {"frame_id": "f", "stamp": {"sec": 1, "nanosec": 0}}}
    with pytest.raises(ValueError, match=r"\['source'\]"):
        from_ros(foreign, schema=PC, seq=0)


def test_a_contract_block_wins_over_the_fallbacks():
    message = to_ros(header(source="lidar.front"), [1.0])
    back, _ = from_ros(message, schema="other/9.9.9", source="wrong", seq=999)
    assert back.source == "lidar.front"
    assert back.seq == 7


@pytest.mark.parametrize("bad", [
    {}, None, {"data": [1.0]},
    {"header": {"frame_id": "f"}},
    {"header": {"stamp": {"sec": 1, "nanosec": 0}}},
    {"header": "not a mapping"},
])
def test_a_malformed_ros_message_is_rejected(bad):
    with pytest.raises(ValueError):
        from_ros(bad, schema=PC, source="s", seq=0)
```
- [ ] **Step 2: Run to verify they fail**

Run: `cd capabilities/data-processing && python3 -m pytest tests/test_ros2_codec.py -q`
Expected: collection error — the module under test does not exist yet

- [ ] **Step 3: Write `ros2_codec_op.py`**

`capabilities/data-processing/open_robot_dataproc/convert/ros2_codec_op.py`:

```python
"""Bidirectional conversion between the contract envelope and ROS 2 messages.

"通用机器人数据格式" resolves to ROS 2 messages: the only such format with an
existing implementation here, and the only one actually present in the
deployment. This starts from the hand-rolled conversions in
dora-nav/peception/euclidean_cluster/ (LidarRawObject_to_ros2.py and
rgb_pointcloud_to_ros2.py), whose frame_id was hard-coded rather than taken
from the declaration.

ROS 2 dropped the `seq` field that ROS 1 had, and it never carried a schema
id, an origin or a validity. Those live in a `contract` block alongside the
standard `header`, so a round trip is exact while a plain ROS 2 subscriber
still finds everything it expects under `header` and `data`. A message from a
foreign ROS 2 publisher has no `contract` block, so reading one requires
explicit fallbacks -- that asymmetry is real and is not papered over.
"""

from typing import Any, Dict, Optional, Tuple

from open_robot_operator.envelope import Header, originate

NANOS = 1_000_000_000


def split_stamp(stamp_ns: int) -> Dict[str, int]:
    """Split a nanosecond stamp into the ROS 2 {sec, nanosec} pair."""
    if isinstance(stamp_ns, bool) or not isinstance(stamp_ns, int) or stamp_ns < 0:
        raise ValueError(f"stamp_ns must be a non-negative int, got {stamp_ns!r}")
    return {"sec": stamp_ns // NANOS, "nanosec": stamp_ns % NANOS}


def join_stamp(stamp: Dict[str, int]) -> int:
    """Rejoin a ROS 2 {sec, nanosec} pair into nanoseconds."""
    if not isinstance(stamp, dict) or "sec" not in stamp or "nanosec" not in stamp:
        raise ValueError(f"a ROS 2 stamp needs sec and nanosec, got {stamp!r}")
    sec, nanosec = stamp["sec"], stamp["nanosec"]
    for name, value in (("sec", sec), ("nanosec", nanosec)):
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"{name} must be a non-negative int, got {value!r}")
    if nanosec >= NANOS:
        raise ValueError(f"nanosec must be below {NANOS}, got {nanosec}")
    return sec * NANOS + nanosec


def to_ros(header: Header, data: Any, /, **fields: Any) -> Dict[str, Any]:
    """Render a contract message as a ROS 2 message dict.

    The first two parameters are positional-only so that a caller passing
    `header=` or `data=` as an extra ROS field reaches the collision guard
    below instead of colliding with the signature and raising TypeError.
    """
    reserved = sorted({"header", "contract", "data"} & set(fields))
    if reserved:
        raise ValueError(f"extra fields may not shadow {reserved}")
    contract = {
        "schema": header.schema,
        "seq": header.seq,
        "source": header.source,
        "validity": header.validity,
    }
    if header.reason is not None:
        contract["reason"] = header.reason
    message = {
        "header": {"frame_id": header.frame_id, "stamp": split_stamp(header.stamp_ns)},
        "contract": contract,
        "data": data,
    }
    message.update(fields)
    return message


def from_ros(
    message: Dict[str, Any],
    *,
    schema: Optional[str] = None,
    source: Optional[str] = None,
    seq: Optional[int] = None,
) -> Tuple[Header, Any]:
    """Read a ROS 2 message dict back into a header and its payload.

    A message this codec produced round-trips exactly. A message from a
    foreign publisher has no `contract` block, so `schema`, `source` and `seq`
    must be supplied; they describe what the integrator knows about that
    publisher and cannot be guessed.
    """
    if not isinstance(message, dict) or "header" not in message:
        raise ValueError(f"a ROS 2 message needs a header, got {message!r}")
    ros_header = message["header"]
    if not isinstance(ros_header, dict) or "frame_id" not in ros_header or "stamp" not in ros_header:
        raise ValueError(f"a ROS 2 header needs frame_id and stamp, got {ros_header!r}")

    contract = message.get("contract") or {}
    resolved_schema = contract.get("schema", schema)
    resolved_source = contract.get("source", source)
    resolved_seq = contract.get("seq", seq)
    missing = [
        name
        for name, value in (
            ("schema", resolved_schema), ("source", resolved_source), ("seq", resolved_seq)
        )
        if value is None
    ]
    if missing:
        raise ValueError(
            f"this message carries no contract block, so {missing} must be supplied; "
            "a foreign ROS 2 publisher states none of them"
        )
    header = originate(
        schema=resolved_schema,
        frame_id=ros_header["frame_id"],
        seq=resolved_seq,
        stamp_ns=join_stamp(ros_header["stamp"]),
        source=resolved_source,
        validity=contract.get("validity", "ok"),
        reason=contract.get("reason"),
    )
    return header, message.get("data")
```
- [ ] **Step 4: Run to verify they pass**

Run: `cd capabilities/data-processing && python3 -m pytest tests/test_ros2_codec.py -q`
Expected: PASS, 39 tests (pack cumulative 255)

ROS 2 dropped the `seq` field ROS 1 had, and it never carried a schema id, an
origin or a validity. Those live in a `contract` block beside the standard
`header`, so the round trip is exact while a plain ROS 2 subscriber still
finds what it expects under `header` and `data`. A message from a foreign
publisher has no `contract` block, so reading one needs explicit fallbacks:
that asymmetry is real, `test_a_foreign_message_needs_explicit_fallbacks`
states it, and guessing an origin would be worse than refusing.

`to_ros` takes its first two parameters positionally only. Without that, a
caller passing `header=` as an extra ROS field collides with the signature
and raises `TypeError` instead of reaching the collision guard — which is
exactly what happened the first time this was written.

- [ ] **Step 5: Commit**

```bash
git add capabilities/data-processing
git commit -m "feat(dataproc): bidirectional ROS 2 conversion with an exact round trip"
```

---

## Task 15: The chain tools

The per-stage aggregation of contract item 16's "逐级统计数据量削减比例与处理
耗时", and the comparison behind "支持以同一输入对比启用前后的下游算子输出".
Both expose pure functions plus a `render` that produces the delivered
record. `diag_collector` also runs as a node, because it has to subscribe to
the live diagnostics ports; `ab_compare` stays a script, since comparing two
recorded streams needs no port of its own.

**Files:**
- Create: `capabilities/data-processing/open_robot_dataproc/tools/diag_collector.py`
- Create: `capabilities/data-processing/open_robot_dataproc/tools/ab_compare.py`
- Test: `capabilities/data-processing/tests/test_tools.py`

- [ ] **Step 1: Write the failing test**

`capabilities/data-processing/tests/test_tools.py`:

```python
import numpy as np
import pytest

from open_robot_dataproc.tools.ab_compare import compare
from open_robot_dataproc.tools.ab_compare import render as render_compare
from open_robot_dataproc.tools.diag_collector import chain_report, render
from open_robot_operator.counters import Counters


def snapshot(*, in_items=0, out_items=0, in_bytes=0, out_bytes=0, proc_ns=0, drops=None, upgrades=None):
    counters = Counters()
    if in_items or in_bytes:
        counters.observe_in(items=in_items, nbytes=in_bytes)
    if out_items or out_bytes:
        counters.observe_out(items=out_items, nbytes=out_bytes)
    if proc_ns:
        counters.observe_proc(ns=proc_ns)
    for reason, count in (drops or {}).items():
        counters.count_drop(reason, count)
    for reason in (upgrades or []):
        counters.count_upgrade(reason)
    return counters.snapshot()


# --- diag collector ----------------------------------------------------------

def test_the_chain_ratio_is_the_product_of_the_stage_ratios():
    stages = [
        ("voxel", snapshot(in_items=1000, out_items=500, in_bytes=16000, out_bytes=8000)),
        ("compress", snapshot(in_items=500, out_items=500, in_bytes=8000, out_bytes=2000)),
    ]
    report = chain_report(stages)
    assert report["chain_byte_ratio"] == pytest.approx(0.5 * 0.25)
    assert report["chain_item_ratio"] == pytest.approx(0.5 * 1.0)


def test_the_reduction_is_the_complement_of_the_ratio():
    stages = [("voxel", snapshot(in_items=10, out_items=5, in_bytes=100, out_bytes=25))]
    assert chain_report(stages)["chain_byte_reduction"] == pytest.approx(0.75)


def test_processing_time_sums_across_stages():
    stages = [
        ("a", snapshot(in_bytes=10, out_bytes=5, proc_ns=1_000_000)),
        ("b", snapshot(in_bytes=5, out_bytes=5, proc_ns=2_500_000)),
    ]
    assert chain_report(stages)["total_proc_ns"] == 3_500_000


def test_a_stage_that_saw_no_input_leaves_the_chain_ratio_unmeasured():
    """An absent measurement must not read as a 100% reduction."""
    stages = [
        ("voxel", snapshot(in_items=10, out_items=5, in_bytes=100, out_bytes=50)),
        ("idle", snapshot()),
    ]
    report = chain_report(stages)
    assert report["chain_byte_ratio"] is None
    assert report["chain_byte_reduction"] is None


def test_drops_are_attributed_to_their_stage_and_reason():
    stages = [
        ("clean", snapshot(in_bytes=10, out_bytes=8, drops={"missing": 2, "duplicate": 1})),
        ("voxel", snapshot(in_bytes=8, out_bytes=4, drops={"downsampled": 40})),
    ]
    report = chain_report(stages)
    assert report["drops_by_stage"] == {
        "clean": {"missing": 2, "duplicate": 1},
        "voxel": {"downsampled": 40},
    }
    assert report["total_drops"] == 43


def test_upgrades_are_reported_per_stage():
    stages = [("clean", snapshot(in_bytes=10, out_bytes=10, upgrades=["repaired_missing"]))]
    assert chain_report(stages)["upgrades_by_stage"] == {"clean": {"repaired_missing": 1}}


def test_a_stage_with_no_drops_is_absent_rather_than_zero():
    stages = [("voxel", snapshot(in_bytes=10, out_bytes=5))]
    assert chain_report(stages)["drops_by_stage"] == {}


def test_the_stage_order_is_preserved():
    stages = [(name, snapshot(in_bytes=10, out_bytes=10)) for name in ("c", "a", "b")]
    assert [s["stage"] for s in chain_report(stages)["stages"]] == ["c", "a", "b"]


def test_an_empty_chain_is_rejected():
    with pytest.raises(ValueError, match="at least one stage"):
        chain_report([])


def test_duplicate_stage_names_are_rejected():
    stages = [("voxel", snapshot(in_bytes=1, out_bytes=1))] * 2
    with pytest.raises(ValueError, match="unique"):
        chain_report(stages)


def test_the_rendered_report_names_every_stage_and_the_chain_ratio():
    stages = [
        ("voxel", snapshot(in_items=1000, out_items=500, in_bytes=16000, out_bytes=8000, proc_ns=2_000_000)),
        ("compress", snapshot(in_items=500, out_items=500, in_bytes=8000, out_bytes=2000, proc_ns=5_000_000)),
    ]
    text = render(chain_report(stages))
    assert "voxel" in text and "compress" in text
    assert "0.1250" in text
    assert "87.5% reduction" in text
    assert "7.00 ms" in text


def test_the_rendered_report_says_so_when_nothing_was_measured():
    text = render(chain_report([("idle", snapshot())]))
    assert "not measured" in text


def test_the_rendered_report_lists_drops_by_reason():
    stages = [("clean", snapshot(in_bytes=10, out_bytes=8, drops={"missing": 2, "duplicate": 1}))]
    text = render(chain_report(stages))
    assert "missing" in text and "duplicate" in text


# --- ab compare --------------------------------------------------------------

def test_identical_outputs_differ_by_nothing():
    result = compare([1.0, 2.0, 3.0], [1.0, 2.0, 3.0])
    assert result["comparable"] is True
    assert result["max_abs_diff"] == 0.0
    assert result["within_tolerance"] is True


def test_a_difference_is_measured():
    result = compare([1.0, 2.0], [1.0, 2.5])
    assert result["max_abs_diff"] == pytest.approx(0.5)
    assert result["mean_abs_diff"] == pytest.approx(0.25)


def test_a_tolerance_decides_the_verdict():
    assert compare([1.0], [1.4], tolerance=0.5)["within_tolerance"] is True
    assert compare([1.0], [1.6], tolerance=0.5)["within_tolerance"] is False


def test_a_zero_tolerance_demands_equality():
    assert compare([1.0], [1.0])["within_tolerance"] is True
    assert compare([1.0], [1.000001])["within_tolerance"] is False


def test_a_length_change_is_reported_rather_than_compared():
    """Preprocessing that removes samples is working as intended."""
    result = compare([1.0, 2.0, 3.0, 4.0], [1.0, 2.0])
    assert result["comparable"] is False
    assert result["item_ratio"] == pytest.approx(0.5)
    assert result["max_abs_diff"] is None
    assert result["within_tolerance"] is None


def test_two_empty_outputs_compare_equal():
    result = compare([], [])
    assert result["comparable"] is True
    assert result["max_abs_diff"] == 0.0


def test_an_empty_baseline_has_no_ratio():
    assert compare([], [1.0])["item_ratio"] is None


def test_numpy_inputs_are_accepted():
    result = compare(np.zeros(4), np.zeros(4, dtype=np.float32))
    assert result["max_abs_diff"] == 0.0


def test_multidimensional_inputs_are_flattened():
    result = compare(np.zeros((2, 3)), np.zeros(6))
    assert result["comparable"] is True


@pytest.mark.parametrize("bad", [-0.1, float("nan"), float("inf")])
def test_a_bad_tolerance_is_rejected(bad):
    with pytest.raises(ValueError, match="tolerance"):
        compare([1.0], [1.0], tolerance=bad)


def test_the_rendered_comparison_states_the_verdict():
    text = render_compare(compare([1.0, 2.0], [1.0, 2.4], tolerance=0.5))
    assert "within tolerance: True" in text
    assert "max abs diff" in text


def test_the_rendered_comparison_explains_a_length_change():
    text = render_compare(compare([1.0, 2.0, 3.0], [1.0]))
    assert "lengths differ" in text
    assert "expected to do this" in text
```
- [ ] **Step 2: Run to verify they fail**

Run: `cd capabilities/data-processing && python3 -m pytest tests/test_tools.py -q`
Expected: collection error — the module under test does not exist yet

- [ ] **Step 3: Write `diag_collector.py`**

`capabilities/data-processing/open_robot_dataproc/tools/diag_collector.py`:

```python
"""Aggregate the per-stage diagnostics into a chain report.

Contract item 16's "逐级统计数据量削减比例与处理耗时". The chain ratio is the
product of the per-stage ratios, so nothing here correlates individual
messages; that would need a header trail growing without bound with the chain
length.
"""

from typing import Dict, List, Optional, Sequence, Tuple


def chain_report(stages: Sequence[Tuple[str, Dict]]) -> Dict:
    """Combine ordered (stage name, counters snapshot) pairs."""
    if not stages:
        raise ValueError("a chain report needs at least one stage")
    names = [name for name, _ in stages]
    if len(names) != len(set(names)):
        raise ValueError(f"stage names must be unique, got {names}")

    per_stage: List[Dict] = []
    chain_bytes: Optional[float] = 1.0
    chain_items: Optional[float] = 1.0
    drops: Dict[str, Dict[str, int]] = {}
    upgrades: Dict[str, Dict[str, int]] = {}
    total_proc_ns = 0

    for name, snapshot in stages:
        byte_ratio = snapshot.get("byte_ratio")
        item_ratio = snapshot.get("item_ratio")
        # A stage that saw no input has no ratio, and a missing measurement
        # must not be read as a 100% reduction.
        chain_bytes = None if byte_ratio is None or chain_bytes is None else chain_bytes * byte_ratio
        chain_items = None if item_ratio is None or chain_items is None else chain_items * item_ratio
        total_proc_ns += int(snapshot.get("proc_ns", 0))
        if snapshot.get("drops_by_reason"):
            drops[name] = dict(snapshot["drops_by_reason"])
        if snapshot.get("upgrades_by_reason"):
            upgrades[name] = dict(snapshot["upgrades_by_reason"])
        per_stage.append(
            {
                "stage": name,
                "in_bytes": snapshot.get("in_bytes", 0),
                "out_bytes": snapshot.get("out_bytes", 0),
                "in_items": snapshot.get("in_items", 0),
                "out_items": snapshot.get("out_items", 0),
                "byte_ratio": byte_ratio,
                "item_ratio": item_ratio,
                "proc_ns": snapshot.get("proc_ns", 0),
            }
        )

    return {
        "stages": per_stage,
        "chain_byte_ratio": chain_bytes,
        "chain_item_ratio": chain_items,
        "chain_byte_reduction": None if chain_bytes is None else 1.0 - chain_bytes,
        "total_proc_ns": total_proc_ns,
        "drops_by_stage": drops,
        "upgrades_by_stage": upgrades,
        "total_drops": sum(sum(b.values()) for b in drops.values()),
    }


def render(report: Dict) -> str:
    """A plain-text table, which is what goes into the delivered record."""
    lines = [f"{'stage':<24}{'in B':>12}{'out B':>12}{'bytes':>9}{'items':>9}{'ms':>9}"]
    for stage in report["stages"]:
        byte_ratio = "-" if stage["byte_ratio"] is None else f"{stage['byte_ratio']:.3f}"
        item_ratio = "-" if stage["item_ratio"] is None else f"{stage['item_ratio']:.3f}"
        lines.append(
            f"{stage['stage']:<24}{stage['in_bytes']:>12}{stage['out_bytes']:>12}"
            f"{byte_ratio:>9}{item_ratio:>9}{stage['proc_ns'] / 1e6:>9.2f}"
        )
    chain = report["chain_byte_ratio"]
    lines.append("")
    lines.append(
        "chain byte ratio: "
        + ("not measured" if chain is None else f"{chain:.4f} ({(1 - chain) * 100:.1f}% reduction)")
    )
    lines.append(f"total processing:  {report['total_proc_ns'] / 1e6:.2f} ms")
    if report["drops_by_stage"]:
        lines.append("drops:")
        for stage, reasons in report["drops_by_stage"].items():
            for reason, count in sorted(reasons.items()):
                lines.append(f"  {stage:<22}{reason:<14}{count}")
    return "\n".join(lines)
```
- [ ] **Step 4: Write `ab_compare.py`**

`capabilities/data-processing/open_robot_dataproc/tools/ab_compare.py`:

```python
"""Compare one input's downstream output with and without the preprocessing chain.

Contract item 16's "支持以同一输入对比启用前后的下游算子输出". This is a
comparison node plus an orchestration example, not a framework.
"""

from typing import Dict

import numpy as np


def compare(baseline, treated, *, tolerance: float = 0.0) -> Dict:
    """Describe how a treated output differs from the bypassed baseline."""
    if not np.isfinite(tolerance) or tolerance < 0:
        raise ValueError(f"tolerance must be a non-negative finite number, got {tolerance!r}")
    left = np.asarray(baseline, dtype=np.float64).reshape(-1)
    right = np.asarray(treated, dtype=np.float64).reshape(-1)

    result = {
        "baseline_items": int(left.size),
        "treated_items": int(right.size),
        "item_ratio": None if left.size == 0 else right.size / left.size,
        "comparable": left.size == right.size,
    }
    if left.size != right.size:
        # Preprocessing that removes samples is working as intended, so a
        # length change is reported rather than treated as a failure.
        result.update({"max_abs_diff": None, "mean_abs_diff": None, "within_tolerance": None})
        return result

    if left.size == 0:
        result.update({"max_abs_diff": 0.0, "mean_abs_diff": 0.0, "within_tolerance": True})
        return result

    difference = np.abs(right - left)
    max_abs = float(difference.max())
    result.update(
        {
            "max_abs_diff": max_abs,
            "mean_abs_diff": float(difference.mean()),
            "within_tolerance": bool(max_abs <= tolerance),
        }
    )
    return result


def render(result: Dict) -> str:
    lines = [
        f"baseline items: {result['baseline_items']}",
        f"treated items:  {result['treated_items']}",
    ]
    if result["item_ratio"] is not None:
        lines.append(f"item ratio:     {result['item_ratio']:.4f}")
    if not result["comparable"]:
        lines.append("lengths differ, so the samples were not compared pairwise;")
        lines.append("preprocessing that removes samples is expected to do this.")
        return "\n".join(lines)
    lines.append(f"max abs diff:   {result['max_abs_diff']:.6g}")
    lines.append(f"mean abs diff:  {result['mean_abs_diff']:.6g}")
    lines.append(f"within tolerance: {result['within_tolerance']}")
    return "\n".join(lines)
```
- [ ] **Step 5: Run to verify they pass**

Run: `cd capabilities/data-processing && python3 -m pytest tests/test_tools.py -q`
Expected: PASS, 27 tests (pack cumulative 282)

Two `None` cases carry weight. A stage that saw no input has no ratio, and
`chain_report` propagates that as `None` instead of folding it in as a 100%
reduction — an absent measurement is not a perfect one. And in `compare`, a
length change is reported rather than scored, because preprocessing that
removes samples is working as intended; scoring it as a failure would make
the comparison useless for the thing it exists to measure.

- [ ] **Step 6: Commit**

```bash
git add capabilities/data-processing
git commit -m "feat(dataproc): per-stage chain statistics and A/B comparison"
```

---

## Task 16: The mocks, the orchestration examples, and conformance

This is the layer that turns drift between the declarations and the
orchestration into a CI failure rather than an on-robot discovery. The mock
sources exist so the examples form a complete, checkable graph, and they are
declared outside the pack's own registry because a mock lidar is not a
capability anyone deploys.

**Files:**
- Create: three modules under `capabilities/data-processing/open_robot_dataproc/mocks/`
- Create: `capabilities/data-processing/dataflows/mocks/operators.yaml`
- Create: `capabilities/data-processing/dataflows/preprocess-chain.yml`, `dataflows/ab-compare.yml`
- Test: `capabilities/data-processing/tests/test_conformance.py`

- [ ] **Step 1: Write the mock point-cloud source**

`capabilities/data-processing/open_robot_dataproc/mocks/point_cloud_source.py`:

```python
"""A deterministic point-cloud source for the orchestration examples."""

import numpy as np

from open_robot_operator.envelope import Header, originate

SCHEMA = "openrobot.sensor.point_cloud/1.0.0"
FRAME = "rslidar"
SOURCE = "mock.lidar"


def frame(seq: int, *, points: int = 2048, stamp_ns: int = None, seed: int = 0):
    """One synthetic cloud and its header. Deterministic for a given seq."""
    if seq < 0:
        raise ValueError(f"seq must be >= 0, got {seq}")
    rng = np.random.default_rng(seed + seq)
    cloud = rng.uniform(-10.0, 10.0, points * 4).astype(np.float32).reshape(-1, 4)
    header = originate(
        schema=SCHEMA,
        frame_id=FRAME,
        seq=seq,
        stamp_ns=stamp_ns if stamp_ns is not None else 1_700_000_000_000_000_000 + seq * 100_000_000,
        source=SOURCE,
    )
    return cloud, header


def main() -> None:  # pragma: no cover - needs the dora runtime
    from dora import Node

    from open_robot_operator.wire import header_to_metadata

    node = Node()
    seq = 0
    for event in node:
        if event["type"] == "INPUT":
            cloud, header = frame(seq)
            import pyarrow as pa

            node.send_output(
                "cloud",
                pa.array(cloud.reshape(-1)),
                metadata=header_to_metadata(header, item_step=4),
            )
            seq += 1


if __name__ == "__main__":  # pragma: no cover
    main()
```
- [ ] **Step 2: Write the mock state source**

`capabilities/data-processing/open_robot_dataproc/mocks/state_source.py`:

```python
"""A state source that injects the four defect classes on a fixed schedule.

The ab-compare example needs defects to exist, otherwise the cleaned and the
bypassed branch are identical and the comparison proves nothing.
"""

import numpy as np

from open_robot_operator.envelope import originate

SCHEMA = "openrobot.state.vector/1.0.0"
FRAME = "base_link"
SOURCE = "mock.state"
BASE_STAMP = 1_700_000_000_000_000_000
STEP_NS = 10_000_000  # 100 Hz


def frame(seq: int, *, width: int = 8, seed: int = 0):
    """One sample and its header.

    Every 5th sample carries a NaN, every 7th an extreme outlier, every 11th
    repeats the previous stamp, and every 13th steps the stamp backwards.
    """
    if seq < 0:
        raise ValueError(f"seq must be >= 0, got {seq}")
    rng = np.random.default_rng(seed + seq)
    values = rng.normal(0.0, 1.0, width)
    validity, reason = "ok", None
    if seq % 5 == 0:
        values[0] = np.nan
        # An honest upstream reports what it knows is absent, which is what
        # gives the cleaner something legitimate to upgrade.
        validity, reason = "missing", "sample 0 was not read this cycle"
    stamp_ns = BASE_STAMP + seq * STEP_NS
    if seq % 11 == 0 and seq > 0:
        stamp_ns -= STEP_NS       # a duplicate capture time
    elif seq % 13 == 0 and seq > 0:
        stamp_ns -= 5 * STEP_NS   # out of order
    if seq % 7 == 0:
        values[-1] = 500.0
    header = originate(
        schema=SCHEMA, frame_id=FRAME, seq=seq, stamp_ns=stamp_ns, source=SOURCE,
        validity=validity, reason=reason,
    )
    return values, header


def main() -> None:  # pragma: no cover - needs the dora runtime
    from dora import Node
    import pyarrow as pa

    from open_robot_operator.wire import header_to_metadata

    node = Node()
    seq = 0
    for event in node:
        if event["type"] == "INPUT":
            values, header = frame(seq)
            node.send_output("state", pa.array(values), metadata=header_to_metadata(header))
            seq += 1


if __name__ == "__main__":  # pragma: no cover
    main()
```

The defect schedule is the point. Without planted defects the cleaned and
the bypassed branch are identical and the A/B comparison proves nothing.
- [ ] **Step 3: Write the mock state sink**

`capabilities/data-processing/open_robot_dataproc/mocks/state_sink.py`:

```python
"""A sink that records what it received, so two branches can be compared."""

from typing import List, Tuple

import numpy as np

from open_robot_operator.envelope import Header, derive
from open_robot_operator.wire import output_frame

SCHEMA = "openrobot.state.vector/1.0.0"


class Recorder:
    """Accumulates the samples one branch produced."""

    def __init__(self, label: str) -> None:
        if not label:
            raise ValueError("a recorder needs a label to tell the branches apart")
        self.label = label
        self._samples: List[np.ndarray] = []
        self._headers: List[Header] = []

    @property
    def count(self) -> int:
        return len(self._samples)

    def record(self, values, header: Header, seq: int, declared_frame: str) -> Tuple[np.ndarray, Header]:
        array = np.asarray(values, dtype=np.float64).reshape(-1)
        self._samples.append(array)
        self._headers.append(header)
        out = derive(
            [header],
            schema=SCHEMA,
            frame_id=output_frame(declared_frame, {"state": header}),
            seq=seq,
            validity=header.validity,
            reason=header.reason,
        )
        return array, out

    def flat(self) -> np.ndarray:
        """Everything recorded, concatenated, for ab_compare."""
        if not self._samples:
            return np.zeros(0, dtype=np.float64)
        return np.concatenate(self._samples)


def main() -> None:  # pragma: no cover - needs the dora runtime
    import os

    from dora import Node
    import pyarrow as pa

    from open_robot_operator.wire import SeqSource, header_to_metadata, metadata_to_header

    node = Node()
    recorder = Recorder(os.environ.get("LABEL", "unlabelled"))
    seq = SeqSource()
    for event in node:
        if event["type"] == "INPUT":
            header = metadata_to_header(event["metadata"])
            values, out = recorder.record(
                event["value"].to_numpy(), header, seq.take(), "same_as:state"
            )
            node.send_output("recorded", pa.array(values), metadata=header_to_metadata(out))


if __name__ == "__main__":  # pragma: no cover
    main()
```
- [ ] **Step 4: Declare the mocks**

`capabilities/data-processing/dataflows/mocks/operators.yaml`:

```yaml
# Mock sources and sinks the orchestration examples need in order to be a
# complete, checkable graph.
#
# They live here rather than in the pack's own operators.yaml because that
# file is the registry of what the pack PROVIDES, and a mock lidar is not a
# capability anyone deploys. The conformance check passes both directories.
contract_version: 1.0.0

operators:
  - name: mock_point_cloud_source
    module: open_robot_dataproc.mocks.point_cloud_source
    inputs: {}
    outputs:
      cloud:
        schema: openrobot.sensor.point_cloud/1.0.0
        frame: rslidar

  - name: mock_state_source
    module: open_robot_dataproc.mocks.state_source
    inputs: {}
    outputs:
      state:
        schema: openrobot.state.vector/1.0.0
        frame: base_link

  - name: mock_state_sink
    module: open_robot_dataproc.mocks.state_sink
    inputs:
      state:
        schema: openrobot.state.vector/^1.0
        frame: any
    outputs:
      recorded:
        schema: openrobot.state.vector/1.0.0
        frame: same_as:state
```
- [ ] **Step 5: Write the preprocessing chain**

`capabilities/data-processing/dataflows/preprocess-chain.yml`:

```yaml
# The preprocessing chain of contract item 16: filter, then compress, with
# every stage's diagnostics collected so the per-stage reduction ratios and
# latencies can be reported.
#
# Deliberately not runnable against a real sensor: the source nodes are mocks,
# because the installed dora binding is 0.2.6 against a 1.0.1 pin and no task
# in this plan starts a dataflow. What this file is for is the conformance
# check -- the validator reads it and must report zero violations.
nodes:
  - id: mock_lidar
    path: dynamic
    env:
      OPERATOR: mock_point_cloud_source
    outputs: [cloud]

  - id: voxel
    path: dynamic
    env:
      OPERATOR: point_cloud_filter
      MODE: voxel
      LEAF_SIZE: "0.05"
    inputs:
      cloud: mock_lidar/cloud
    outputs: [cloud, diag]

  - id: outlier
    path: dynamic
    env:
      OPERATOR: point_cloud_filter
      MODE: outlier
      NEIGHBOURS: "8"
      SIGMA: "1.0"
    inputs:
      cloud: voxel/cloud
    outputs: [cloud, diag]

  - id: squeeze
    path: dynamic
    env:
      OPERATOR: point_cloud_compress
      LOSSY: "true"
      PRECISION: "0.01"
    inputs:
      cloud: outlier/cloud
    outputs: [blob, diag]

  - id: chain_diag
    path: dynamic
    env:
      OPERATOR: diag_collector
    inputs:
      stage_1: voxel/diag
      stage_2: outlier/diag
      stage_3: squeeze/diag
    outputs: [report]
```
- [ ] **Step 6: Write the A/B comparison flow**

`capabilities/data-processing/dataflows/ab-compare.yml`:

```yaml
# Contract item 16's "支持以同一输入对比启用前后的下游算子输出": one source
# feeds two branches, one through the cleaning and filtering chain and one
# bypassing it, and the recorded outputs are compared by
# open_robot_dataproc.tools.ab_compare.
#
# ab_compare itself is a script rather than a node: the contract asks for the
# comparison to be supported, and comparing two recorded streams needs no
# port of its own.
nodes:
  - id: mock_state
    path: dynamic
    env:
      OPERATOR: mock_state_source
    outputs: [state]

  # treated branch: clean, then smooth
  - id: cleaner
    path: dynamic
    env:
      OPERATOR: data_cleaner
      SIGMA: "3.0"
    inputs:
      data: mock_state/state
    outputs: [data, diag]

  - id: smooth
    path: dynamic
    env:
      OPERATOR: state_filter
      MODE: moving_average
      WINDOW: "5"
    inputs:
      state: cleaner/data
    outputs: [state, diag]

  # bypass branch: the same source, recorded untouched
  - id: recorder_treated
    path: dynamic
    env:
      OPERATOR: mock_state_sink
      LABEL: treated
    inputs:
      state: smooth/state

  - id: recorder_baseline
    path: dynamic
    env:
      OPERATOR: mock_state_sink
      LABEL: baseline
    inputs:
      state: mock_state/state

  - id: chain_diag
    path: dynamic
    env:
      OPERATOR: diag_collector
    inputs:
      stage_1: cleaner/diag
      stage_2: smooth/diag
    outputs: [report]
```
- [ ] **Step 7: Write the conformance suite**

`capabilities/data-processing/tests/test_conformance.py`:

```python
"""The validator, run as a test.

This is the layer that turns drift between the declarations and the
orchestration into a CI failure rather than an on-robot discovery. It also
checks the manifests themselves and that every declared module is importable,
because a mistyped module path otherwise surfaces only at launch.
"""

import ast
import importlib
from pathlib import Path

import pytest
import yaml

from open_robot_operator.declare import load_operators
from open_robot_operator.validate import load_dataflow, validate_dataflow

PACK = Path(__file__).resolve().parents[1]
MOCKS = PACK / "dataflows" / "mocks"
DATAFLOWS = sorted(PACK.joinpath("dataflows").glob("*.yml"))

DECLS = {**load_operators(PACK / "operators.yaml"), **load_operators(MOCKS / "operators.yaml")}
PACK_YAML = yaml.safe_load((PACK / "pack.yaml").read_text(encoding="utf-8"))

EXPECTED = (
    "point_cloud_filter",
    "image_filter",
    "state_filter",
    "point_cloud_compress",
    "image_compress",
    "data_cleaner",
    "ros2_codec",
    "diag_collector",
)


# --- the registry ------------------------------------------------------------

def test_the_pack_declares_the_expected_operators():
    assert tuple(load_operators(PACK / "operators.yaml")) == EXPECTED


def test_the_seven_contract_operators_are_present():
    """Item 16 promises filtering, compression, cleaning and conversion."""
    declared = set(load_operators(PACK / "operators.yaml"))
    assert {"point_cloud_filter", "image_filter", "state_filter"} <= declared
    assert {"point_cloud_compress", "image_compress"} <= declared
    assert "data_cleaner" in declared
    assert "ros2_codec" in declared


def test_mocks_are_declared_outside_the_pack_registry():
    """The registry is what the pack provides; a mock lidar is not that."""
    provided = set(load_operators(PACK / "operators.yaml"))
    assert not any(name.startswith("mock_") for name in provided)
    assert all(name.startswith("mock_") for name in load_operators(MOCKS / "operators.yaml"))


@pytest.mark.parametrize("name", EXPECTED)
def test_every_declared_module_is_importable(name):
    """A mistyped module path would otherwise surface only at launch."""
    importlib.import_module(DECLS[name].module)


@pytest.mark.parametrize("name", sorted(load_operators(MOCKS / "operators.yaml")))
def test_every_mock_module_is_importable(name):
    importlib.import_module(DECLS[name].module)


@pytest.mark.parametrize("name", EXPECTED)
def test_no_operator_module_imports_dora_at_load_time(name):
    """The installed binding is 0.2.6 against a 1.0.1 pin, so the pure
    functions have to stay importable without the runtime. Walking the AST
    rather than grepping: a substring scan cannot tell an import from the word
    appearing in a docstring."""
    module = importlib.import_module(DECLS[name].module)
    tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
    top_level = []
    for node in tree.body:  # only module scope; inside main() is fine
        if isinstance(node, ast.Import):
            top_level.extend(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            top_level.append(node.module.split(".")[0])
    assert "dora" not in top_level, f"{DECLS[name].module} imports dora at module scope"


@pytest.mark.parametrize("name", EXPECTED)
def test_every_operator_with_diagnostics_declares_that_output(name):
    decl = DECLS[name]
    if decl.diagnostics is not None:
        assert decl.diagnostics in decl.outputs
        assert decl.outputs[decl.diagnostics].schema_id == "openrobot.diag.counters"
        assert decl.outputs[decl.diagnostics].frame == "none"


def test_the_collector_has_no_diagnostics_of_its_own():
    """It reports on others; a report about its own reporting is noise."""
    assert DECLS["diag_collector"].diagnostics is None


@pytest.mark.parametrize("name", EXPECTED)
def test_every_non_diagnostic_output_states_a_concrete_version(name):
    for port in DECLS[name].outputs.values():
        assert not port.version_spec.startswith("^"), f"{name}.{port.name}"


def test_compressed_outputs_use_the_compressed_schemas():
    """Otherwise a compressed stream could be wired into an operator that
    expects raw samples, and the pre-launch check would not catch it."""
    assert DECLS["point_cloud_compress"].outputs["blob"].schema_id == (
        "openrobot.sensor.point_cloud_compressed"
    )
    assert DECLS["image_compress"].outputs["blob"].schema_id == (
        "openrobot.sensor.image_compressed"
    )


def test_both_codec_directions_are_optional():
    """A dataflow wires the direction it needs."""
    codec = DECLS["ros2_codec"]
    assert codec.inputs["native"].required is False
    assert codec.inputs["ros"].required is False


# --- pack.yaml ---------------------------------------------------------------

def test_pack_yaml_is_a_capability_pack():
    assert PACK_YAML["apiVersion"] == "openrobot.dev/v1alpha1"
    assert PACK_YAML["kind"] == "CapabilityPack"
    assert PACK_YAML["metadata"]["name"] == "data-processing"


def test_pack_yaml_uses_camel_case_for_its_manifest_fields():
    """v1.3 §8.5 splits the casing: camelCase here, snake_case in
    operators.yaml."""
    for capability in PACK_YAML["provides"]["capabilities"]:
        for operation in capability["operations"].values():
            assert "safetyTier" in operation


def test_every_capability_declares_a_safety_tier():
    for capability in PACK_YAML["provides"]["capabilities"]:
        for name, operation in capability["operations"].items():
            assert operation["safetyTier"] == "observe", (capability["id"], name)


def test_the_pack_requires_the_contract_package():
    required = {r["id"]: r["version"] for r in PACK_YAML["requires"]["packages"]}
    assert required["open-robot-operator"].startswith("^")


# --- the dataflows -----------------------------------------------------------

def test_the_expected_dataflows_exist():
    assert [p.name for p in DATAFLOWS] == ["ab-compare.yml", "preprocess-chain.yml"]


@pytest.mark.parametrize("path", DATAFLOWS, ids=lambda p: p.name)
def test_every_dataflow_validates_with_no_violations_at_all(path):
    """Not merely no blocking ones: an unwired diagnostics port in a shipped
    example would mean the per-stage statistics are missing from the record."""
    violations = validate_dataflow(load_dataflow(path), DECLS)
    assert violations == [], "\n".join(str(v) for v in violations)


@pytest.mark.parametrize("path", DATAFLOWS, ids=lambda p: p.name)
def test_every_dataflow_node_binds_to_a_declared_operator(path):
    for node, operator in load_dataflow(path).nodes.items():
        assert operator in DECLS, f"{path.name}: node {node!r} -> {operator!r}"


def test_the_preprocess_chain_collects_every_stage():
    """A stage whose diagnostics go uncollected is missing from the record."""
    flow = load_dataflow(PACK / "dataflows" / "preprocess-chain.yml")
    publishing = {
        node for node, operator in flow.nodes.items()
        if DECLS[operator].diagnostics in flow.declared_outputs.get(node, [])
    }
    collected = {
        upstream for (consumer, _), (upstream, port) in flow.edges.items()
        if flow.nodes[consumer] == "diag_collector" and port == "diag"
    }
    assert publishing == collected


def test_the_ab_compare_flow_has_a_treated_and_a_bypass_branch():
    """Both branches must start at the same source, or the comparison is
    between two different inputs."""
    flow = load_dataflow(PACK / "dataflows" / "ab-compare.yml")
    sinks = [n for n, op in flow.nodes.items() if op == "mock_state_sink"]
    assert len(sinks) == 2
    upstreams = {flow.edges[(sink, "state")][0] for sink in sinks}
    assert "mock_state" in upstreams, "no branch bypasses the chain"
    assert len(upstreams) == 2, "both sinks read the same branch"
```
- [ ] **Step 8: Run it**

Run: `cd capabilities/data-processing && python3 -m pytest tests/test_conformance.py -q`
Expected: PASS, 52 tests

- [ ] **Step 9: Run the validator by hand on both flows**

```bash
cd capabilities/data-processing
for flow in dataflows/*.yml; do
  PYTHONPATH="../../packages/open-robot-operator:." \
    python3 -m open_robot_operator.validate "$flow" \
      --pack . --pack dataflows/mocks
  echo "  exit=$?"
done
```

Expected, for each flow:

```text
dataflows/ab-compare.yml: OK
  exit=0
dataflows/preprocess-chain.yml: OK
  exit=0
```

Zero violations, not merely zero blocking ones. An unwired diagnostics port in
a shipped example would mean the per-stage statistics are missing from the
delivered record, and `test_every_dataflow_validates_with_no_violations_at_all`
holds the examples to that.

- [ ] **Step 10: Run the whole pack suite**

Run: `cd capabilities/data-processing && python3 -m pytest -q`
Expected: PASS, 334 tests

- [ ] **Step 11: Commit**

```bash
git add capabilities/data-processing
git commit -m "feat(dataproc): mocks, orchestration examples and the conformance suite"
```

---

## Task 17: The mutation sweep, the records, and the README

The suites are green; this task establishes that they would go red if the
load-bearing behaviour broke, produces the two records contract item 16
promises, and writes the entry point a reader needs.

**Files:**
- Create: `tools/mutation-sweep.py`
- Create: `docs/operator-contract.md` (the README for both pieces)
- Create: `capabilities/data-processing/records/` with two generated records

- [ ] **Step 1: Write the mutation sweep**

`tools/mutation-sweep.py`:

```python
#!/usr/bin/env python3
"""Apply one mutation at a time, run both suites, restore, and report.

Branch coverage is not sufficient assurance here and there is direct evidence:
in the edge-inference work a *doubly wrong* gate passed all sixteen of its
tests at 100% branch coverage. So each load-bearing promise gets a mutation
that breaks it, and a mutation that no test notices is a hole in the suite,
not a curiosity.

Two operational rules, both learned the hard way:

  * nothing else may run tests in this worktree while this is running, or the
    failures it reports belong to the other process;
  * __pycache__ is cleared around every run, because a patch of identical
    length does not always invalidate a .pyc.

Usage: python3 tools/mutation-sweep.py [--list]
Exit status is non-zero if any mutation survives.
"""

import argparse
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "packages" / "open-robot-operator"
DATAPROC = ROOT / "capabilities" / "data-processing"
SUITES = (CONTRACT, DATAPROC)

# (label, file, anchor, replacement). The anchor must occur exactly once.
MUTATIONS = [
    (
        "1. the cleaner drops a degraded message instead of forwarding it",
        DATAPROC / "open_robot_dataproc/clean/cleaner_op.py",
        "        self._remember(key)",
        '        if header.validity != "ok":\n'
        "            return Decision(None, None, {})\n"
        "        self._remember(key)",
    ),
    (
        "2. compression mints a fresh capture time",
        DATAPROC / "open_robot_dataproc/compress/point_cloud_op.py",
        "    out = derive(\n        [header],",
        "    import time\n"
        "    header = type(header)(schema=header.schema, frame_id=header.frame_id,\n"
        "        seq=header.seq, stamp_ns=time.time_ns(), source=header.source,\n"
        "        validity=header.validity, reason=header.reason)\n"
        "    out = derive(\n        [header],",
    ),
    (
        "3. an output declared with a literal frame publishes its input's frame",
        CONTRACT / "open_robot_operator/wire.py",
        "    if declared.startswith(SAME_AS):\n        port = declared[len(SAME_AS):]",
        "    if parents:\n"
        "        return next(iter(parents.values())).frame_id\n"
        "    if declared.startswith(SAME_AS):\n        port = declared[len(SAME_AS):]",
    ),
    (
        "4. an upgrade is granted but never counted",
        CONTRACT / "open_robot_operator/envelope.py",
        "    if upgrade is not None:\n"
        "        upgrade.counters.count_upgrade(upgrade.reason)\n"
        "    return header",
        "    return header",
    ),
    (
        "5a. caret matching becomes exact equality",
        CONTRACT / "open_robot_operator/schemaref.py",
        '    if not constraint.startswith("^"):\n        return actual == _triple(constraint)',
        '    return actual == _triple(constraint.lstrip("^"))\n'
        '    if not constraint.startswith("^"):\n        return actual == _triple(constraint)',
    ),
    (
        "5b. caret matching becomes always true",
        CONTRACT / "open_robot_operator/schemaref.py",
        "    floor = _triple(constraint[1:])\n    if actual < floor:\n        return False",
        "    floor = _triple(constraint[1:])\n    return True\n"
        "    if actual < floor:\n        return False",
    ),
    (
        "6. the cleaner removes a defective value instead of holding it",
        DATAPROC / "open_robot_dataproc/clean/cleaner_op.py",
        "        repaired = values.copy()\n"
        "        repaired[suspect] = self._last_good[suspect]\n"
        "        return repaired",
        "        return values[~suspect]",
    ),
]


def clear_pycache() -> None:
    for root in SUITES:
        for directory in root.rglob("__pycache__"):
            shutil.rmtree(directory, ignore_errors=True)


def failing_suites() -> list:
    """Names of the suites that fail right now."""
    failed = []
    for suite in SUITES:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "-x", "--no-header",
             "-p", "no:cacheprovider"],
            cwd=suite, capture_output=True, text=True,
        )
        if result.returncode != 0:
            failed.append(suite.name)
    return failed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="print the mutations and exit")
    args = parser.parse_args()

    if args.list:
        for label, path, _, _ in MUTATIONS:
            print(f"{label}\n    {path.relative_to(ROOT)}")
        return 0

    print("baseline ... ", end="", flush=True)
    clear_pycache()
    baseline = failing_suites()
    if baseline:
        print(f"FAILING: {baseline}")
        print("the baseline must be green before mutating; fix that first")
        return 2
    print("green")

    survivors = []
    for label, path, anchor, replacement in MUTATIONS:
        original = path.read_text(encoding="utf-8")
        occurrences = original.count(anchor)
        if occurrences != 1:
            print(f"SKIP     {label}\n    anchor matched {occurrences} times in "
                  f"{path.relative_to(ROOT)}; the file has moved on and the "
                  f"mutation needs updating")
            survivors.append(label)
            continue
        path.write_text(original.replace(anchor, replacement), encoding="utf-8")
        clear_pycache()
        try:
            failed = failing_suites()
        finally:
            path.write_text(original, encoding="utf-8")
            clear_pycache()
        if failed:
            print(f"CAUGHT   {label}   [{', '.join(failed)}]")
        else:
            print(f"SURVIVED {label}   <-- HOLE")
            survivors.append(label)

    print("\nrestored baseline ... ", end="", flush=True)
    print("green" if not failing_suites() else "BROKEN, inspect the worktree")
    print(f"surviving mutations: {len(survivors)}/{len(MUTATIONS)}")
    for label in survivors:
        print(f"  {label}")
    return 1 if survivors else 0


if __name__ == "__main__":
    raise SystemExit(main())
```
- [ ] **Step 2: Run it**

Run: `python3 tools/mutation-sweep.py`
Expected output, and an exit status of 0:

```text
baseline ... green
CAUGHT   1. the cleaner drops a degraded message instead of forwarding it   [data-processing]
CAUGHT   2. compression mints a fresh capture time   [data-processing]
CAUGHT   3. an output declared with a literal frame publishes its input's frame   [open-robot-operator]
CAUGHT   4. an upgrade is granted but never counted   [open-robot-operator]
CAUGHT   5a. caret matching becomes exact equality   [open-robot-operator]
CAUGHT   5b. caret matching becomes always true   [open-robot-operator]
CAUGHT   6. the cleaner removes a defective value instead of holding it   [data-processing]

restored baseline ... green
surviving mutations: 0/7
```

If any mutation survives, that is a hole in the suite and the fix is a test,
not a change to the mutation. Do not run anything else that executes tests in
this worktree while the sweep is running: the failures it reports would belong
to the other process. That is not hypothetical — it produced a phantom test
failure once already.

- [ ] **Step 3: Generate the per-stage statistics record**

```bash
cd capabilities/data-processing
mkdir -p records
python3 - <<'PY' > records/chain-statistics.txt
import sys; sys.path[:0] = ["../../packages/open-robot-operator", "."]
import numpy as np, time
from open_robot_dataproc.compress import point_cloud_op as squeeze
from open_robot_dataproc.filter.point_cloud_op import apply
from open_robot_dataproc.mocks.point_cloud_source import frame
from open_robot_dataproc.tools.diag_collector import chain_report, render
from open_robot_operator.counters import Counters
from open_robot_operator.wire import payload_nbytes

stages = [
    ("voxel", Counters(), {"mode": "voxel", "leaf_size": 1.0}),
    ("outlier", Counters(), {"mode": "outlier", "neighbours": 8, "sigma": 1.0}),
]
squeeze_counters = Counters()

for seq in range(20):
    cloud, header = frame(seq, points=4096)
    for name, counters, config in stages:
        counters.observe_in(items=len(cloud), nbytes=payload_nbytes(cloud))
        started = time.perf_counter_ns()
        cloud, drops = apply(cloud, config)
        counters.observe_proc(ns=time.perf_counter_ns() - started)
        counters.observe_out(items=len(cloud), nbytes=payload_nbytes(cloud))
        for reason, count in drops.items():
            counters.count_drop(reason, count)
    squeeze_counters.observe_in(items=len(cloud), nbytes=payload_nbytes(cloud))
    started = time.perf_counter_ns()
    blob, info = squeeze.encode(cloud, lossy=True, precision=0.01)
    squeeze_counters.observe_proc(ns=time.perf_counter_ns() - started)
    squeeze_counters.observe_out(items=len(cloud), nbytes=len(blob))

report = chain_report(
    [(name, counters.snapshot()) for name, counters, _ in stages]
    + [("compress", squeeze_counters.snapshot())]
)
print("Per-stage data reduction and processing time")
print("20 synthetic frames of 4096 points, voxel 1.0 -> outlier k=8 s=1.0 -> lossy 0.01")
print()
print(render(report))
PY
cat records/chain-statistics.txt
```

Expected output, with the exact numbers varying only in the timings:

```text
Per-stage data reduction and processing time
20 synthetic frames of 4096 points, voxel 1.0 -> outlier k=8 s=1.0 -> lossy 0.01

stage                           in B       out B    bytes    items       ms
voxel                        1310720     1023424    0.781    0.781    40.47
outlier                      1023424      875680    0.856    0.856   225.21
compress                      875680      439180    0.502    1.000     6.21

chain byte ratio: 0.3351 (66.5% reduction)
total processing:  271.89 ms
drops:
  voxel                 downsampled   17956
  outlier               outlier       9234
```

The leaf size is 1.0, not the 0.05 a first draft used. The mock scatters 4096
points through a 20 m cube, where 0.05 m leaves give 64 million cells and
almost no collisions, so the voxel row read `1.000` and the record looked
broken. Every stage now shows a real reduction.

This is the deliverable behind "逐级统计数据量削减比例与处理耗时". It is a run
output, not a hand-written document: a hand-written one collapses under the
first detailed question at acceptance.

- [ ] **Step 4: Generate the A/B comparison record**

```bash
cd capabilities/data-processing
mkdir -p records
python3 - > records/ab-comparison.txt <<'PY'
import sys; sys.path[:0] = ["../../packages/open-robot-operator", "."]
import numpy as np
from open_robot_dataproc.clean.cleaner_op import Cleaner
from open_robot_dataproc.filter.state_op import MovingAverage, apply
from open_robot_dataproc.mocks.state_source import frame
from open_robot_dataproc.tools.ab_compare import compare, render

# sigma=2.0, not 3.0: over a width-8 vector a 3-sigma test cannot see a single
# gross outlier, because that value inflates the very spread it is judged
# against. test_a_lone_gross_outlier_can_mask_itself_in_a_narrow_vector pins it.
cleaner, smoother = Cleaner(sigma=2.0), MovingAverage(5)
baseline, treated = [], []
rejected, declined = 0, 0

for seq in range(60):
    values, header = frame(seq)
    baseline.append(np.nan_to_num(np.asarray(values, dtype=np.float64)))
    decision = cleaner.process(values, header, seq=seq, declared_frame="same_as:data")
    if not decision.forwarded:
        rejected += 1
        continue
    # Invariant 1 sends degraded messages on; it does not oblige the consumer
    # to eat them. A downstream operator reads validity and decides.
    if decision.header.validity != "ok":
        declined += 1
        continue
    smoothed, _ = apply(decision.values, {"mode": "moving_average"}, smoother)
    treated.append(smoothed)

print("Downstream output with and without the preprocessing chain")
print("60 synthetic samples of width 8; cleaner sigma=2.0 then a 5-sample moving average")
print()
print(render(compare(np.concatenate(baseline), np.concatenate(treated))))
print()
print(f"messages the cleaner did not forward:   {rejected}  (duplicate or out of order)")
print(f"messages the consumer declined to use:  {declined}  (validity was not ok)")
print()
print("what the chain removed or repaired, by reason:")
for reason, count in sorted(cleaner.counters.drops_by_reason.items()) or [("(none)", 0)]:
    print(f"  {reason:<20}{count}")
print("validity upgrades, by reason:")
rows = sorted(cleaner.counters.upgrades_by_reason.items())
for reason, count in rows or [("(none)", 0)]:
    print(f"  {reason:<20}{count}")
PY
cat records/ab-comparison.txt
```

Expected output:

```text
Downstream output with and without the preprocessing chain
60 synthetic samples of width 8; cleaner sigma=2.0 then a 5-sample moving average

baseline items: 480
treated items:  400
item ratio:     0.8333
lengths differ, so the samples were not compared pairwise;
preprocessing that removes samples is expected to do this.

messages the cleaner did not forward:   9  (duplicate or out of order)
messages the consumer declined to use:  1  (validity was not ok)

what the chain removed or repaired, by reason:
  duplicate           9
  missing             11
  outlier             17
validity upgrades, by reason:
  repaired_missing    10
```

Three details in that script are load-bearing, and each was wrong the first
time it was written.

`sigma=2.0`, not 3.0: over a width-8 vector a 3-sigma test cannot see a single
gross outlier, because the outlier inflates the very spread it is judged
against. The test named
`test_a_lone_gross_outlier_can_mask_itself_in_a_narrow_vector` pins both
halves of that.

The consumer checks `validity` before feeding the smoother. Invariant 1 sends
degraded messages on; it does not oblige the consumer to eat them. Without
that check the run dies on the first sample, because the mock's sample 0
carries a NaN the cleaner has no history to repair — which is the contract
working, not a bug.

All four drop reasons appear separately. That is item 16's counting promise:
a single total could not distinguish a duplicate from a missing value from an
outlier, and an acceptance reviewer will ask.

- [ ] **Step 5: Write the README**

`docs/operator-contract.md`:

```markdown
# Operator contract and data-processing operators

Two pieces that ship together: the contract every capability pack's operators
speak, and the first pack that speaks it.

- `packages/open-robot-operator/` — the envelope, the port declarations and
  the pre-launch validator
- `specs/operators/` — the normative text plus the frame, unit and payload
  dictionaries
- `capabilities/data-processing/` — seven data operators, one collector, and
  two orchestration examples

## What the contract is

An operator's message carries a header split along one line. Two fields
propagate verbatim through every operator:

| Field | Meaning |
|---|---|
| `stamp_ns` | the original capture time |
| `source` | where the data came from, e.g. `lidar.front` |

Five are restated by whoever produces the message, and copying them from an
input is a violation:

| Field | Meaning |
|---|---|
| `schema` | `openrobot.sensor.point_cloud/1.0.0` — structure plus SemVer |
| `frame_id` | the frame, checked for agreement and never transformed |
| `seq` | monotonic per output port; a gap means messages were lost |
| `validity` | `ok`, `missing`, `stale`, `unpaired`, `low_confidence` or `rejected` |
| `reason` | required when `validity` is not `ok`, forbidden when it is |

Two invariants make it load-bearing:

1. A message whose `validity` is not `ok` is still sent. The downstream
   operator decides what to do with it.
2. An output may be `ok` only if every contributing input was `ok`, unless the
   operator counts the upgrade — and the library does the counting, inside the
   call that grants it.

Each pack projects the same vocabulary statically into its `operators.yaml`,
which is also the operator registry. The validator reads that against a dora
dataflow and refuses to launch on a mismatch.

## Checking a dataflow before launch

```bash
cd packages/open-robot-operator
python3 -m open_robot_operator.validate \
  ../../capabilities/data-processing/dataflows/preprocess-chain.yml \
  --pack ../../capabilities/data-processing \
  --pack ../../capabilities/data-processing/dataflows/mocks
```

Five checks run, four of them blocking: schema compatibility, frame agreement,
unknown ports, unknown upstream nodes, and unwired required inputs. An
unwired diagnostics port is a warning, because diagnostics are off the
critical path. Any blocking violation exits non-zero, which is v1.3 §8.4's
"Missing requirements fail before motion".

## Running the tests

```bash
cd packages/open-robot-operator && python3 -m pytest -q   # 215 tests
cd capabilities/data-processing && python3 -m pytest -q    # 334 tests
python3 -m pytest tests/test_specs.py -q                   # 66 tests, from the repo root
```

Nothing starts a dataflow. The installed `dora` binding is 0.2.6 against a
1.0.1 pin, so every operator splits into a pure function that the tests drive
and a `main()` that owns the dora loop. A conformance test walks each
module's AST to prove the runtime is not imported at module scope.

## Assurance

```bash
python3 tools/mutation-sweep.py
```

Seven mutations, one per load-bearing promise, each of which must make a
suite fail. Branch coverage is not enough and there is evidence: in the
edge-inference work a doubly wrong gate passed all sixteen of its tests at
100% branch coverage. Nothing else may run tests in the worktree while the
sweep is running.

## What this deliberately does not do

- **No coordinate transformation.** Frames are declared and checked for
  agreement. Transforming between them belongs to the perception and control
  operators. A TF tree here would make this a project of its own.
- **No capability-ID registry.** v1.3 §8.3 governs task-level request and
  response; operators are streaming ports. The two granularities stay apart.
- **No runtime registry service.** `operators.yaml` is the registry.
- **No cross-host staleness.** `max_age_ms` compares a local clock against
  `stamp_ns`, which is well defined only on one host. The two-sided age rule
  belongs to the inference path.
- **No per-frame payload validation.** The pre-launch check already reconciled
  the schemas, and validating a point cloud at 30 Hz is not acceptable.
- **No bilateral image filter.** `cv2` is not installed, scipy and PIL do not
  provide one, and the contract does not ask for it.
```
- [ ] **Step 6: Record the component versions**

Append to `component-lock.yaml`:

```yaml
  - id: open-robot-operator
    version: 0.1.0
    kind: package
    path: packages/open-robot-operator
  - id: open-robot-dataproc
    version: 0.1.0
    kind: capability-pack
    path: capabilities/data-processing
```

- [ ] **Step 7: Run everything one last time**

```bash
cd packages/open-robot-operator && python3 -m pytest -q && cd ../..
cd capabilities/data-processing && python3 -m pytest -q && cd ../..
python3 -m pytest tests/test_specs.py -q
python3 tools/mutation-sweep.py
```

Expected: 215, 334 and 66 tests passing, and 0/7 mutations surviving.

- [ ] **Step 8: Commit**

```bash
git add tools/mutation-sweep.py docs/operator-contract.md \
        capabilities/data-processing/records component-lock.yaml
git commit -m "test(operator): mutation sweep, the delivered records, and the README"
```

---

## What this plan does not build

Stated so the gaps are decisions rather than omissions:

| Not built | Why | Where it belongs |
|---|---|---|
| Any running dataflow | The installed dora binding is 0.2.6 against a 1.0.1 pin, and `tools/install-dora.sh` stops at its x86_64 check on this host | Sub-project 2, on a fleet host |
| A C++ contract library | Python first, by decision; the C++ side only has to read the schemas | A later phase, if dora-nav's nodes need it natively |
| Coordinate transformation | The largest scope cut; frames are declared and checked, never converted | The perception and control operators |
| `robot-stack operators validate` | Would need a v1.3 §9.2 amendment, and the prerequisite for three contract items should not wait on spec review | Once §9.2 has a place for it |
| Cross-host staleness | Needs a two-sided age rule and clock-offset handling | Already owned by the inference path |
| Ground segmentation, clustering | Perception semantics, not preprocessing | Sub-project 2 (contract item 13) |
