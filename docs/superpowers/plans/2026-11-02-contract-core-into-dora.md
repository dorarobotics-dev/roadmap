# Contract Core into dora — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** In local copies of dora and DORA_NAV, prove that the operator contract (header metadata, validity rules, frames, transform library, pre-launch frame checks) works as part of dora, end to end, from the MuJoCo sim through a frame_transform node.

**Architecture:** The header lives in `dora-message` (`header.rs`). Frames, extrinsics, routes and rigid transforms live in a new crate `dora-transform`. `dora-core` gains frame annotations on nodes, a `frames:` dataflow key, and a frame-check pass that `dora validate` runs. The Python package exposes the transform crate as `dora.transform`. A Python `frame-transform` node and a C metadata API complete the dora side. DORA_NAV's sim emits headers and typed outputs; a checker node and `dora validate` prove the chain.

**Tech Stack:** Rust 2024 (cargo 1.96), pyo3 0.29 + maturin, Python 3.11 (uv venv), pyarrow, numpy, MuJoCo 3, dora master `1016eab0a`, DORA_NAV `a9257f5`.

**Spec:** `docs/superpowers/specs/2026-11-02-contract-core-into-dora-design.md` (in this worktree).

---

## Ground rules for every task

- Paths: `D=/home/demo/Public/github_dimos/dora`, `N=/home/demo/Public/github_dimos/DORA_NAV`, `REF=/home/demo/Public/github_dimos/open-robot-stack-operator-contract`, `VENV=/home/demo/Public/github_dimos/.venv-exp`.
- Work only on branch `exp/contract-core` in `D` and `N`. **Never push. Never run `git push`.**
- Every `pytest` is run as `PYTHONPATH= $VENV/bin/python -m pytest ...` (ROS humble on this machine injects a pytest plugin that breaks collection otherwise).
- **Never** run `dora up`, `dora destroy`, `dora stop` or `dora start` without `DORA_COORDINATOR_PORT=6113` and `DORA_DAEMON_PORT` set as in Task 13. The coordinator on the default port belongs to another project.
- `REF` is the behavioural reference. When a step says "same message as the reference", copy the wording from the cited reference line.
- Commit after every task with a message ending in:
  ```
  Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
  ```

## Deviations from the spec, decided while planning

1. **Frame names.** The reference dictionary (`REF/specs/operators/frames.yaml`) rejects `lidar_link` and `camera_link`; their names are `rslidar` and `camera_front`. The dictionary is copied unchanged, and the sim maps its frame names (Task 11). Spec §5's `robots/mickrobot-sim/frames.yml` lists the reference names instead.
2. **`derive()` semantics.** Ported from `REF/packages/open-robot-operator/open_robot_operator/envelope.py:57-79`, not "worst input wins". The caller states the output validity. An `ok` output from degraded parents needs a counted upgrade; an upgrade with no degraded parent is an error. The output stamp is the minimum parent stamp, and the source is the sorted, `+`-joined parent sources.
3. **No `schema` key at run time.** dora's type URN on the port replaces the reference's `schema` header key.
4. **Pose-coverage check.** Ported as the reference does it (`validate.py:319-397`): more than one dynamic edge on a route is refused; one dynamic edge needs a wired `std/math/v1/Pose` input. It does not inspect `child_frame` before launch.
5. **Calibration env.** Nodes load calibration from `DORA_FRAMES` and `DORA_EXTRINSICS`, which replace `ORS_FRAMES` and `ORS_EXTRINSICS`. The validator checks that `DORA_EXTRINSICS` resolves to the dataflow's `frames.extrinsics` (reference mutation 16).
6. **Mutation sweep scope.** Ten of the reference's 17 mutations concern this slice: 3, 4, 7, 10–16. The other seven, 1, 2, 5a, 5b, 6, 8 and 9 (data processing, version carets, dora built-ins), are recorded as "later slice" in the test mapping.

## File structure

dora copy (`D`):

| File | Responsibility |
|---|---|
| `libraries/message/src/header.rs` (new) | Header key constants, `Validity`, `Header` read/write over `MetadataParameters`, `derive` |
| `libraries/message/src/lib.rs` (modify) | `pub mod header;` |
| `libraries/transform/Cargo.toml`, `src/lib.rs` (new) | Crate `dora-transform` root, error types |
| `libraries/transform/src/frames.rs` (new) | Frame dictionary: parse, `require`, `chain` |
| `libraries/transform/src/extrinsics.rs` (new) | Per-robot calibration: parse, `route` |
| `libraries/transform/src/rigid.rs` (new) | `Transform`, `lookup`, `pose_transform`, `resolve` |
| `libraries/transform/tests/fixtures/*.yml` (new) | Reference frames and extrinsics copies |
| `Cargo.toml` (modify) | Workspace member and dependency entry |
| `libraries/core/types/std/media/v1.yml`, `std/math/v1.yml` (modify) | Required header keys; `PointCloud` `fields` parameter |
| `libraries/message/src/descriptor.rs` (modify) | `Node.output_frames`, `Node.input_frames`, `Descriptor.frames` |
| `libraries/core/src/descriptor/classify.rs` (modify) | Whitelist the two new node keys |
| `libraries/core/src/descriptor/frames_check.rs` (new) | The five frame checks |
| `libraries/core/src/descriptor/mod.rs` (modify) | `pub mod frames_check;` |
| `binaries/cli/src/command/validate.rs` (modify) | Run the frame checks; fail on any |
| `apis/c/node/src/lib.rs`, `node_api.h` (modify) | `DoraParam`, `dora_send_output_with_params` |
| `examples/c-header/` (new) | C node sending a header; Python receiver asserting it |
| `apis/python/node/src/transform.rs` (new), `lib.rs`, `Cargo.toml` (modify) | `dora.transform` submodule |
| `nodes/frame-transform/` (new) | Python node package, `dora-node.yml`, tests |
| `tools/contract-mutation-sweep.py` (new) | The ten mutations |
| `docs/contract-core/test-mapping.md`, `tools/check-test-mapping.py` (new) | Reference test → new test |
| `docs/contract-core/feasibility.md` (new) | Exit report |

DORA_NAV copy (`N`):

| File | Responsibility |
|---|---|
| `modules/simulation/mujoco_mickrobot/src/mujoco_mickrobot/contract.py` (new) | Frame renames, stamp conversion, seq, header metadata, typed arrays |
| `.../dora_adapter.py`, `runtime.py`, `main.py` (modify) | Send headers; typed `cloud` and `odom_pose` outputs; strip switch |
| `.../tests/test_contract.py` (new) | Unit tests |
| `.../dora-node.yml` (new) | Manifest with types and frames |
| `robots/mickrobot-sim/frames.yml`, `extrinsics.yml` (new) | Robot description |
| `examples/contract-core/good.yml`, `bad-*.yml`, `checker.py`, `run_validate.sh`, `run_live.sh` (new) | Dataflows, checker, scripts |

---

### Task 1: Workspace, copies and build environment

**Files:** none in git; creates the copies and `.venv-exp`.

- [ ] **Step 1: Clone the seven repos**

```bash
cd /home/demo/Public/github_dimos
git clone ~/Public/github_dora/dora dora
git clone ~/Public/github_dora/DORA_NAV DORA_NAV
git clone ~/Public/github_dora/dora-moveit2 dora-moveit2
git clone ~/Public/github_dora/dora-hub dora-hub
git clone ~/Public/github_octos-org/octos octos
git clone https://github.com/dora-rs/dora-studio.git dora-studio
git clone https://github.com/dorarobotics/octos-dora-bridge.git octos-dora-bridge
```

- [ ] **Step 2: Branches and remotes**

```bash
cd /home/demo/Public/github_dimos
(cd dora && git checkout -b exp/contract-core 1016eab0a && git remote add upstream https://github.com/dora-rs/dora.git)
(cd DORA_NAV && git checkout -b exp/contract-core a9257f5 && git remote add upstream https://github.com/dora-rs/DORA_NAV.git)
for r in dora-moveit2 dora-hub octos; do (cd $r && git checkout -b exp/contract-core); done
(cd dora-moveit2 && git remote add upstream https://github.com/dora-rs/dora-moveit2.git)
(cd dora-hub && git remote add upstream https://github.com/dora-rs/dora-hub.git)
(cd octos && git remote add upstream https://github.com/octos-org/octos.git)
for r in dora-studio octos-dora-bridge; do (cd $r && git checkout -b exp/contract-core && git remote rename origin upstream); done
for r in dora DORA_NAV dora-moveit2 dora-hub octos dora-studio octos-dora-bridge; do
  (cd $r && git remote set-url --push upstream DISABLED && git remote set-url --push origin DISABLED 2>/dev/null; echo "$r $(git rev-parse --short HEAD) $(git branch --show-current)")
done
```

Expected: seven lines, each on `exp/contract-core`; `dora 1016eab0a`, `DORA_NAV a9257f5`. The push URLs are `DISABLED`, so an accidental push fails.

- [ ] **Step 3: Python 3.11 venv with the test and sim dependencies**

```bash
cd /home/demo/Public/github_dimos
uv venv --python 3.11 .venv-exp
uv pip install --python .venv-exp/bin/python maturin pytest pytest-timeout numpy "pyarrow>=14,<26" PyYAML "mujoco>=3.2,<4"
```

Expected: installs succeed. If uv cannot find 3.11, add `--python ~/anaconda3/envs/ff-agent-py311/bin/python`.

- [ ] **Step 4: Build the experiment dora (CLI and Python package)**

```bash
cd /home/demo/Public/github_dimos/dora
cargo build -p dora-cli --release
cd apis/python/node && VIRTUAL_ENV=/home/demo/Public/github_dimos/.venv-exp /home/demo/Public/github_dimos/.venv-exp/bin/maturin develop --release
/home/demo/Public/github_dimos/dora/target/release/dora --version
PYTHONPATH= /home/demo/Public/github_dimos/.venv-exp/bin/python -c "import dora; print(dora.__version__)"
```

Expected: `dora-cli 1.1.0` and `1.1.0`. Use `$D/target/release/dora` for every later `dora` command; never the system `dora`.

- [ ] **Step 5: Baseline test runs (record the numbers)**

```bash
cd /home/demo/Public/github_dimos/dora
cargo test -p dora-message -p dora-core 2>&1 | grep -E "^test result" | tee /tmp/claude-baseline-dora.txt
```

Expected: every `test result: ok`. Record the totals in `D/docs/contract-core/feasibility.md` (create the file with a `## Baseline` heading and the lines). Nothing to commit in `N` yet.

- [ ] **Step 6: Commit the baseline note**

```bash
cd /home/demo/Public/github_dimos/dora
git add docs/contract-core/feasibility.md
git commit -m "docs(contract-core): record the baseline test results

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Header in dora-message

**Files:**
- Create: `D/libraries/message/src/header.rs`
- Modify: `D/libraries/message/src/lib.rs` (add `pub mod header;` next to `pub mod metadata;`)

- [ ] **Step 1: Write the failing tests** (bottom of `header.rs`, written first with the module skeleton `pub mod header;` added)

```rust
#[cfg(test)]
mod tests {
    use super::*;
    use crate::metadata::{MetadataParameters, Parameter};

    fn ok(frame: &str, stamp: i64, source: &str) -> Header {
        Header::new(frame, 0, stamp, source, Validity::Ok, None).unwrap()
    }

    #[test]
    fn validity_round_trips_as_snake_case() {
        for v in Validity::ALL {
            assert_eq!(Validity::parse(v.as_str()).unwrap(), v);
        }
        assert_eq!(Validity::LowConfidence.as_str(), "low_confidence");
        assert!(Validity::parse("fine").is_err());
    }

    #[test]
    fn ok_with_reason_is_refused() {
        assert!(Header::new("map", 0, 1, "s", Validity::Ok, Some("x".into())).is_err());
    }

    #[test]
    fn degraded_without_reason_is_refused() {
        assert!(Header::new("map", 0, 1, "s", Validity::Stale, None).is_err());
        assert!(Header::new("map", 0, 1, "s", Validity::Stale, Some(String::new())).is_err());
    }

    #[test]
    fn empty_frame_or_source_and_zero_stamp_are_refused() {
        assert!(Header::new("", 0, 1, "s", Validity::Ok, None).is_err());
        assert!(Header::new("map", 0, 1, "", Validity::Ok, None).is_err());
        assert!(Header::new("map", 0, 0, "s", Validity::Ok, None).is_err());
        assert!(Header::new("map", -1, 1, "s", Validity::Ok, None).is_err());
    }

    #[test]
    fn metadata_round_trip_omits_reason_when_ok() {
        let h = ok("rslidar", 5, "lidar");
        let mut params = MetadataParameters::new();
        h.write(&mut params);
        assert!(!params.contains_key(REASON));
        assert_eq!(Header::read(&params).unwrap(), h);
    }

    #[test]
    fn read_names_the_missing_key() {
        let mut params = MetadataParameters::new();
        ok("map", 1, "s").write(&mut params);
        params.remove(FRAME_ID);
        let err = Header::read(&params).unwrap_err().to_string();
        assert!(err.contains("frame_id"), "{err}");
    }

    #[test]
    fn read_refuses_a_wrongly_typed_key() {
        let mut params = MetadataParameters::new();
        ok("map", 1, "s").write(&mut params);
        params.insert(SEQ.into(), Parameter::String("3".into()));
        let err = Header::read(&params).unwrap_err().to_string();
        assert!(err.contains("seq"), "{err}");
    }

    #[test]
    fn derive_takes_min_stamp_and_joined_sources() {
        let out = derive(&[ok("a", 9, "lidar"), ok("a", 4, "cam")], "map", 2,
                         Validity::Ok, None, None).unwrap();
        assert_eq!(out.stamp_ns, 4);
        assert_eq!(out.source, "cam+lidar");
        assert_eq!(out.frame_id, "map");
        assert_eq!(out.seq, 2);
    }

    #[test]
    fn derive_refuses_ok_from_degraded_without_upgrade() {
        let stale = Header::new("a", 0, 1, "s", Validity::Stale, Some("old".into())).unwrap();
        assert!(derive(&[stale.clone()], "a", 0, Validity::Ok, None, None).is_err());
        let out = derive(&[stale], "a", 0, Validity::Stale, Some("old".into()), None).unwrap();
        assert_eq!(out.validity, Validity::Stale);
    }

    #[test]
    fn derive_counts_an_upgrade() {
        let stale = Header::new("a", 0, 1, "s", Validity::Stale, Some("old".into())).unwrap();
        let mut counted = Vec::new();
        let mut count = |r: &str| counted.push(r.to_string());
        derive(&[stale], "a", 0, Validity::Ok, None, Some(Upgrade { reason: "refit", count: &mut count })).unwrap();
        assert_eq!(counted, vec!["refit".to_string()]);
    }

    #[test]
    fn derive_refuses_upgrade_with_no_degraded_parent() {
        let mut count = |_: &str| {};
        assert!(derive(&[ok("a", 1, "s")], "a", 0, Validity::Ok, None,
                       Some(Upgrade { reason: "x", count: &mut count })).is_err());
    }

    #[test]
    fn derive_needs_a_parent() {
        assert!(derive(&[], "a", 0, Validity::Ok, None, None).is_err());
    }
}
```

- [ ] **Step 2: Run to verify failure**

Run: `cd $D && cargo test -p dora-message header::`
Expected: compile errors (`Header`, `Validity`, `derive` not found).

- [ ] **Step 3: Implement** (top of `header.rs`)

```rust
//! The contract header carried in dora metadata.
//!
//! A message's frame, capture time, sequence, source and validity travel as
//! metadata parameters under the keys below. A degraded message is forwarded,
//! never silently dropped, and never upgraded except by an operator that
//! counts the upgrade (see [`derive`]).

use crate::metadata::{MetadataParameters, Parameter};
use std::fmt;

pub const FRAME_ID: &str = "frame_id";
pub const SEQ: &str = "seq";
pub const STAMP_NS: &str = "stamp_ns";
pub const SOURCE: &str = "source";
pub const VALIDITY: &str = "validity";
pub const REASON: &str = "reason";
pub const CHILD_FRAME: &str = "child_frame";

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct HeaderError(pub String);

impl fmt::Display for HeaderError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(&self.0)
    }
}

impl std::error::Error for HeaderError {}

fn err<T>(msg: impl Into<String>) -> Result<T, HeaderError> {
    Err(HeaderError(msg.into()))
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub enum Validity {
    Ok,
    Missing,
    Stale,
    Unpaired,
    LowConfidence,
    Rejected,
}

impl Validity {
    pub const ALL: [Validity; 6] = [
        Validity::Ok, Validity::Missing, Validity::Stale,
        Validity::Unpaired, Validity::LowConfidence, Validity::Rejected,
    ];

    pub fn as_str(self) -> &'static str {
        match self {
            Validity::Ok => "ok",
            Validity::Missing => "missing",
            Validity::Stale => "stale",
            Validity::Unpaired => "unpaired",
            Validity::LowConfidence => "low_confidence",
            Validity::Rejected => "rejected",
        }
    }

    pub fn parse(s: &str) -> Result<Self, HeaderError> {
        Self::ALL.into_iter().find(|v| v.as_str() == s).map_or_else(
            || err(format!("unknown validity {s:?}; expected one of ok, missing, stale, unpaired, low_confidence, rejected")),
            Ok,
        )
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Header {
    pub frame_id: String,
    pub seq: i64,
    pub stamp_ns: i64,
    pub source: String,
    pub validity: Validity,
    pub reason: Option<String>,
}

impl Header {
    pub fn new(
        frame_id: impl Into<String>, seq: i64, stamp_ns: i64, source: impl Into<String>,
        validity: Validity, reason: Option<String>,
    ) -> Result<Self, HeaderError> {
        let h = Header { frame_id: frame_id.into(), seq, stamp_ns, source: source.into(), validity, reason };
        if h.frame_id.is_empty() {
            return err("frame_id must be a non-empty string");
        }
        if h.source.is_empty() {
            return err("source must be a non-empty string");
        }
        if h.seq < 0 {
            return err(format!("seq must be an int >= 0, got {}", h.seq));
        }
        if h.stamp_ns < 1 {
            return err(format!("stamp_ns must be an int >= 1, got {}", h.stamp_ns));
        }
        match (&h.validity, &h.reason) {
            (Validity::Ok, Some(_)) => return err("reason must be absent when validity is ok"),
            (v, None) if *v != Validity::Ok => {
                return err(format!("validity {:?} requires a non-empty reason", v.as_str()));
            }
            (v, Some(r)) if *v != Validity::Ok && r.is_empty() => {
                return err(format!("validity {:?} requires a non-empty reason", v.as_str()));
            }
            _ => {}
        }
        Ok(h)
    }

    /// Write the header into `params`. `reason` is omitted when absent.
    pub fn write(&self, params: &mut MetadataParameters) {
        params.insert(FRAME_ID.into(), Parameter::String(self.frame_id.clone()));
        params.insert(SEQ.into(), Parameter::Integer(self.seq));
        params.insert(STAMP_NS.into(), Parameter::Integer(self.stamp_ns));
        params.insert(SOURCE.into(), Parameter::String(self.source.clone()));
        params.insert(VALIDITY.into(), Parameter::String(self.validity.as_str().into()));
        match &self.reason {
            Some(r) => { params.insert(REASON.into(), Parameter::String(r.clone())); }
            None => { params.remove(REASON); }
        }
    }

    /// Read a header back. A missing or wrongly typed key is an error naming it.
    pub fn read(params: &MetadataParameters) -> Result<Self, HeaderError> {
        let string = |key: &str| match params.get(key) {
            Some(Parameter::String(s)) => Ok(s.clone()),
            Some(other) => err(format!("metadata key {key:?} must be a string, got {other:?}")),
            None => err(format!("metadata carries no contract header; missing {key:?}")),
        };
        let integer = |key: &str| match params.get(key) {
            Some(Parameter::Integer(i)) => Ok(*i),
            Some(other) => err(format!("metadata key {key:?} must be an integer, got {other:?}")),
            None => err(format!("metadata carries no contract header; missing {key:?}")),
        };
        let reason = match params.get(REASON) {
            Some(Parameter::String(s)) => Some(s.clone()),
            Some(other) => return err(format!("metadata key \"reason\" must be a string, got {other:?}")),
            None => None,
        };
        Header::new(
            string(FRAME_ID)?, integer(SEQ)?, integer(STAMP_NS)?, string(SOURCE)?,
            Validity::parse(&string(VALIDITY)?)?, reason,
        )
    }
}

/// A counted upgrade: the only way an output may be `ok` while a parent is not.
pub struct Upgrade<'a> {
    pub reason: &'a str,
    pub count: &'a mut dyn FnMut(&str),
}

/// The header of a message computed from `parents`.
///
/// The caller states the output validity. It cannot be `ok` while a parent is
/// degraded unless an [`Upgrade`] is given, which is counted. The stamp is the
/// earliest parent stamp; the source is the sorted, `+`-joined parent sources.
pub fn derive(
    parents: &[Header], frame_id: &str, seq: i64, validity: Validity,
    reason: Option<String>, upgrade: Option<Upgrade<'_>>,
) -> Result<Header, HeaderError> {
    if parents.is_empty() {
        return err("derive() needs at least one parent; source nodes build a Header directly");
    }
    let mut degraded: Vec<&str> = parents.iter()
        .filter(|p| p.validity != Validity::Ok).map(|p| p.validity.as_str()).collect();
    degraded.sort_unstable();
    degraded.dedup();
    match (validity, &upgrade) {
        (Validity::Ok, None) if !degraded.is_empty() => {
            return err(format!(
                "invariant 2: the output cannot be ok while its inputs are {degraded:?} without a counted upgrade"));
        }
        (Validity::Ok, Some(_)) if degraded.is_empty() => {
            return err("an upgrade was offered but every input is already ok");
        }
        (v, Some(_)) if v != Validity::Ok => {
            return err("an upgrade is only meaningful when the output is ok");
        }
        _ => {}
    }
    let mut sources: Vec<&str> = parents.iter().map(|p| p.source.as_str()).collect();
    sources.sort_unstable();
    sources.dedup();
    let header = Header::new(
        frame_id, seq, parents.iter().map(|p| p.stamp_ns).min().unwrap(),
        sources.join("+"), validity, reason,
    )?;
    if let Some(up) = upgrade {
        (up.count)(up.reason);
    }
    Ok(header)
}
```

- [ ] **Step 4: Run the tests**

Run: `cd $D && cargo test -p dora-message header::`
Expected: 12 tests pass.

- [ ] **Step 5: Commit**

```bash
cd $D && git add libraries/message/src/header.rs libraries/message/src/lib.rs
git commit -m "feat(message): contract header keys, validity and derive

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: dora-transform crate — frames and extrinsics

**Files:**
- Create: `D/libraries/transform/Cargo.toml`, `src/lib.rs`, `src/frames.rs`, `src/extrinsics.rs`
- Create: `D/libraries/transform/tests/fixtures/frames.yml` (copy of `REF/specs/operators/frames.yaml`), `tests/fixtures/extrinsics.yml` (copy of `REF/robots/simulated-mobile-robot/extrinsics.yaml`)
- Create: `D/libraries/transform/tests/frames_extrinsics.rs`
- Modify: `D/Cargo.toml` — add `"libraries/transform",` to `members` after `"libraries/recording",`, and `dora-transform = { version = "=1.1.0", path = "libraries/transform" }` under `[workspace.dependencies]` after `dora-message`.

- [ ] **Step 1: Crate skeleton**

`libraries/transform/Cargo.toml`:

```toml
[package]
name = "dora-transform"
version.workspace = true
edition.workspace = true
rust-version.workspace = true
license.workspace = true
repository.workspace = true
description = "Frame dictionary, per-robot extrinsics and rigid transforms for dora dataflows."

[dependencies]
serde = { workspace = true }
serde_yaml = { workspace = true }
thiserror = { workspace = true }
```

`libraries/transform/src/lib.rs`:

```rust
//! Frames, calibration and rigid transforms.
//!
//! Which edges a transform uses is decided in [`frames`] and [`extrinsics`],
//! without arithmetic, so `dora validate` can check a route before launch.
//! [`rigid`] does the arithmetic.

pub mod extrinsics;
pub mod frames;
pub mod rigid;

pub use extrinsics::{Edge, Extrinsics, Route};
pub use frames::{Frame, FrameDict, Kind};

/// Upstream dora-nav normalises in float32, which leaves the norm about 1e-7
/// off; 1e-6 accepts that and still refuses a quaternion nobody normalised.
pub const QUATERNION_NORM_TOLERANCE: f64 = 1e-6;

#[derive(Debug, Clone, PartialEq, thiserror::Error)]
pub enum FrameError {
    /// A malformed dictionary, calibration or transform.
    #[error("{0}")]
    Invalid(String),
    /// The name is not in the dictionary, or is an upstream name it rejects.
    #[error("{0}")]
    UnknownFrame(String),
    /// A static path needs an edge the robot's calibration does not hold.
    #[error("{0}")]
    MissingExtrinsic(String),
    /// A static path crosses edges only a published pose can give.
    /// `edges` holds every dynamic edge as (child, parent), in route order.
    #[error("{message}")]
    DynamicEdge { message: String, edges: Vec<(String, String)> },
    /// Two transforms were composed whose frames do not meet.
    #[error("{0}")]
    FrameOrder(String),
}

pub type Result<T> = std::result::Result<T, FrameError>;
```

Create an empty `src/rigid.rs` (filled in Task 4) so the crate compiles.

- [ ] **Step 2: Write the failing tests** (`tests/frames_extrinsics.rs`)

```rust
use dora_transform::{Extrinsics, FrameDict, FrameError, Kind};

const FRAMES: &str = include_str!("fixtures/frames.yml");
const EXTRINSICS: &str = include_str!("fixtures/extrinsics.yml");

fn frames() -> FrameDict { FrameDict::parse(FRAMES).unwrap() }
fn extrinsics() -> Extrinsics { Extrinsics::parse(EXTRINSICS, &frames(), None).unwrap() }

#[test]
fn reference_dictionary_loads() {
    let f = frames();
    assert_eq!(f.require("rslidar").unwrap().kind, Kind::Mounted);
    assert_eq!(f.chain("rslidar").unwrap(), vec!["rslidar", "base_link", "base_footprint", "odom", "map"]);
}

#[test]
fn rejected_name_says_what_to_use() {
    let e = frames().require("lidar_link").unwrap_err();
    assert!(matches!(e, FrameError::UnknownFrame(_)));
    assert!(e.to_string().contains("'rslidar'"), "{e}");
}

#[test]
fn unknown_frame_is_refused() {
    assert!(matches!(frames().require("nowhere"), Err(FrameError::UnknownFrame(_))));
}

#[test]
fn dictionary_shape_errors() {
    for bad in [
        "frames: [{name: a, kind: fixed}, {name: a, kind: fixed}]",
        "frames: [{name: a, kind: spinning}]",
        "frames: [{name: a, parent: b, kind: mounted}]",
        "frames: [{name: a, kind: mounted}]",
        "frames: [{name: a, parent: a, kind: fixed}]",
        "frames: [{name: [a], kind: fixed}]",
        "frames: [{name: a, kind: fixed}]\nrejected_names: {a: a}",
        "frames: [{name: a, kind: fixed}]\nrejected_names: {b: c}",
        "nodes: []",
    ] {
        assert!(FrameDict::parse(bad).is_err(), "accepted: {bad}");
    }
}

#[test]
fn cycle_is_refused() {
    let doc = "frames: [{name: a, parent: b, kind: dynamic}, {name: b, parent: a, kind: dynamic}]";
    assert!(FrameDict::parse(doc).unwrap_err().to_string().contains("cycle"));
}

#[test]
fn static_route_up_and_down() {
    let r = extrinsics().route("rslidar", "camera_front").unwrap();
    assert_eq!(r.up.iter().map(|e| e.child.as_str()).collect::<Vec<_>>(), vec!["rslidar"]);
    assert_eq!(r.down.iter().map(|e| e.child.as_str()).collect::<Vec<_>>(), vec!["camera_front"]);
}

#[test]
fn route_through_one_dynamic_edge_names_it() {
    match extrinsics().route("rslidar", "odom") {
        Err(FrameError::DynamicEdge { edges, .. }) => {
            assert_eq!(edges, vec![("base_footprint".to_string(), "odom".to_string())]);
        }
        other => panic!("{other:?}"),
    }
}

#[test]
fn route_through_two_dynamic_edges_lists_both() {
    match extrinsics().route("rslidar", "map") {
        Err(FrameError::DynamicEdge { edges, .. }) => assert_eq!(edges.len(), 2),
        other => panic!("{other:?}"),
    }
}

#[test]
fn missing_extrinsic_wins_over_dynamic_edge() {
    let doc = EXTRINSICS.replace(
        "  - parent: base_footprint\n    child: base_link\n    translation_m: [0.0, 0.0, 0.1]\n    rotation_xyzw: [0.0, 0.0, 0.0, 1.0]\n", "");
    let e = Extrinsics::parse(&doc, &frames(), None).unwrap();
    let err = e.route("rslidar", "odom").unwrap_err();
    assert!(matches!(err, FrameError::MissingExtrinsic(_)), "{err:?}");
    assert!(err.to_string().contains("never assumed to be identity"));
}

#[test]
fn none_frame_is_never_routed() {
    assert!(matches!(extrinsics().route("none", "map"), Err(FrameError::UnknownFrame(_))));
}

#[test]
fn calibration_shape_errors() {
    let f = frames();
    let edge = |body: &str| format!(
        "contract_version: 1.0.0\nrobot: r\ncalibrated: \"2026-10-20\"\nsource: s\ntransforms:\n{body}");
    for bad in [
        edge("  - {parent: odom, child: base_footprint, translation_m: [0,0,0], rotation_xyzw: [0,0,0,1]}"),
        edge("  - {parent: map, child: base_link, translation_m: [0,0,0], rotation_xyzw: [0,0,0,1]}"),
        edge("  - {parent: base_link, child: rslidar, translation_m: [0,0], rotation_xyzw: [0,0,0,1]}"),
        edge("  - {parent: base_link, child: rslidar, translation_m: [0,0,0], rotation_xyzw: [0,0,0,2]}"),
        edge("  - {parent: base_link, child: rslidar, translation_m: [0,0,0], rotation_xyzw: [0,0,0,1]}\n  - {parent: base_link, child: rslidar, translation_m: [0,0,0], rotation_xyzw: [0,0,0,1]}"),
        edge("  - {parent: base_link, child: rslidar, translation_m: [0,0,.nan], rotation_xyzw: [0,0,0,1]}"),
        edge("  - {parent: base_link, child: rslidar, translation_m: [0,0,true], rotation_xyzw: [0,0,0,1]}"),
        "robot: r\ntransforms: []".to_string(),
    ] {
        assert!(Extrinsics::parse(&bad, &f, None).is_err(), "accepted: {bad}");
    }
}
```

- [ ] **Step 3: Run to verify failure**

Run: `cd $D && cargo test -p dora-transform --test frames_extrinsics`
Expected: compile errors (`FrameDict::parse` etc. not found).

- [ ] **Step 4: Implement `src/frames.rs`**

```rust
use crate::{FrameError, Result};
use serde_yaml::Value;
use std::collections::{BTreeMap, BTreeSet};
use std::path::Path;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Kind { Fixed, Dynamic, Mounted, None }

impl Kind {
    fn parse(s: &str) -> Option<Kind> {
        match s {
            "fixed" => Some(Kind::Fixed),
            "dynamic" => Some(Kind::Dynamic),
            "mounted" => Some(Kind::Mounted),
            "none" => Some(Kind::None),
            _ => None,
        }
    }
    pub fn as_str(self) -> &'static str {
        match self { Kind::Fixed => "fixed", Kind::Dynamic => "dynamic", Kind::Mounted => "mounted", Kind::None => "none" }
    }
}

#[derive(Debug, Clone, PartialEq)]
pub struct Frame { pub name: String, pub parent: Option<String>, pub kind: Kind }

#[derive(Debug, Clone, PartialEq)]
pub struct FrameDict {
    pub frames: BTreeMap<String, Frame>,
    pub rejected: BTreeMap<String, String>,
}

fn invalid<T>(msg: String) -> Result<T> { Err(FrameError::Invalid(msg)) }

impl FrameDict {
    pub fn load(path: &Path) -> Result<Self> {
        let text = std::fs::read_to_string(path)
            .map_err(|e| FrameError::Invalid(format!("{}: {e}", path.display())))?;
        Self::parse(&text)
    }

    pub fn parse(text: &str) -> Result<Self> {
        let doc: Value = serde_yaml::from_str(text).map_err(|e| FrameError::Invalid(e.to_string()))?;
        let Some(list) = doc.get("frames").and_then(Value::as_sequence) else {
            return invalid("a frame dictionary must be a mapping with a 'frames' list".into());
        };
        let mut frames = BTreeMap::new();
        for entry in list {
            if !entry.is_mapping() {
                return invalid(format!("each frame must be a mapping, got {entry:?}"));
            }
            let Some(name) = entry.get("name").and_then(Value::as_str).filter(|s| !s.is_empty()) else {
                return invalid(format!("a frame needs a non-empty name, got {entry:?}"));
            };
            if frames.contains_key(name) {
                return invalid(format!("frame '{name}' is declared more than once"));
            }
            let kind_raw = entry.get("kind").and_then(Value::as_str).unwrap_or("");
            let Some(kind) = Kind::parse(kind_raw) else {
                return invalid(format!(
                    "frame '{name}' has kind {kind_raw:?}; expected one of fixed, dynamic, mounted, none"));
            };
            let parent = match entry.get("parent") {
                None | Some(Value::Null) => None,
                Some(Value::String(p)) => Some(p.clone()),
                Some(other) => return invalid(format!(
                    "frame '{name}' has parent {other:?}; expected a frame name or null")),
            };
            frames.insert(name.to_string(), Frame { name: name.to_string(), parent, kind });
        }
        for frame in frames.values() {
            if let Some(p) = &frame.parent && !frames.contains_key(p) {
                return invalid(format!("frame '{}' names unknown parent '{p}'", frame.name));
            }
            match (frame.kind, &frame.parent) {
                (Kind::Dynamic | Kind::Mounted, None) => {
                    return invalid(format!("{} frame '{}' needs a parent", frame.kind.as_str(), frame.name));
                }
                (Kind::Fixed | Kind::None, Some(_)) => {
                    return invalid(format!("{} frame '{}' cannot have a parent", frame.kind.as_str(), frame.name));
                }
                _ => {}
            }
        }
        for start in frames.keys() {
            let mut seen = BTreeSet::new();
            let mut node = Some(start.clone());
            while let Some(n) = node {
                if !seen.insert(n.clone()) {
                    return invalid(format!("the frame tree has a cycle through '{n}'"));
                }
                node = frames[&n].parent.clone();
            }
        }
        let mut rejected = BTreeMap::new();
        match doc.get("rejected_names") {
            None | Some(Value::Null) => {}
            Some(Value::Mapping(map)) => {
                for (bad, good) in map {
                    let (Some(bad), Some(good)) = (bad.as_str(), good.as_str()) else {
                        return invalid("rejected_names must map an upstream name to a frame".into());
                    };
                    if frames.contains_key(bad) {
                        return invalid(format!("'{bad}' is both a frame and a rejected name"));
                    }
                    if !frames.contains_key(good) {
                        return invalid(format!("rejected name '{bad}' points at unknown frame '{good}'"));
                    }
                    rejected.insert(bad.to_string(), good.to_string());
                }
            }
            Some(_) => return invalid("rejected_names must map an upstream name to a frame".into()),
        }
        Ok(FrameDict { frames, rejected })
    }

    pub fn require(&self, name: &str) -> Result<&Frame> {
        if let Some(good) = self.rejected.get(name) {
            return Err(FrameError::UnknownFrame(format!(
                "frame '{name}' is an upstream name the dictionary rejects; use '{good}'")));
        }
        self.frames.get(name).ok_or_else(|| FrameError::UnknownFrame(format!(
            "frame '{name}' is not in the frame dictionary")))
    }

    /// `name` and its ancestors, nearest first, ending at a root.
    pub fn chain(&self, name: &str) -> Result<Vec<String>> {
        self.require(name)?;
        let mut out = Vec::new();
        let mut node = Some(name.to_string());
        while let Some(n) = node {
            node = self.frames[&n].parent.clone();
            out.push(n);
        }
        Ok(out)
    }
}
```

- [ ] **Step 5: Implement `src/extrinsics.rs`**

```rust
use crate::frames::{FrameDict, Kind};
use crate::{FrameError, QUATERNION_NORM_TOLERANCE, Result};
use serde_yaml::Value;
use std::collections::BTreeMap;
use std::path::{Path, PathBuf};

/// One calibrated mounting: the pose of `child` expressed in `parent`.
#[derive(Debug, Clone, PartialEq)]
pub struct Edge {
    pub parent: String,
    pub child: String,
    pub translation_m: [f64; 3],
    pub rotation_xyzw: [f64; 4],
}

/// `up` climbs from `src` to the common ancestor (child -> parent);
/// `down` descends from it to `dst` (parent -> child, applied inverted).
#[derive(Debug, Clone, PartialEq)]
pub struct Route { pub src: String, pub dst: String, pub up: Vec<Edge>, pub down: Vec<Edge> }

#[derive(Debug, Clone, PartialEq)]
pub struct Extrinsics {
    pub robot: String,
    pub source: String,
    pub frames: FrameDict,
    pub edges: BTreeMap<String, Edge>,
    pub path: Option<PathBuf>,
}

const REQUIRED: [&str; 5] = ["contract_version", "robot", "calibrated", "source", "transforms"];

fn numbers<const N: usize>(value: Option<&Value>, label: &str, where_: &str) -> Result<[f64; N]> {
    let Some(seq) = value.and_then(Value::as_sequence).filter(|s| s.len() == N) else {
        return Err(FrameError::Invalid(format!("{where_}: {label} must be a list of {N} numbers, got {value:?}")));
    };
    let mut out = [0.0; N];
    for (i, item) in seq.iter().enumerate() {
        let v = match item {
            Value::Number(n) => n.as_f64(),
            _ => None,
        };
        match v {
            Some(v) if v.is_finite() => out[i] = v,
            _ => return Err(FrameError::Invalid(format!(
                "{where_}: {label} holds {item:?}, which is not a finite number"))),
        }
    }
    Ok(out)
}

impl Extrinsics {
    pub fn load(path: &Path, frames: &FrameDict) -> Result<Self> {
        let text = std::fs::read_to_string(path)
            .map_err(|e| FrameError::Invalid(format!("{}: {e}", path.display())))?;
        Self::parse(&text, frames, Some(path.to_path_buf()))
    }

    pub fn parse(text: &str, frames: &FrameDict, path: Option<PathBuf>) -> Result<Self> {
        let where_ = path.as_ref().map_or("extrinsics".to_string(), |p| p.display().to_string());
        let doc: Value = serde_yaml::from_str(text).map_err(|e| FrameError::Invalid(format!("{where_}: {e}")))?;
        if !doc.is_mapping() {
            return Err(FrameError::Invalid(format!("{where_}: must be a mapping")));
        }
        for key in REQUIRED {
            if doc.get(key).is_none() {
                return Err(FrameError::Invalid(format!("{where_}: missing the required key '{key}'")));
            }
        }
        let Some(entries) = doc["transforms"].as_sequence().filter(|s| !s.is_empty()) else {
            return Err(FrameError::Invalid(format!("{where_}: 'transforms' must be a non-empty list")));
        };
        let mut edges = BTreeMap::new();
        for entry in entries {
            let parent = entry.get("parent").and_then(Value::as_str);
            let child = entry.get("child").and_then(Value::as_str);
            let (Some(parent), Some(child)) = (parent, child) else {
                return Err(FrameError::Invalid(format!("{where_}: parent and child must be frame names, got {entry:?}")));
            };
            let label = format!("{where_}: {parent} -> {child}");
            frames.require(parent)?;
            let frame = frames.require(child)?;
            if frame.kind != Kind::Mounted {
                return Err(FrameError::Invalid(format!(
                    "{label}: '{child}' is {}, and only mounted frames are calibrated; a dynamic edge comes from a published pose",
                    frame.kind.as_str())));
            }
            if frame.parent.as_deref() != Some(parent) {
                return Err(FrameError::Invalid(format!(
                    "{label}: the frame dictionary says '{child}' hangs from {:?}", frame.parent)));
            }
            let translation_m = numbers::<3>(entry.get("translation_m"), "translation_m", &label)?;
            let rotation_xyzw = numbers::<4>(entry.get("rotation_xyzw"), "rotation_xyzw", &label)?;
            let norm = rotation_xyzw.iter().map(|c| c * c).sum::<f64>().sqrt();
            if (norm - 1.0).abs() > QUATERNION_NORM_TOLERANCE {
                return Err(FrameError::Invalid(format!(
                    "{label}: rotation_xyzw has norm {norm}; it must be a unit quaternion, and it is not normalised for you")));
            }
            if edges.contains_key(child) {
                return Err(FrameError::Invalid(format!("{where_}: '{child}' is calibrated more than once")));
            }
            edges.insert(child.to_string(), Edge {
                parent: parent.to_string(), child: child.to_string(), translation_m, rotation_xyzw,
            });
        }
        Ok(Extrinsics {
            robot: doc["robot"].as_str().unwrap_or_default().to_string(),
            source: doc["source"].as_str().unwrap_or_default().to_string(),
            frames: frames.clone(),
            edges,
            path,
        })
    }

    pub fn route(&self, src: &str, dst: &str) -> Result<Route> {
        for name in [src, dst] {
            if self.frames.require(name)?.kind == Kind::None {
                return Err(FrameError::UnknownFrame(
                    "frame 'none' marks a payload with no spatial meaning and is never part of a transform".into()));
            }
        }
        let up_chain = self.frames.chain(src)?;
        let down_chain = self.frames.chain(dst)?;
        let Some(common) = up_chain.iter().find(|n| down_chain.contains(n)).cloned() else {
            return Err(FrameError::MissingExtrinsic(format!("'{src}' and '{dst}' share no ancestor in the frame tree")));
        };
        // Walk the whole route before refusing it: a wired pose can stand in for
        // a dynamic edge but never for a missing calibration, so a missing one wins.
        let mut dynamic = Vec::new();
        let up_children = &up_chain[..up_chain.iter().position(|n| *n == common).unwrap()];
        let down_children = &down_chain[..down_chain.iter().position(|n| *n == common).unwrap()];
        let up = self.edges_above(up_children, src, dst, &mut dynamic)?;
        let mut down = self.edges_above(down_children, src, dst, &mut dynamic)?;
        if let Some(first) = dynamic.first() {
            let parent = self.frames.frames[first].parent.clone().unwrap_or_default();
            return Err(FrameError::DynamicEdge {
                message: format!("'{src}' -> '{dst}' crosses the dynamic edge '{parent}' -> '{first}'; compose with a published pose instead of a static lookup"),
                edges: dynamic.iter().map(|c| (c.clone(), self.frames.frames[c].parent.clone().unwrap_or_default())).collect(),
            });
        }
        down.reverse();
        Ok(Route { src: src.into(), dst: dst.into(), up, down })
    }

    fn edges_above(&self, children: &[String], src: &str, dst: &str, dynamic: &mut Vec<String>) -> Result<Vec<Edge>> {
        let mut out = Vec::new();
        for child in children {
            let frame = &self.frames.frames[child];
            if frame.kind == Kind::Dynamic {
                dynamic.push(child.clone());
                continue;
            }
            match self.edges.get(child) {
                Some(edge) => out.push(edge.clone()),
                None => return Err(FrameError::MissingExtrinsic(format!(
                    "'{src}' -> '{dst}' needs the extrinsic {:?} -> '{child}', which '{}' does not calibrate; a missing extrinsic is never assumed to be identity",
                    frame.parent.as_deref().unwrap_or(""), self.robot))),
            }
        }
        Ok(out)
    }
}
```

- [ ] **Step 6: Copy fixtures and run the tests**

```bash
mkdir -p $D/libraries/transform/tests/fixtures
cp $REF/specs/operators/frames.yaml $D/libraries/transform/tests/fixtures/frames.yml
cp $REF/robots/simulated-mobile-robot/extrinsics.yaml $D/libraries/transform/tests/fixtures/extrinsics.yml
cd $D && cargo test -p dora-transform --test frames_extrinsics
```

Expected: 11 tests pass.

- [ ] **Step 7: Commit**

```bash
cd $D && git add Cargo.toml Cargo.lock libraries/transform
git commit -m "feat(transform): frame dictionary, per-robot extrinsics and routes

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: dora-transform — rigid transforms, lookup, pose, resolve

**Files:**
- Modify: `D/libraries/transform/src/rigid.rs`
- Create: `D/libraries/transform/tests/rigid.rs`

- [ ] **Step 1: Write the failing tests** (`tests/rigid.rs`)

```rust
use dora_transform::rigid::{Transform, lookup, pose_transform, resolve};
use dora_transform::{Extrinsics, FrameDict, FrameError};

const FRAMES: &str = include_str!("fixtures/frames.yml");
const EXTRINSICS: &str = include_str!("fixtures/extrinsics.yml");
fn ex() -> Extrinsics { Extrinsics::parse(EXTRINSICS, &FrameDict::parse(FRAMES).unwrap(), None).unwrap() }

fn close(a: [f64; 3], b: [f64; 3]) -> bool { a.iter().zip(b).all(|(x, y)| (x - y).abs() < 1e-9) }

#[test]
fn non_rigid_matrix_is_refused() {
    let mut m = Transform::identity("a").matrix;
    m[0][0] = 2.0; // scale
    assert!(Transform::new("a", "b", m).is_err());
    let mut r = Transform::identity("a").matrix;
    r[0][0] = -1.0; // reflection
    assert!(Transform::new("a", "b", r).is_err());
    let mut last = Transform::identity("a").matrix;
    last[3][0] = 1.0;
    assert!(Transform::new("a", "b", last).is_err());
}

#[test]
fn then_requires_frames_to_meet() {
    let a = Transform::identity("a");
    let b = Transform::from_parts("b", "c", [0.0; 3], [0.0, 0.0, 0.0, 1.0]).unwrap();
    assert!(matches!(a.then(&b), Err(FrameError::FrameOrder(_))));
}

#[test]
fn rotation_is_read_xyzw() {
    // 90 degrees about z: x axis goes to y.
    let s = std::f64::consts::FRAC_1_SQRT_2;
    let t = Transform::from_parts("a", "b", [0.0; 3], [0.0, 0.0, s, s]).unwrap();
    assert!(close(t.apply([1.0, 0.0, 0.0]), [0.0, 1.0, 0.0]));
}

#[test]
fn inverse_undoes() {
    let t = Transform::from_parts("a", "b", [1.0, 2.0, 3.0], [0.0, 0.0, 0.3826834323650898, 0.9238795325112867]).unwrap();
    let back = t.then(&t.inverse()).unwrap();
    assert!(close(back.apply([4.0, 5.0, 6.0]), [4.0, 5.0, 6.0]));
}

#[test]
fn lookup_lidar_to_base_footprint() {
    let t = lookup(&ex(), "rslidar", "base_footprint").unwrap();
    assert!(close(t.apply([0.0, 0.0, 0.0]), [0.25, 0.0, 0.35]));
}

#[test]
fn lookup_through_dynamic_edge_is_refused() {
    assert!(matches!(lookup(&ex(), "rslidar", "odom"), Err(FrameError::DynamicEdge { .. })));
}

#[test]
fn pose_transform_checks_frames_and_values() {
    let f = FrameDict::parse(FRAMES).unwrap();
    let pose = [1.0, 2.0, 0.0, 0.0, 0.0, 0.0, 1.0];
    let t = pose_transform(&pose, "odom", "base_footprint", &f).unwrap();
    assert_eq!((t.src.as_str(), t.dst.as_str()), ("base_footprint", "odom"));
    assert!(pose_transform(&pose, "base_link", "rslidar", &f).is_err()); // mounted parent
    assert!(pose_transform(&pose, "odom", "none", &f).is_err());
    assert!(pose_transform(&[1.0, 2.0, 0.0, 0.0, 0.0, 0.0, 2.0], "odom", "base_footprint", &f).is_err());
    assert!(pose_transform(&[1.0, 2.0, 0.0], "odom", "base_footprint", &f).is_err());
    assert!(pose_transform(&[f64::NAN, 2.0, 0.0, 0.0, 0.0, 0.0, 1.0], "odom", "base_footprint", &f).is_err());
}

#[test]
fn resolve_upwards_with_pose() {
    let f = FrameDict::parse(FRAMES).unwrap();
    let pose = pose_transform(&[1.0, 2.0, 0.0, 0.0, 0.0, 0.0, 1.0], "odom", "base_footprint", &f).unwrap();
    let (t, used) = resolve(&ex(), "rslidar", "odom", Some(&pose)).unwrap();
    assert!(used);
    assert!(close(t.unwrap().apply([0.0, 0.0, 0.0]), [1.25, 2.0, 0.35]));
}

#[test]
fn resolve_downwards_uses_inverse_pose() {
    let f = FrameDict::parse(FRAMES).unwrap();
    let pose = pose_transform(&[1.0, 2.0, 0.0, 0.0, 0.0, 0.0, 1.0], "odom", "base_footprint", &f).unwrap();
    let (t, used) = resolve(&ex(), "odom", "base_link", Some(&pose)).unwrap();
    assert!(used);
    assert!(close(t.unwrap().apply([1.0, 2.0, 0.1]), [0.0, 0.0, 0.0]));
}

#[test]
fn resolve_static_ignores_pose_and_none_without_pose() {
    let (t, used) = resolve(&ex(), "rslidar", "base_link", None).unwrap();
    assert!(!used && t.is_some());
    let (t, used) = resolve(&ex(), "rslidar", "odom", None).unwrap();
    assert!(!used && t.is_none());
}

#[test]
fn resolve_refuses_a_second_dynamic_edge() {
    let f = FrameDict::parse(FRAMES).unwrap();
    let pose = pose_transform(&[0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0], "odom", "base_footprint", &f).unwrap();
    assert!(matches!(resolve(&ex(), "rslidar", "map", Some(&pose)), Err(FrameError::DynamicEdge { .. })));
}

#[test]
fn apply_packed_moves_xyz_and_keeps_intensity() {
    let t = Transform::from_parts("a", "b", [1.0, 0.0, 0.0], [0.0, 0.0, 0.0, 1.0]).unwrap();
    let pts: Vec<f32> = vec![0.0, 0.0, 0.0, 7.0, 1.0, 1.0, 1.0, 9.0];
    let out = t.apply_packed(&pts, 4).unwrap();
    assert_eq!(out, vec![1.0, 0.0, 0.0, 7.0, 2.0, 1.0, 1.0, 9.0]);
    assert!(t.apply_packed(&pts[..7], 4).is_err());
    assert!(t.apply_packed(&pts, 2).is_err());
}
```

- [ ] **Step 2: Run to verify failure**

Run: `cd $D && cargo test -p dora-transform --test rigid`
Expected: compile errors (module `rigid` empty).

- [ ] **Step 3: Implement `src/rigid.rs`**

```rust
use crate::frames::{FrameDict, Kind};
use crate::{Extrinsics, FrameError, QUATERNION_NORM_TOLERANCE, Result};
use crate::extrinsics::Edge;

pub type Matrix = [[f64; 4]; 4];

fn mul(a: &Matrix, b: &Matrix) -> Matrix {
    let mut out = [[0.0; 4]; 4];
    for i in 0..4 { for j in 0..4 { for k in 0..4 { out[i][j] += a[i][k] * b[k][j]; } } }
    out
}

/// A 3x3 rotation from a unit quaternion in x, y, z, w order.
pub fn rotation_matrix(q: [f64; 4]) -> [[f64; 3]; 3] {
    let [x, y, z, w] = q;
    [
        [1.0 - 2.0 * (y * y + z * z), 2.0 * (x * y - z * w), 2.0 * (x * z + y * w)],
        [2.0 * (x * y + z * w), 1.0 - 2.0 * (x * x + z * z), 2.0 * (y * z - x * w)],
        [2.0 * (x * z - y * w), 2.0 * (y * z + x * w), 1.0 - 2.0 * (x * x + y * y)],
    ]
}

/// Maps coordinates expressed in `src` to coordinates expressed in `dst`.
#[derive(Debug, Clone, PartialEq)]
pub struct Transform { pub src: String, pub dst: String, pub matrix: Matrix }

impl Transform {
    pub fn new(src: impl Into<String>, dst: impl Into<String>, m: Matrix) -> Result<Self> {
        if m.iter().flatten().any(|v| !v.is_finite()) {
            return Err(FrameError::Invalid("a transform is a finite 4x4 matrix".into()));
        }
        let last = [0.0, 0.0, 0.0, 1.0];
        if m[3].iter().zip(last).any(|(a, b)| (a - b).abs() > 1e-8) {
            return Err(FrameError::Invalid("the last row of a rigid transform must be 0 0 0 1".into()));
        }
        // R^T R == I and det(R) > 0
        for i in 0..3 {
            for j in 0..3 {
                let dot: f64 = (0..3).map(|k| m[k][i] * m[k][j]).sum();
                let want = if i == j { 1.0 } else { 0.0 };
                if (dot - want).abs() > 1e-5 {
                    return Err(FrameError::Invalid("the rotation block of a rigid transform must be orthonormal with a positive determinant (no scale, shear or reflection)".into()));
                }
            }
        }
        let det = m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1])
            - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
            + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0]);
        if det <= 0.0 {
            return Err(FrameError::Invalid("the rotation block of a rigid transform must be orthonormal with a positive determinant (no scale, shear or reflection)".into()));
        }
        Ok(Transform { src: src.into(), dst: dst.into(), matrix: m })
    }

    pub fn identity(frame: &str) -> Self {
        let mut m = [[0.0; 4]; 4];
        for (i, row) in m.iter_mut().enumerate() { row[i] = 1.0; }
        Transform { src: frame.into(), dst: frame.into(), matrix: m }
    }

    pub fn from_parts(src: &str, dst: &str, t: [f64; 3], q_xyzw: [f64; 4]) -> Result<Self> {
        let r = rotation_matrix(q_xyzw);
        let mut m = [[0.0; 4]; 4];
        for i in 0..3 { for j in 0..3 { m[i][j] = r[i][j]; } m[i][3] = t[i]; }
        m[3][3] = 1.0;
        Self::new(src, dst, m)
    }

    /// Apply `self`, then `other`.
    pub fn then(&self, other: &Transform) -> Result<Transform> {
        if self.dst != other.src {
            return Err(FrameError::FrameOrder(format!(
                "cannot apply '{}' -> '{}' after '{}' -> '{}'; the frames do not meet",
                other.src, other.dst, self.src, self.dst)));
        }
        Transform::new(self.src.clone(), other.dst.clone(), mul(&other.matrix, &self.matrix))
    }

    pub fn inverse(&self) -> Transform {
        let m = &self.matrix;
        let mut out = [[0.0; 4]; 4];
        for i in 0..3 {
            for j in 0..3 { out[i][j] = m[j][i]; }
            out[i][3] = -(0..3).map(|k| m[k][i] * m[k][3]).sum::<f64>();
        }
        out[3][3] = 1.0;
        Transform { src: self.dst.clone(), dst: self.src.clone(), matrix: out }
    }

    pub fn apply(&self, p: [f64; 3]) -> [f64; 3] {
        let m = &self.matrix;
        let mut out = [0.0; 3];
        for i in 0..3 { out[i] = m[i][0] * p[0] + m[i][1] * p[1] + m[i][2] * p[2] + m[i][3]; }
        out
    }

    /// Transform packed float32 points of `item_step` floats each; only the
    /// first three (x, y, z) move, the rest pass through.
    pub fn apply_packed(&self, points: &[f32], item_step: usize) -> Result<Vec<f32>> {
        if item_step < 3 {
            return Err(FrameError::Invalid(format!("item_step must be >= 3, got {item_step}")));
        }
        if points.len() % item_step != 0 {
            return Err(FrameError::Invalid(format!(
                "{} floats is not a whole number of {item_step}-float points", points.len())));
        }
        let mut out = points.to_vec();
        for chunk in out.chunks_exact_mut(item_step) {
            let p = self.apply([chunk[0] as f64, chunk[1] as f64, chunk[2] as f64]);
            chunk[0] = p[0] as f32; chunk[1] = p[1] as f32; chunk[2] = p[2] as f32;
        }
        Ok(out)
    }
}

/// child -> parent: an edge stores the child's pose in its parent.
pub fn edge_transform(edge: &Edge) -> Result<Transform> {
    Transform::from_parts(&edge.child, &edge.parent, edge.translation_m, edge.rotation_xyzw)
}

/// The static transform from `src` to `dst`. Errors as `Extrinsics::route` does.
pub fn lookup(ex: &Extrinsics, src: &str, dst: &str) -> Result<Transform> {
    let route = ex.route(src, dst)?;
    let mut result = Transform::identity(src);
    for edge in &route.up { result = result.then(&edge_transform(edge)?)?; }
    for edge in &route.down { result = result.then(&edge_transform(edge)?.inverse())?; }
    Ok(result)
}

/// `child_frame -> parent_frame` from one pose: px py pz qx qy qz qw.
pub fn pose_transform(values: &[f64], parent_frame: &str, child_frame: &str, frames: &FrameDict) -> Result<Transform> {
    let parent = frames.require(parent_frame)?;
    if !matches!(parent.kind, Kind::Fixed | Kind::Dynamic) {
        return Err(FrameError::Invalid(format!(
            "a pose is expressed in a fixed or dynamic frame, not the {} frame '{}'", parent.kind.as_str(), parent.name)));
    }
    if frames.require(child_frame)?.kind == Kind::None {
        return Err(FrameError::UnknownFrame(
            "frame 'none' marks a payload with no spatial meaning and is never part of a transform".into()));
    }
    if values.len() != 7 || values.iter().any(|v| !v.is_finite()) {
        return Err(FrameError::Invalid(format!(
            "a pose payload is seven finite values px py pz qx qy qz qw, got {values:?}")));
    }
    let q = [values[3], values[4], values[5], values[6]];
    let norm = q.iter().map(|c| c * c).sum::<f64>().sqrt();
    if (norm - 1.0).abs() > QUATERNION_NORM_TOLERANCE {
        return Err(FrameError::Invalid(format!("the pose orientation has norm {norm}; it must be a unit quaternion")));
    }
    Transform::from_parts(child_frame, parent_frame, [values[0], values[1], values[2]], q)
}

fn through(ex: &Extrinsics, src: &str, dst: &str, moving: &Transform) -> Result<Option<Transform>> {
    let legs = lookup(ex, src, &moving.src)
        .and_then(|a| a.then(moving))
        .and_then(|a| Ok((a, lookup(ex, &moving.dst, dst)?)))
        .and_then(|(a, b)| a.then(&b));
    match legs {
        Ok(t) => Ok(Some(t)),
        Err(FrameError::DynamicEdge { .. }) => Ok(None),
        Err(e) => Err(e),
    }
}

/// The transform for one cloud, and whether it used the pose. A static path
/// never consults the pose; otherwise exactly one dynamic edge, the pose's, is
/// crossed in either direction. With no pose yet there is no transform.
pub fn resolve(ex: &Extrinsics, src: &str, dst: &str, pose: Option<&Transform>) -> Result<(Option<Transform>, bool)> {
    match lookup(ex, src, dst) {
        Ok(t) => return Ok((Some(t), false)),
        Err(FrameError::DynamicEdge { .. }) => {}
        Err(e) => return Err(e),
    }
    let Some(moving) = pose else { return Ok((None, false)) };
    for candidate in [moving.clone(), moving.inverse()] {
        if let Some(t) = through(ex, src, dst, &candidate)? {
            return Ok((Some(t), true));
        }
    }
    Err(FrameError::DynamicEdge {
        message: format!(
            "'{src}' -> '{dst}' cannot be composed with the pose of '{}' in '{}': the route needs a dynamic edge that pose does not give, and one pose covers one dynamic edge",
            moving.src, moving.dst),
        edges: vec![],
    })
}
```

- [ ] **Step 4: Run all transform tests**

Run: `cd $D && cargo test -p dora-transform`
Expected: 23 tests pass (11 + 12).

- [ ] **Step 5: Commit**

```bash
cd $D && git add libraries/transform
git commit -m "feat(transform): rigid transforms, static lookup, pose and resolve

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Required header keys on std types; PointCloud `fields` parameter

**Files:**
- Modify: `D/libraries/core/types/std/media/v1.yml` (`PointCloud`, `Image`)
- Modify: `D/libraries/core/types/std/math/v1.yml` (`Pose`, `Transform`)
- Test: add to the `#[cfg(test)]` module of `D/libraries/core/src/types.rs`

- [ ] **Step 1: Write the failing test** (append inside `mod tests` in `types.rs`)

```rust
    #[test]
    fn spatial_std_types_require_the_header_keys() {
        let reg = TypeRegistry::new();
        let keys = |urn: &str| -> Vec<String> {
            reg.resolve(urn).unwrap().metadata.iter().map(|m| m.key.clone()).collect()
        };
        for urn in ["std/media/v1/PointCloud", "std/media/v1/Image"] {
            let k = keys(urn);
            assert!(k.contains(&"frame_id".to_string()) && k.contains(&"stamp_ns".to_string()), "{urn}: {k:?}");
        }
        for urn in ["std/math/v1/Pose", "std/math/v1/Transform"] {
            let k = keys(urn);
            for want in ["frame_id", "child_frame", "stamp_ns"] {
                assert!(k.contains(&want.to_string()), "{urn}: {k:?}");
            }
        }
        let pc = reg.resolve("std/media/v1/PointCloud").unwrap();
        assert_eq!(pc.params.iter().map(|p| (p.name.as_str(), p.default.as_deref())).collect::<Vec<_>>(),
                   vec![("fields", Some("xyz"))]);
    }
```

- [ ] **Step 2: Run to verify failure**

Run: `cd $D && cargo test -p dora-core spatial_std_types_require_the_header_keys`
Expected: FAIL (empty metadata).

- [ ] **Step 3: Edit the YAML**

In `std/media/v1.yml`, give `PointCloud` (keep its existing `fields:` list unchanged):

```yaml
  PointCloud:
    arrow: Struct
    description: "3D point cloud: packed float32 points (layout given by the `fields` parameter, xyz or xyzi), width and height"
    params:
      - name: fields
        default: xyz
    fields:
      - name: points
        type: LargeBinary
      - name: width
        type: UInt32
      - name: height
        type: UInt32
    metadata:
      - key: frame_id
        description: "Frame the points are expressed in (frame dictionary name)"
      - key: stamp_ns
        description: "Capture time, integer nanoseconds"
```

Add the same two-entry `metadata:` block to `Image`. In `std/math/v1.yml`, add to `Pose` and `Transform`:

```yaml
    metadata:
      - key: frame_id
        description: "Parent frame the pose is expressed in"
      - key: child_frame
        description: "Frame whose pose this is"
      - key: stamp_ns
        description: "Capture time, integer nanoseconds"
```

- [ ] **Step 4: Run the new test, then every dora-core and CLI test**

Run: `cd $D && cargo test -p dora-core && cargo test -p dora-cli`
Expected: the new test passes. If an existing test fails because it built a dataflow emitting `PointCloud`, `Image`, `Pose` or `Transform` without these keys, apply the spec §11 fallback instead of editing that test: move the `metadata:` entries out of the YAML, and add the requirement in Task 7's frame check (only when the dataflow has a `frames:` key). Record which tests forced it in `docs/contract-core/feasibility.md` under `## Friction`.

- [ ] **Step 5: Commit**

```bash
cd $D && git add libraries/core/types libraries/core/src/types.rs docs/contract-core/feasibility.md
git commit -m "feat(types): spatial std types require frame_id and stamp_ns

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Descriptor — frame annotations and the `frames:` key

**Files:**
- Modify: `D/libraries/message/src/descriptor.rs` (struct `Node` after `input_types`; `Node::new` at line ~1038; struct `Descriptor` after `type_rules`; `Descriptor::new`)
- Modify: `D/libraries/core/src/descriptor/classify.rs` (`STANDARD_ALLOWED`, plus any other kind whitelist that lists `output_types`)
- Test: `D/libraries/message/src/descriptor.rs` `mod tests` (or the file's existing test module)

- [ ] **Step 1: Write the failing test**

```rust
    #[test]
    fn frame_annotations_and_frames_key_parse() {
        let yaml = r#"
frames:
  dictionary: robots/r/frames.yml
  extrinsics: robots/r/extrinsics.yml
nodes:
  - id: t
    path: t.py
    inputs:
      cloud: s/cloud
    outputs: [cloud]
    input_frames:
      cloud: any
    output_frames:
      cloud: env:TARGET_FRAME
"#;
        let d: Descriptor = serde_yaml::from_str(yaml).unwrap();
        let f = d.frames.as_ref().unwrap();
        assert_eq!(f.dictionary.to_str(), Some("robots/r/frames.yml"));
        assert_eq!(f.extrinsics.to_str(), Some("robots/r/extrinsics.yml"));
        let n = &d.nodes[0];
        assert_eq!(n.input_frames.get(&"cloud".parse().unwrap()).map(String::as_str), Some("any"));
        assert_eq!(n.output_frames.get(&"cloud".parse().unwrap()).map(String::as_str), Some("env:TARGET_FRAME"));
    }
```

- [ ] **Step 2: Run to verify failure**

Run: `cd $D && cargo test -p dora-message frame_annotations_and_frames_key_parse`
Expected: compile error (no field `frames`).

- [ ] **Step 3: Add the fields**

In `Node`, after `input_types`:

```rust
    /// Frame each output is expressed in: a frame name, `any`,
    /// `same_as:<input id>` or `env:<VAR>` (resolved from this node's `env`).
    /// Checked by `dora validate` when the dataflow has a `frames:` key.
    #[serde(default, skip_serializing_if = "BTreeMap::is_empty")]
    #[schemars(with = "Option<BTreeMap<DataId, String>>")]
    pub output_frames: BTreeMap<DataId, String>,

    /// Frame each input requires: a frame name or `any`.
    #[serde(default, skip_serializing_if = "BTreeMap::is_empty")]
    #[schemars(with = "Option<BTreeMap<DataId, String>>")]
    pub input_frames: BTreeMap<DataId, String>,
```

In `Descriptor`, after `type_rules`:

```rust
    /// Frame dictionary and robot calibration for frame checks.
    ///
    /// ```yaml
    /// frames:
    ///   dictionary: robots/my-robot/frames.yml
    ///   extrinsics: robots/my-robot/extrinsics.yml
    /// ```
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub frames: Option<FramesConfig>,
```

And a new struct next to `TypeRuleDef`:

```rust
/// Paths relative to the dataflow file.
#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema, PartialEq)]
#[serde(deny_unknown_fields)]
pub struct FramesConfig {
    pub dictionary: PathBuf,
    pub extrinsics: PathBuf,
}
```

Add `output_frames: BTreeMap::new(), input_frames: BTreeMap::new(),` to `Node::new`, and `frames: None,` to `Descriptor::new`. Then run `cargo check --workspace` and add the same defaults wherever the compiler reports a struct literal missing these fields.

In `classify.rs`, add `"output_frames"` and `"input_frames"` after `"input_types"` in `STANDARD_ALLOWED`, and in every other whitelist array that contains `"input_types"`.

- [ ] **Step 4: Regenerate the schema and run the tests**

```bash
cd $D && cargo run -p dora-core --bin generate_schema && cargo test -p dora-message -p dora-core
```

Expected: `dora-schema.json` and `libraries/core/dora-schema.json` change; all tests pass.

- [ ] **Step 5: Commit**

```bash
cd $D && git add -A libraries/message libraries/core dora-schema.json
git commit -m "feat(descriptor): frame annotations on ports and a dataflow frames key

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Frame checks in `dora validate`

**Files:**
- Create: `D/libraries/core/src/descriptor/frames_check.rs`
- Modify: `D/libraries/core/src/descriptor/mod.rs` (`pub mod frames_check;`), `D/libraries/core/Cargo.toml` (`dora-transform = { workspace = true }`)
- Modify: `D/binaries/cli/src/command/validate.rs` (call after `check_type_annotations_full`)
- Create: `D/libraries/core/tests/frames_check/` fixtures: `frames.yml`, `extrinsics.yml` (same copies as Task 3)
- Test: `D/libraries/core/tests/frames_check.rs`

The checks, in order (each produces `FrameViolation { node, port, check, message }`):

1. **unknown_frame:** every literal frame in `input_frames`/`output_frames`, and every resolved `env:` value, exists in the dictionary (`FrameDict::require`, whose message names the replacement for a rejected name).
2. **frame (edge):** for each input with a frame other than `any`, the upstream output's resolved frame must equal it. Resolving follows `same_as:` upstream (a cycle is an error) and `env:` from the node's `env`. A missing variable, or a value that is `any`, `none`, `same_as:…` or `env:…`, is an error (message as `REF/.../resolve.py:52-62`). An upstream output that resolves to `any`, or has no `output_frames` entry, is "cannot be checked before launch".
3. **transform (route):** for each node, gather the resolved frames of its data inputs. A data input is any input whose `input_types` is not `std/math/v1/Pose`. Skip frames that are `none`, and skip an input whose frame the input itself refuses (reference `_input_frames`, `validate.py:297-316`). For each output with a resolved frame (not `same_as:`, not `none`) that differs from an input frame, call `Extrinsics::route`.
4. **transform (dynamic):** on `DynamicEdge` with more than one edge, report "crosses N dynamic edges; one pose input covers one". With exactly one, the node must have a wired input typed `std/math/v1/Pose`; otherwise report the route error plus "has no wired std/math/v1/Pose input to compose with".
5. **transform (calibration):** other `FrameError`s from route (missing extrinsic, unknown frame) are reported. A node that changes frames must set `DORA_EXTRINSICS` in its `env`. Its path, resolved relative to the dataflow directory, must equal `frames.extrinsics` resolved the same way; otherwise report "launches with X but was validated against Y; a robot must run the calibration it was checked with".

A dataflow with no `frames:` key returns no violations, and the checks are skipped.

- [ ] **Step 1: Write the failing tests** (`libraries/core/tests/frames_check.rs`)

```rust
use dora_core::descriptor::frames_check::check_frames;
use dora_core::descriptor::Descriptor;
use std::path::Path;

fn run(yaml: &str) -> Vec<String> {
    let base = Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/frames_check");
    let d: Descriptor = serde_yaml::from_str(yaml).unwrap();
    check_frames(&d, &base).into_iter().map(|v| format!("{}:{}:{}: {}", v.check, v.node, v.port, v.message)).collect()
}

const HEAD: &str = "frames: {dictionary: frames.yml, extrinsics: extrinsics.yml}\nnodes:\n";

const SIM: &str = r#"
  - id: sim
    path: sim.py
    outputs: [cloud, odom_pose]
    output_types: {cloud: std/media/v1/PointCloud, odom_pose: std/math/v1/Pose}
    output_frames: {cloud: rslidar, odom_pose: odom}
"#;

fn transform_node(target: &str, with_pose: bool, extrinsics: &str) -> String {
    let pose_in = if with_pose { "      pose: sim/odom_pose\n" } else { "" };
    format!(r#"
  - id: ft
    path: ft.py
    inputs:
      cloud: sim/cloud
{pose_in}    input_types: {{cloud: std/media/v1/PointCloud, pose: std/math/v1/Pose}}
    input_frames: {{cloud: any}}
    outputs: [cloud]
    output_frames: {{cloud: env:TARGET_FRAME}}
    env: {{TARGET_FRAME: {target}, DORA_EXTRINSICS: {extrinsics}}}
"#)
}

#[test]
fn good_chain_passes() {
    let v = run(&format!("{HEAD}{SIM}{}", transform_node("odom", true, "extrinsics.yml")));
    assert!(v.is_empty(), "{v:?}");
}

#[test]
fn no_frames_key_means_no_checks() {
    let yaml = format!("nodes:\n{SIM}").replace("rslidar", "nowhere");
    assert!(run(&yaml).is_empty());
}

#[test]
fn unknown_and_rejected_frames() {
    let v = run(&format!("{HEAD}{}", SIM.replace("cloud: rslidar", "cloud: lidar_link")));
    assert!(v.iter().any(|m| m.starts_with("unknown_frame:sim:cloud") && m.contains("'rslidar'")), "{v:?}");
}

#[test]
fn edge_frame_mismatch() {
    let sink = "\n  - id: sink\n    path: s.py\n    inputs: {cloud: sim/cloud}\n    input_frames: {cloud: base_link}\n";
    let v = run(&format!("{HEAD}{SIM}{sink}"));
    assert!(v.iter().any(|m| m.starts_with("frame:sink:cloud") && m.contains("'base_link'") && m.contains("'rslidar'")), "{v:?}");
}

#[test]
fn env_target_must_be_a_real_frame() {
    for bad in ["any", "none", "same_as:cloud", "env:X"] {
        let v = run(&format!("{HEAD}{SIM}{}", transform_node(&format!("\"{bad}\""), true, "extrinsics.yml")));
        assert!(v.iter().any(|m| m.starts_with("frame:ft:cloud") || m.starts_with("unknown_frame:ft:cloud")), "{bad}: {v:?}");
    }
}

#[test]
fn dynamic_edge_without_pose_input() {
    let v = run(&format!("{HEAD}{SIM}{}", transform_node("odom", false, "extrinsics.yml")));
    assert!(v.iter().any(|m| m.starts_with("transform:ft:cloud") && m.contains("std/math/v1/Pose")), "{v:?}");
}

#[test]
fn two_dynamic_edges_refused_even_with_pose() {
    let v = run(&format!("{HEAD}{SIM}{}", transform_node("map", true, "extrinsics.yml")));
    assert!(v.iter().any(|m| m.contains("crosses 2 dynamic edges")), "{v:?}");
}

#[test]
fn missing_calibration_refused() {
    let yaml = format!("{HEAD}{SIM}{}", transform_node("odom", true, "extrinsics-no-base.yml"))
        .replace("extrinsics: extrinsics.yml", "extrinsics: extrinsics-no-base.yml");
    let v = run(&yaml);
    assert!(v.iter().any(|m| m.contains("never assumed to be identity")), "{v:?}");
}

#[test]
fn launch_calibration_must_match_checked_one() {
    let v = run(&format!("{HEAD}{SIM}{}", transform_node("odom", true, "other.yml")));
    assert!(v.iter().any(|m| m.contains("a robot must run the calibration it was checked with")), "{v:?}");
}

#[test]
fn frame_change_without_extrinsics_env() {
    let yaml = format!("{HEAD}{SIM}{}", transform_node("odom", true, "x")).replace(", DORA_EXTRINSICS: x", "");
    let v = run(&yaml);
    assert!(v.iter().any(|m| m.contains("sets no DORA_EXTRINSICS")), "{v:?}");
}
```

Fixtures: `tests/frames_check/frames.yml` and `extrinsics.yml` (the Task 3 copies), plus `extrinsics-no-base.yml`, the same file with the `base_footprint -> base_link` entry removed.

- [ ] **Step 2: Run to verify failure**

Run: `cd $D && cargo test -p dora-core --test frames_check`
Expected: compile error (`frames_check` not found).

- [ ] **Step 3: Implement `frames_check.rs`**

```rust
//! Pre-launch frame checks, run by `dora validate` when the dataflow has a
//! `frames:` key. Ported from the operator contract's validator checks 2 and 6.

use crate::descriptor::Descriptor;
use dora_message::descriptor::{EnvValue, Node};
use dora_transform::{Extrinsics, FrameDict, FrameError, Kind};
use std::collections::BTreeMap;
use std::fmt;
use std::path::{Path, PathBuf};

pub const POSE_TYPE: &str = "std/math/v1/Pose";
pub const EXTRINSICS_ENV: &str = "DORA_EXTRINSICS";

#[derive(Debug, Clone, PartialEq)]
pub struct FrameViolation { pub check: &'static str, pub node: String, pub port: String, pub message: String }

impl fmt::Display for FrameViolation {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "[{}] {}/{}: {}", self.check, self.node, self.port, self.message)
    }
}

struct Ctx<'a> {
    nodes: BTreeMap<String, &'a Node>,
    frames: FrameDict,
}

fn env(node: &Node, var: &str) -> Option<String> {
    node.env.as_ref()?.get(var).map(EnvValue::to_string)
}

fn upstream(node: &Node, input: &str) -> Option<(String, String)> {
    let input = node.inputs.get(&input.parse().ok()?)?;
    // `Input`'s mapping renders as "node/output" for user sources.
    let s = input.mapping.to_string();
    let (n, o) = s.split_once('/')?;
    if n == "dora" { return None; }
    Some((n.to_string(), o.to_string()))
}

impl<'a> Ctx<'a> {
    /// The frame an output resolves to, following same_as: and env:.
    fn resolve(&self, node_id: &str, port: &str, seen: &mut Vec<(String, String)>) -> Result<String, String> {
        let here = (node_id.to_string(), port.to_string());
        if seen.contains(&here) {
            let path: Vec<String> = seen.iter().chain([&here]).map(|(n, p)| format!("{n}.{p}")).collect();
            return Err(format!("frame resolution cycle: {}", path.join(" -> ")));
        }
        seen.push(here);
        let node = self.nodes.get(node_id).ok_or(format!("node '{node_id}' is not in the dataflow"))?;
        let Some(declared) = node.output_frames.get(&port.parse().map_err(|e| format!("{e}"))?) else {
            return Ok("any".into());
        };
        if let Some(target) = declared.strip_prefix("same_as:") {
            let (n, o) = upstream(node, target)
                .ok_or(format!("{node_id}.{target} is unwired, so {node_id}.{port} cannot resolve same_as:{target}"))?;
            return self.resolve(&n, &o, seen);
        }
        if let Some(var) = declared.strip_prefix("env:") {
            let value = env(node, var).filter(|v| !v.is_empty()).ok_or(format!(
                "{node_id}.{port} declares env:{var}, but node '{node_id}' sets no {var} in its env"))?;
            if value == "any" || value == "none" || value.starts_with("same_as:") || value.starts_with("env:") {
                return Err(format!(
                    "{node_id}.{port} declares env:{var}, and node '{node_id}' sets {var} to '{value}', which is not a frame; an env frame must name one frame, never 'any', 'none', same_as: or env:"));
            }
            return Ok(value);
        }
        Ok(declared.clone())
    }
}

pub fn check_frames(dataflow: &Descriptor, base_dir: &Path) -> Vec<FrameViolation> {
    let Some(cfg) = &dataflow.frames else { return vec![] };
    let mut out = Vec::new();
    let mut push = |check: &'static str, node: &str, port: &str, message: String| {
        out.push(FrameViolation { check, node: node.into(), port: port.into(), message });
    };
    let dict_path = base_dir.join(&cfg.dictionary);
    let ex_path = base_dir.join(&cfg.extrinsics);
    let frames = match FrameDict::load(&dict_path) {
        Ok(f) => f,
        Err(e) => { push("transform", "-", "frames.dictionary", e.to_string()); return out; }
    };
    let extrinsics = Extrinsics::load(&ex_path, &frames);
    let ctx = Ctx { nodes: dataflow.nodes.iter().map(|n| (n.id.to_string(), n)).collect(), frames };

    // check 1: literal frames exist
    for node in &dataflow.nodes {
        for (port, f) in node.output_frames.iter().chain(node.input_frames.iter()) {
            if f == "any" || f.starts_with("same_as:") || f.starts_with("env:") { continue; }
            if let Err(e) = ctx.frames.require(f) { push("unknown_frame", &node.id.to_string(), &port.to_string(), e.to_string()); }
        }
    }

    // check 2: edges agree
    for node in &dataflow.nodes {
        let nid = node.id.to_string();
        for (port, want) in &node.input_frames {
            if want == "any" { continue; }
            let Some((un, uo)) = upstream(node, &port.to_string()) else { continue };
            match ctx.resolve(&un, &uo, &mut vec![]) {
                Err(e) => push("frame", &nid, &port.to_string(), e),
                Ok(actual) if actual == "any" => push("frame", &nid, &port.to_string(), format!(
                    "requires frame '{want}' but {un}/{uo} declares 'any', which cannot be checked before launch")),
                Ok(actual) if &actual != want => push("frame", &nid, &port.to_string(), format!(
                    "requires frame '{want}' but {un}/{uo} resolves to '{actual}'")),
                Ok(_) => {}
            }
        }
    }

    // checks 3-5: a frame change needs a calibration that supports it
    for node in &dataflow.nodes {
        let nid = node.id.to_string();
        let is_pose = |p: &str| node.input_types.iter().any(|(k, t)| k.to_string() == p && t == POSE_TYPE);
        let mut inputs = Vec::new();
        for port in node.inputs.keys() {
            let p = port.to_string();
            if is_pose(&p) { continue; }
            let Some((un, uo)) = upstream(node, &p) else { continue };
            let Ok(frame) = ctx.resolve(&un, &uo, &mut vec![]) else { continue };
            if frame == "any" || ctx.frames.frames.get(&frame).is_some_and(|f| f.kind == Kind::None) { continue; }
            let want = node.input_frames.get(port).map(String::as_str).unwrap_or("any");
            if want != "any" && want != frame { continue; } // check 2's violation
            inputs.push(frame);
        }
        let mut changes = Vec::new();
        for (port, declared) in &node.output_frames {
            if declared.starts_with("same_as:") { continue; }
            let p = port.to_string();
            let out_frame = match ctx.resolve(&nid, &p, &mut vec![]) {
                Ok(f) => f,
                Err(e) => { if declared.starts_with("env:") { push("frame", &nid, &p, e); } continue; }
            };
            if let Err(e) = ctx.frames.require(&out_frame) {
                if declared.starts_with("env:") { push("unknown_frame", &nid, &p, e.to_string()); }
                continue;
            }
            if out_frame == "any" || ctx.frames.frames[&out_frame].kind == Kind::None { continue; }
            for src in &inputs { if *src != out_frame { changes.push((src.clone(), out_frame.clone(), p.clone())); } }
        }
        for (src, dst, port) in &changes {
            let ex = match &extrinsics { Ok(e) => e, Err(e) => { push("transform", &nid, port, e.to_string()); continue; } };
            match ex.route(src, dst) {
                Ok(_) => {}
                Err(FrameError::DynamicEdge { message, edges }) => {
                    let wired_pose = node.inputs.keys().any(|k| is_pose(&k.to_string()));
                    if edges.len() > 1 {
                        push("transform", &nid, port, format!(
                            "'{src}' -> '{dst}' crosses {} dynamic edges; one pose input covers one", edges.len()));
                    } else if !wired_pose {
                        push("transform", &nid, port, format!(
                            "{message}; node '{nid}' has no wired {POSE_TYPE} input to compose with"));
                    }
                }
                Err(e) => push("transform", &nid, port, e.to_string()),
            }
        }
        match env(node, EXTRINSICS_ENV) {
            Some(named) => {
                let launched = normalize(&base_dir.join(&named));
                let checked = normalize(&ex_path);
                if launched != checked {
                    push("transform", &nid, EXTRINSICS_ENV, format!(
                        "launches with {} but was validated against {}; a robot must run the calibration it was checked with",
                        launched.display(), checked.display()));
                }
            }
            None if !changes.is_empty() => push("transform", &nid, EXTRINSICS_ENV, format!(
                "changes frames but sets no {EXTRINSICS_ENV}, so the node cannot load a calibration")),
            None => {}
        }
    }
    out
}

fn normalize(p: &Path) -> PathBuf {
    p.canonicalize().unwrap_or_else(|_| p.components().collect())
}
```

If `Input`'s mapping does not render as `node/output`, open `libraries/message/src/config.rs` (`InputMapping`) and use its `User(UserInputMapping { source, output })` variant directly in `upstream()`. Note this in `feasibility.md`.

- [ ] **Step 4: Wire into the CLI** (`binaries/cli/src/command/validate.rs`, after the type-annotation block and before `Ok(())`)

```rust
    let frame_violations = dora_core::descriptor::frames_check::check_frames(&descriptor, working_dir);
    if descriptor.frames.is_some() {
        if frame_violations.is_empty() {
            println!("Frames OK.");
        } else {
            println!("Frame errors:");
            for v in &frame_violations {
                println!("  - {v}");
            }
            bail!("{} frame error(s) found", frame_violations.len());
        }
    }
```

- [ ] **Step 5: Run the tests**

Run: `cd $D && cargo test -p dora-core --test frames_check && cargo test -p dora-cli`
Expected: 10 frames_check tests pass; CLI tests still pass.

- [ ] **Step 6: Commit**

```bash
cd $D && git add libraries/core binaries/cli Cargo.lock
git commit -m "feat(validate): frame, route and calibration checks before launch

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: C API — send an output with metadata parameters

**Files:**
- Modify: `D/apis/c/node/src/lib.rs`, `D/apis/c/node/node_api.h`
- Create: `D/examples/c-header/node.c`, `receiver.py`, `dataflow.yml`, `build.sh`

- [ ] **Step 1: Write the failing Rust unit test** (in `apis/c/node/src/lib.rs` `mod tests`)

```rust
    #[test]
    fn params_convert_with_types_and_refuse_bad_input() {
        let key = b"frame_id";
        let val = b"rslidar";
        let seq = b"seq";
        let params = [
            DoraParam { key: key.as_ptr().cast(), key_len: key.len(), kind: DoraParamKind::String,
                        value: DoraParamValue { s: DoraStr { ptr: val.as_ptr().cast(), len: val.len() } } },
            DoraParam { key: seq.as_ptr().cast(), key_len: seq.len(), kind: DoraParamKind::Int,
                        value: DoraParamValue { i: 7 } },
        ];
        let out = unsafe { params_to_metadata(params.as_ptr(), params.len()) }.unwrap();
        assert_eq!(out.get("frame_id"), Some(&Parameter::String("rslidar".into())));
        assert_eq!(out.get("seq"), Some(&Parameter::Integer(7)));
        assert!(unsafe { params_to_metadata(std::ptr::null(), 0) }.unwrap().is_empty());
        assert!(unsafe { params_to_metadata(std::ptr::null(), 1) }.is_err());
        let bad = [0xffu8, 0xfe];
        let p = [DoraParam { key: bad.as_ptr().cast(), key_len: 2, kind: DoraParamKind::Bool, value: DoraParamValue { b: true } }];
        assert!(unsafe { params_to_metadata(p.as_ptr(), 1) }.is_err());
    }
```

- [ ] **Step 2: Run to verify failure**

Run: `cd $D && cargo test -p dora-node-api-c params_convert`
Expected: compile error.

- [ ] **Step 3: Implement** (in `lib.rs`, after `dora_send_output`; import `dora_node_api::{MetadataParameters, Parameter}`, or `dora_message::metadata::*` as the crate already re-exports)

```rust
#[repr(C)]
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum DoraParamKind { Bool = 0, Int = 1, Float = 2, String = 3 }

#[repr(C)]
#[derive(Clone, Copy)]
pub struct DoraStr { pub ptr: *const c_char, pub len: usize }

#[repr(C)]
#[derive(Clone, Copy)]
pub union DoraParamValue { pub b: bool, pub i: i64, pub f: f64, pub s: DoraStr }

#[repr(C)]
pub struct DoraParam { pub key: *const c_char, pub key_len: usize, pub kind: DoraParamKind, pub value: DoraParamValue }

unsafe fn utf8<'a>(ptr: *const c_char, len: usize, what: &str) -> eyre::Result<&'a str> {
    if ptr.is_null() && len > 0 { eyre::bail!("{what}: null pointer with non-zero length"); }
    let bytes = if len == 0 { &[][..] } else { unsafe { slice::from_raw_parts(ptr.cast::<u8>(), len) } };
    Ok(std::str::from_utf8(bytes).map_err(|e| eyre::eyre!("{what}: invalid UTF-8: {e}"))?)
}

unsafe fn params_to_metadata(params: *const DoraParam, n: usize) -> eyre::Result<MetadataParameters> {
    let mut out = MetadataParameters::new();
    if n == 0 { return Ok(out); }
    if params.is_null() { eyre::bail!("params is null with n_params > 0"); }
    for p in unsafe { slice::from_raw_parts(params, n) } {
        let key = unsafe { utf8(p.key, p.key_len, "param key") }?;
        if key.is_empty() { eyre::bail!("param key is empty"); }
        let value = match p.kind {
            DoraParamKind::Bool => Parameter::Bool(unsafe { p.value.b }),
            DoraParamKind::Int => Parameter::Integer(unsafe { p.value.i }),
            DoraParamKind::Float => Parameter::Float(unsafe { p.value.f }),
            DoraParamKind::String => {
                let s = unsafe { p.value.s };
                Parameter::String(unsafe { utf8(s.ptr, s.len, key) }?.to_string())
            }
        };
        out.insert(key.to_string(), value);
    }
    Ok(out)
}

/// Like [`dora_send_output`], with metadata parameters. `params` may be NULL
/// when `n_params` is 0. Returns 0 on success, -1 on error (nothing is sent).
///
/// ## Safety
/// As for `dora_send_output`; each key and string value must be a valid
/// pointer/length pair.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn dora_send_output_with_params(
    context: *mut c_void, id_ptr: *const u8, id_len: usize, data_ptr: *const u8, data_len: usize,
    params: *const DoraParam, n_params: usize,
) -> c_int {
    let result = (|| -> eyre::Result<()> {
        let metadata = unsafe { params_to_metadata(params, n_params) }?;
        if context.is_null() || id_ptr.is_null() { eyre::bail!("null pointer passed to dora_send_output_with_params"); }
        let context: &mut DoraContext = unsafe { &mut *context.cast() };
        let id = std::str::from_utf8(unsafe { slice::from_raw_parts(id_ptr, id_len) })?;
        let output_id = id.parse::<dora_node_api::dora_core::config::DataId>()
            .map_err(|e| eyre::eyre!("invalid output id `{id}`: {e}"))?;
        let data = unsafe { data_slice(data_ptr, data_len) }?;
        Ok(context.node.send_output_raw(output_id, metadata, data.len(), |out| out.copy_from_slice(data))?)
    })();
    match result { Ok(()) => 0, Err(err) => { tracing::error!("{err:?}"); -1 } }
}
```

In `node_api.h`, after `dora_send_output`:

```c
typedef enum { DORA_PARAM_BOOL = 0, DORA_PARAM_INT = 1, DORA_PARAM_FLOAT = 2, DORA_PARAM_STRING = 3 } DoraParamKind;
typedef struct { const char *ptr; size_t len; } DoraStr;
typedef union { bool b; int64_t i; double f; DoraStr s; } DoraParamValue;
typedef struct { const char *key; size_t key_len; DoraParamKind kind; DoraParamValue value; } DoraParam;

/* Thread-safe: NO. As dora_send_output, plus metadata parameters.
 * `params` may be NULL when `n_params` is 0. Returns 0, or -1 and sends nothing. */
int dora_send_output_with_params(void *dora_context, const char *id_ptr, size_t id_len,
                                 const char *data_ptr, size_t data_len,
                                 const DoraParam *params, size_t n_params);
```

Add `#include <stdbool.h>` and `#include <stdint.h>` at the top if missing.

- [ ] **Step 4: The C example** (used for the live check in Task 13)

`examples/c-header/node.c`:

```c
#include <stdio.h>
#include <string.h>
#include "../../apis/c/node/node_api.h"

static DoraParam str_param(const char *k, const char *v) {
    DoraParam p = { k, strlen(k), DORA_PARAM_STRING, { .s = { v, strlen(v) } } };
    return p;
}

int main(void) {
    void *ctx = init_dora_context_from_env();
    if (!ctx) { fprintf(stderr, "no dora context\n"); return 1; }
    for (int64_t seq = 0; seq < 10; seq++) {
        void *event = dora_next_event(ctx);
        if (!event) break;
        if (read_dora_event_type(event) != DoraEventType_Input) { free_dora_event(event); break; }
        DoraParam params[5] = {
            str_param("frame_id", "rslidar"),
            { "seq", 3, DORA_PARAM_INT, { .i = seq } },
            { "stamp_ns", 8, DORA_PARAM_INT, { .i = 1000 + seq } },
            str_param("source", "c-header"),
            str_param("validity", "ok"),
        };
        const char data[] = "x";
        if (dora_send_output_with_params(ctx, "out", 3, data, 1, params, 5) != 0) return 2;
        free_dora_event(event);
    }
    free_dora_context(ctx);
    return 0;
}
```

`examples/c-header/receiver.py`:

```python
"""Assert every header key a C node sent arrives with its type."""
from dora import Node

seen = 0
for event in Node():
    if event["type"] != "INPUT":
        continue
    m = event["metadata"]
    assert m["frame_id"] == "rslidar", m
    assert isinstance(m["seq"], int) and m["seq"] == seen, m
    assert m["stamp_ns"] == 1000 + seen, m
    assert m["source"] == "c-header" and m["validity"] == "ok", m
    seen += 1
    if seen == 10:
        print("C_HEADER_OK")
        break
```

`examples/c-header/dataflow.yml`:

```yaml
nodes:
  - id: c_node
    path: build/c_node
    inputs:
      tick: dora/timer/millis/50
    outputs: [out]
  - id: receiver
    path: receiver.py
    inputs:
      out: c_node/out
```

`examples/c-header/build.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
root=$(cd "$here/../.." && pwd)
cargo build -p dora-node-api-c --release --manifest-path "$root/Cargo.toml"
mkdir -p "$here/build"
cc "$here/node.c" -o "$here/build/c_node" -L "$root/target/release" -ldora_node_api_c -lm -lpthread -ldl -lrt
```

- [ ] **Step 5: Run the unit test and build the example**

```bash
cd $D && cargo test -p dora-node-api-c && bash examples/c-header/build.sh && ls -l examples/c-header/build/c_node
```

Expected: tests pass and the binary exists. If linking needs other system libraries, copy the link line from `examples/c-dataflow/run.rs`.

- [ ] **Step 6: Commit**

```bash
cd $D && git add apis/c/node examples/c-header
git commit -m "feat(c-api): dora_send_output_with_params for C nodes

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: `dora.transform` Python binding

**Files:**
- Create: `D/apis/python/node/src/transform.rs`
- Modify: `D/apis/python/node/src/lib.rs` (`mod transform;` and register the submodule in `fn dora`), `D/apis/python/node/Cargo.toml` (`dora-transform = { workspace = true }`)
- Create: `D/apis/python/node/tests/test_transform.py`

- [ ] **Step 1: Write the failing Python test**

```python
"""dora.transform: the Rust transform library seen from Python."""
from pathlib import Path

import numpy as np
import pytest

from dora import transform as tf

FIX = Path(__file__).resolve().parents[4] / "libraries/transform/tests/fixtures"


@pytest.fixture
def ex():
    frames = tf.FrameDict.load(str(FIX / "frames.yml"))
    return tf.Extrinsics.load(str(FIX / "extrinsics.yml"), frames)


def test_lookup_and_apply_packed(ex):
    t = tf.lookup(ex, "rslidar", "base_footprint")
    out = np.frombuffer(t.apply_packed(np.zeros(4, dtype="<f4").tobytes(), 4), dtype="<f4")
    assert np.allclose(out, [0.25, 0.0, 0.35, 0.0])


def test_errors_are_typed(ex):
    with pytest.raises(tf.DynamicEdgeError) as e:
        tf.lookup(ex, "rslidar", "map")
    assert len(e.value.args[1]) == 2
    with pytest.raises(tf.UnknownFrameError, match="'rslidar'"):
        tf.lookup(ex, "lidar_link", "base_link")
    assert issubclass(tf.MissingExtrinsicError, tf.FrameError)
    assert issubclass(tf.FrameError, ValueError)


def test_resolve_with_pose(ex):
    pose = tf.pose_transform([1.0, 2.0, 0.0, 0.0, 0.0, 0.0, 1.0], "odom", "base_footprint", ex.frames)
    t, used = tf.resolve(ex, "rslidar", "odom", pose)
    assert used
    assert np.allclose(t.apply([0.0, 0.0, 0.0]), [1.25, 2.0, 0.35])
    assert tf.resolve(ex, "rslidar", "odom", None) == (None, False)


def test_frame_kind(ex):
    assert ex.frames.kind("none") == "none"
    assert ex.frames.kind("rslidar") == "mounted"
```

- [ ] **Step 2: Run to verify failure**

Run: `cd $D/apis/python/node && PYTHONPATH= $VENV/bin/python -m pytest tests/test_transform.py -q`
Expected: `ImportError: cannot import name 'transform'`.

- [ ] **Step 3: Implement `src/transform.rs`**

```rust
use dora_transform::{Extrinsics, FrameDict, FrameError, rigid};
use pyo3::create_exception;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use std::path::Path;

create_exception!(transform, PyFrameError, PyValueError, "A frame or calibration problem.");
create_exception!(transform, PyUnknownFrameError, PyFrameError);
create_exception!(transform, PyMissingExtrinsicError, PyFrameError);
create_exception!(transform, PyDynamicEdgeError, PyFrameError);
create_exception!(transform, PyFrameOrderError, PyFrameError);

fn to_py(e: FrameError) -> PyErr {
    match e {
        FrameError::Invalid(m) => PyFrameError::new_err(m),
        FrameError::UnknownFrame(m) => PyUnknownFrameError::new_err(m),
        FrameError::MissingExtrinsic(m) => PyMissingExtrinsicError::new_err(m),
        FrameError::FrameOrder(m) => PyFrameOrderError::new_err(m),
        FrameError::DynamicEdge { message, edges } => PyDynamicEdgeError::new_err((message, edges)),
    }
}

#[pyclass(name = "FrameDict", module = "dora.transform", frozen)]
#[derive(Clone)]
pub struct PyFrameDict(pub FrameDict);

#[pymethods]
impl PyFrameDict {
    #[staticmethod]
    fn load(path: &str) -> PyResult<Self> { FrameDict::load(Path::new(path)).map(Self).map_err(to_py) }
    fn kind(&self, name: &str) -> PyResult<&'static str> { Ok(self.0.require(name).map_err(to_py)?.kind.as_str()) }
    fn require(&self, name: &str) -> PyResult<()> { self.0.require(name).map(|_| ()).map_err(to_py) }
}

#[pyclass(name = "Extrinsics", module = "dora.transform", frozen)]
pub struct PyExtrinsics(pub Extrinsics);

#[pymethods]
impl PyExtrinsics {
    #[staticmethod]
    fn load(path: &str, frames: &PyFrameDict) -> PyResult<Self> {
        Extrinsics::load(Path::new(path), &frames.0).map(Self).map_err(to_py)
    }
    #[getter]
    fn frames(&self) -> PyFrameDict { PyFrameDict(self.0.frames.clone()) }
    #[getter]
    fn path(&self) -> Option<String> { self.0.path.as_ref().map(|p| p.display().to_string()) }
}

#[pyclass(name = "Transform", module = "dora.transform", frozen)]
#[derive(Clone)]
pub struct PyTransform(pub rigid::Transform);

#[pymethods]
impl PyTransform {
    #[getter] fn src(&self) -> String { self.0.src.clone() }
    #[getter] fn dst(&self) -> String { self.0.dst.clone() }
    #[getter] fn matrix(&self) -> [[f64; 4]; 4] { self.0.matrix }
    fn then(&self, other: &PyTransform) -> PyResult<Self> { self.0.then(&other.0).map(Self).map_err(to_py) }
    fn inverse(&self) -> Self { Self(self.0.inverse()) }
    fn apply(&self, p: [f64; 3]) -> [f64; 3] { self.0.apply(p) }
    /// Packed little-endian float32 points, `item_step` floats each; returns new bytes.
    fn apply_packed<'py>(&self, py: Python<'py>, data: &[u8], item_step: usize) -> PyResult<Bound<'py, pyo3::types::PyBytes>> {
        if data.len() % 4 != 0 { return Err(PyFrameError::new_err("point bytes are not a whole number of float32")); }
        let pts: Vec<f32> = data.chunks_exact(4).map(|c| f32::from_le_bytes([c[0], c[1], c[2], c[3]])).collect();
        let out = self.0.apply_packed(&pts, item_step).map_err(to_py)?;
        let bytes: Vec<u8> = out.iter().flat_map(|v| v.to_le_bytes()).collect();
        Ok(pyo3::types::PyBytes::new(py, &bytes))
    }
}

#[pyfunction]
fn lookup(ex: &PyExtrinsics, src: &str, dst: &str) -> PyResult<PyTransform> {
    rigid::lookup(&ex.0, src, dst).map(PyTransform).map_err(to_py)
}

#[pyfunction]
fn pose_transform(values: Vec<f64>, parent_frame: &str, child_frame: &str, frames: &PyFrameDict) -> PyResult<PyTransform> {
    rigid::pose_transform(&values, parent_frame, child_frame, &frames.0).map(PyTransform).map_err(to_py)
}

#[pyfunction]
#[pyo3(signature = (ex, src, dst, pose=None))]
fn resolve(ex: &PyExtrinsics, src: &str, dst: &str, pose: Option<&PyTransform>) -> PyResult<(Option<PyTransform>, bool)> {
    let (t, used) = rigid::resolve(&ex.0, src, dst, pose.map(|p| &p.0)).map_err(to_py)?;
    Ok((t.map(PyTransform), used))
}

pub fn register(parent: &Bound<'_, PyModule>) -> PyResult<()> {
    let py = parent.py();
    let m = PyModule::new(py, "transform")?;
    m.add_class::<PyFrameDict>()?;
    m.add_class::<PyExtrinsics>()?;
    m.add_class::<PyTransform>()?;
    m.add_function(wrap_pyfunction!(lookup, &m)?)?;
    m.add_function(wrap_pyfunction!(pose_transform, &m)?)?;
    m.add_function(wrap_pyfunction!(resolve, &m)?)?;
    m.add("FrameError", py.get_type::<PyFrameError>())?;
    m.add("UnknownFrameError", py.get_type::<PyUnknownFrameError>())?;
    m.add("MissingExtrinsicError", py.get_type::<PyMissingExtrinsicError>())?;
    m.add("DynamicEdgeError", py.get_type::<PyDynamicEdgeError>())?;
    m.add("FrameOrderError", py.get_type::<PyFrameOrderError>())?;
    parent.add_submodule(&m)?;
    // `from dora import transform` needs the submodule in sys.modules.
    py.import("sys")?.getattr("modules")?.set_item("dora.transform", &m)?;
    Ok(())
}
```

In `lib.rs`: add `mod transform;` near the other `mod` lines, and `transform::register(&m)?;` in `fn dora` before `Ok(())`. If the package ships a Python-side `dora/__init__.py` that re-exports from the native module, add `from .dora import transform` there. Check `apis/python/node/dora/__init__.py`.

- [ ] **Step 4: Rebuild and test**

```bash
cd $D/apis/python/node && VIRTUAL_ENV=$VENV $VENV/bin/maturin develop --release
PYTHONPATH= $VENV/bin/python -m pytest tests/test_transform.py -q
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
cd $D && git add apis/python/node Cargo.lock
git commit -m "feat(python): dora.transform binding over dora-transform

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: frame-transform node

**Files:**
- Create: `D/nodes/frame-transform/pyproject.toml`, `dora-node.yml`, `README.md`
- Create: `D/nodes/frame-transform/dora_frame_transform/__init__.py`, `core.py` (pure functions), `main.py` (node loop)
- Create: `D/nodes/frame-transform/tests/test_core.py`

Payload conventions (used by DORA_NAV in Task 11):
- `std/media/v1/PointCloud` is a one-row Arrow struct `{points: large_binary, width: uint32, height: uint32}`. `points` is packed little-endian float32, `item_step` floats per point (3 for `xyz`, 4 for `xyzi`), `width` = number of points, `height` = 1.
- `std/math/v1/Pose` is a one-row Arrow struct `{position: {x,y,z}, orientation: {x,y,z,w}}`, all float64.

- [ ] **Step 1: Write the failing tests** (`tests/test_core.py`)

```python
from pathlib import Path

import numpy as np
import pyarrow as pa
import pytest

from dora import transform as tf
from dora_frame_transform.core import (
    POSE_MAX_AGE_MS, Header, Pose, cloud_from_arrow, cloud_to_arrow, on_pose, process,
)

FIX = Path(__file__).resolve().parents[3] / "libraries/transform/tests/fixtures"


@pytest.fixture
def ex():
    return tf.Extrinsics.load(str(FIX / "extrinsics.yml"), tf.FrameDict.load(str(FIX / "frames.yml")))


def hdr(frame="rslidar", stamp=1_000_000_000, validity="ok", reason=None, source="lidar"):
    return Header(frame_id=frame, seq=0, stamp_ns=stamp, source=source, validity=validity, reason=reason)


def pose_meta(stamp=1_000_000_000, validity="ok", reason=None):
    m = {"frame_id": "odom", "child_frame": "base_footprint", "seq": 0, "stamp_ns": stamp,
         "source": "odom", "validity": validity}
    if reason:
        m["reason"] = reason
    return m


def pose_arrow(x=1.0, y=2.0):
    return pa.array([{"position": {"x": x, "y": y, "z": 0.0},
                      "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0}}])


def seqs():
    n = iter(range(100))
    return lambda: next(n)


def pts():
    return np.array([[0, 0, 0, 7]], dtype="<f4")


def test_cloud_round_trip():
    a = cloud_to_arrow(pts())
    assert np.array_equal(cloud_from_arrow(a, 4), pts())


def test_static_transform_keeps_intensity_stamp_source(ex):
    out, h, drops = process(pts(), hdr(), extrinsics=ex, target_frame="base_footprint", take_seq=seqs())
    assert np.allclose(out, [[0.25, 0, 0.35, 7]]) and drops == {}
    assert (h.frame_id, h.stamp_ns, h.source, h.validity) == ("base_footprint", 1_000_000_000, "lidar", "ok")


def test_pose_composes_into_odom(ex):
    pose = on_pose(pose_arrow(), pose_meta(), ex.frames)
    out, h, _ = process(pts(), hdr(), extrinsics=ex, target_frame="odom", take_seq=seqs(), pose=pose)
    assert np.allclose(out[0, :3], [1.25, 2.0, 0.35]) and h.validity == "ok"


def test_no_pose_is_a_counted_drop_not_a_wrong_frame(ex):
    out, h, drops = process(pts(), hdr(), extrinsics=ex, target_frame="odom", take_seq=seqs())
    assert out is None and h is None and drops == {"no_pose": 1}


@pytest.mark.parametrize("delta_ms", [POSE_MAX_AGE_MS + 1, -(POSE_MAX_AGE_MS + 1)])
def test_stale_pose_either_direction(ex, delta_ms):
    pose = on_pose(pose_arrow(), pose_meta(stamp=1_000_000_000 + delta_ms * 1_000_000), ex.frames)
    _, h, _ = process(pts(), hdr(), extrinsics=ex, target_frame="odom", take_seq=seqs(), pose=pose)
    assert (h.validity, h.reason) == ("stale", "stale_pose")


def test_degraded_pose_passes_its_validity(ex):
    pose = on_pose(pose_arrow(), pose_meta(validity="low_confidence", reason="fit"), ex.frames)
    _, h, _ = process(pts(), hdr(), extrinsics=ex, target_frame="odom", take_seq=seqs(), pose=pose)
    assert (h.validity, h.reason) == ("low_confidence", "pose_fit")


def test_degraded_cloud_is_never_upgraded(ex):
    pose = on_pose(pose_arrow(), pose_meta(), ex.frames)
    _, h, _ = process(pts(), hdr(validity="stale", reason="old"), extrinsics=ex,
                      target_frame="odom", take_seq=seqs(), pose=pose)
    assert (h.validity, h.reason) == ("stale", "old")


def test_bad_pose_needs_child_frame(ex):
    m = pose_meta()
    del m["child_frame"]
    with pytest.raises(ValueError, match="child_frame"):
        on_pose(pose_arrow(), m, ex.frames)


def test_seq_taken_only_when_published(ex):
    take = seqs()
    process(pts(), hdr(), extrinsics=ex, target_frame="odom", take_seq=take)  # dropped
    _, h, _ = process(pts(), hdr(), extrinsics=ex, target_frame="base_link", take_seq=take)
    assert h.seq == 0


def test_header_metadata_round_trip():
    h = hdr(validity="stale", reason="x")
    assert Header.from_metadata(h.to_metadata()) == h
    with pytest.raises(ValueError, match="frame_id"):
        Header.from_metadata({k: v for k, v in h.to_metadata().items() if k != "frame_id"})
```

- [ ] **Step 2: Run to verify failure**

Run: `cd $D/nodes/frame-transform && PYTHONPATH=. $VENV/bin/python -m pytest -q`
Expected: `ModuleNotFoundError: dora_frame_transform`.

- [ ] **Step 3: Implement `core.py`**

```python
"""Change the frame a point cloud is expressed in, explicitly and checked.

`dora validate` has already confirmed that the calibration holds a route from
the input frame to TARGET_FRAME, or that a pose input is wired when the route
crosses one dynamic edge. Only x, y, z move; intensity, capture stamp and
source pass through, because the cloud still describes the same instant from
the same sensor.
"""
from dataclasses import dataclass
from typing import Callable, Dict, Optional, Tuple

import numpy as np
import pyarrow as pa

from dora import transform as tf

VALIDITY = ("ok", "missing", "stale", "unpaired", "low_confidence", "rejected")
POSE_MAX_AGE_MS = 100


@dataclass(frozen=True)
class Header:
    frame_id: str
    seq: int
    stamp_ns: int
    source: str
    validity: str = "ok"
    reason: Optional[str] = None

    def __post_init__(self):
        if not isinstance(self.frame_id, str) or not self.frame_id:
            raise ValueError(f"frame_id must be a non-empty str, got {self.frame_id!r}")
        if not isinstance(self.source, str) or not self.source:
            raise ValueError(f"source must be a non-empty str, got {self.source!r}")
        for name, value, floor in (("seq", self.seq, 0), ("stamp_ns", self.stamp_ns, 1)):
            if isinstance(value, bool) or not isinstance(value, int) or value < floor:
                raise ValueError(f"{name} must be an int >= {floor}, got {value!r}")
        if self.validity not in VALIDITY:
            raise ValueError(f"unknown validity {self.validity!r}; expected one of {VALIDITY}")
        if self.validity == "ok" and self.reason is not None:
            raise ValueError("reason must be None when validity is ok")
        if self.validity != "ok" and not self.reason:
            raise ValueError(f"validity {self.validity!r} requires a non-empty reason")

    def to_metadata(self) -> dict:
        m = {"frame_id": self.frame_id, "seq": self.seq, "stamp_ns": self.stamp_ns,
             "source": self.source, "validity": self.validity}
        if self.reason is not None:
            m["reason"] = self.reason
        return m

    @classmethod
    def from_metadata(cls, m) -> "Header":
        if not isinstance(m, dict):
            raise ValueError(f"metadata must be a mapping, got {m!r}")
        missing = [k for k in ("frame_id", "seq", "stamp_ns", "source", "validity") if k not in m]
        if missing:
            raise ValueError(f"metadata carries no contract header; missing {missing}")
        return cls(m["frame_id"], m["seq"], m["stamp_ns"], m["source"], m["validity"], m.get("reason"))


@dataclass(frozen=True)
class Pose:
    transform: "tf.Transform"
    header: Header


def cloud_from_arrow(value, item_step: int) -> np.ndarray:
    row = value[0].as_py() if isinstance(value, (pa.Array, pa.ChunkedArray)) else value
    flat = np.frombuffer(row["points"], dtype="<f4")
    if flat.size % item_step:
        raise ValueError(f"{flat.size} floats is not a whole number of {item_step}-float points")
    return flat.reshape(-1, item_step)


def cloud_to_arrow(points: np.ndarray) -> pa.Array:
    p = np.ascontiguousarray(points, dtype="<f4")
    return pa.array([{"points": p.tobytes(), "width": len(p), "height": 1}],
                    type=pa.struct([("points", pa.large_binary()), ("width", pa.uint32()), ("height", pa.uint32())]))


def on_pose(value, metadata, frames) -> Pose:
    """One pose off the wire. Raises ValueError on a bad message; the caller
    counts a `bad_pose` drop and keeps the previous pose."""
    child = (metadata or {}).get("child_frame")
    if not isinstance(child, str) or not child:
        raise ValueError("a pose message needs a 'child_frame' metadata entry naming the frame whose pose it is")
    header = Header.from_metadata(metadata)
    row = value[0].as_py()
    p, q = row["position"], row["orientation"]
    values = [p["x"], p["y"], p["z"], q["x"], q["y"], q["z"], q["w"]]  # read by name, never by position
    return Pose(tf.pose_transform(values, header.frame_id, child, frames), header)


def _pose_quality(cloud: Header, pose: Pose, max_age_ms: int) -> Tuple[str, Optional[str]]:
    if pose.header.validity != "ok":
        return pose.header.validity, f"pose_{pose.header.reason}"
    if abs(cloud.stamp_ns - pose.header.stamp_ns) > max_age_ms * 1_000_000:
        return "stale", "stale_pose"
    return "ok", None


def process(points: np.ndarray, header: Header, *, extrinsics, target_frame: str,
            take_seq: Callable[[], int], pose: Optional[Pose] = None,
            max_age_ms: int = POSE_MAX_AGE_MS) -> Tuple[Optional[np.ndarray], Optional[Header], Dict[str, int]]:
    """Transform one cloud. A cloud that cannot be placed in `target_frame` is a
    counted drop, never published under a frame it is not in. Raises
    tf.FrameError on an unknown frame (the caller counts `bad_frame`)."""
    transform, used_pose = tf.resolve(extrinsics, header.frame_id, target_frame,
                                      pose.transform if pose else None)
    if transform is None:
        return None, None, {"no_pose": 1}
    validity, reason = header.validity, header.reason
    if used_pose and validity == "ok":
        validity, reason = _pose_quality(header, pose, max_age_ms)
    out = Header(target_frame, take_seq(), header.stamp_ns, header.source, validity, reason)
    step = points.shape[1]
    moved = np.frombuffer(transform.apply_packed(np.ascontiguousarray(points, dtype="<f4").tobytes(), step),
                          dtype="<f4").reshape(-1, step)
    return moved, out, {}
```

The source is unchanged and the stamp is the cloud's own (the pose is not a data parent), matching `REF` `frame_transform_op.py`, where `derive([header], …)` has the cloud as its only parent.

- [ ] **Step 4: Implement `main.py`, `__init__.py`, packaging and manifest**

`__init__.py`: empty.

`main.py`:

```python
"""The dora node loop. Configuration is read and checked before the first message."""
import json
import os
import time
from collections import Counter

import pyarrow as pa
from dora import Node
from dora import transform as tf

from dora_frame_transform.core import Header, cloud_from_arrow, cloud_to_arrow, on_pose, process

ITEM_STEP = {"xyz": 3, "xyzi": 4}


def config():
    frames = tf.FrameDict.load(os.environ["DORA_FRAMES"])
    extrinsics = tf.Extrinsics.load(os.environ["DORA_EXTRINSICS"], frames)
    target = os.environ["TARGET_FRAME"]
    if frames.kind(target) == "none":
        raise SystemExit("TARGET_FRAME is 'none', which has no spatial meaning")
    fields = os.environ.get("POINT_FIELDS", "xyzi")
    if fields not in ITEM_STEP:
        raise SystemExit(f"POINT_FIELDS must be one of {sorted(ITEM_STEP)}, got {fields!r}")
    return extrinsics, target, ITEM_STEP[fields], int(os.environ.get("DIAG_EVERY", "10"))


def main():
    extrinsics, target, step, diag_every = config()
    node = Node()
    pose, seq, n_in = None, 0, 0
    drops, logged = Counter(), False

    def take():
        nonlocal seq
        seq += 1
        return seq - 1

    for event in node:
        if event["type"] != "INPUT":
            continue
        if event["id"] == "pose":
            try:
                pose = on_pose(event["value"], event["metadata"], extrinsics.frames)
            except ValueError:
                drops["bad_pose"] += 1
            continue
        if event["id"] != "cloud":
            continue
        n_in += 1
        started = time.perf_counter_ns()
        try:
            header = Header.from_metadata(event["metadata"])
            moved, out, d = process(cloud_from_arrow(event["value"], step), header,
                                    extrinsics=extrinsics, target_frame=target, take_seq=take, pose=pose)
        except ValueError as error:  # tf.FrameError is a ValueError
            moved, out, d = None, None, {"bad_frame": 1}
            if not logged:
                node.log("info", f"dropping clouds as bad_frame: {error}")
                logged = True
        drops.update(d)
        if moved is not None:
            node.send_output("cloud", cloud_to_arrow(moved), out.to_metadata())
        if n_in % diag_every == 0:
            blob = json.dumps({"in": n_in, "out": seq, "drops": dict(drops),
                               "proc_ns": time.perf_counter_ns() - started}).encode()
            node.send_output("diag", pa.array(list(blob), type=pa.uint8()), {"frame_id": "none"})


if __name__ == "__main__":
    main()
```

If `node.log` is not the Python API's logging method, use whichever method `apis/python/node/src/lib.rs` exposes for logging (look for `fn log`).

`pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "dora-frame-transform"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = ["numpy", "pyarrow"]

[project.scripts]
dora-frame-transform = "dora_frame_transform.main:main"

[tool.setuptools.packages.find]
include = ["dora_frame_transform*"]
```

`dora-node.yml` (follow the field layout of `~/Public/github_dora/dora-hub/node-hub/dora-yolo/dora-node.yml`):

```yaml
apiVersion: 1
name: dora-frame-transform
namespace: dora-rs
description: Transform a point cloud into a target frame, statically or composed with a pose.
categories: [transform]
keywords: [frames, tf, point-cloud]
runtime: python
entrypoint: dora-frame-transform
build: pip install .
dora: ">=1.1.0"
inputs:
  cloud:
    required: true
    type: std/media/v1/PointCloud
    description: Points in any frame named by frame_id.
  pose:
    required: false
    type: std/math/v1/Pose
    description: The pose for the one dynamic edge on the route (child_frame in metadata).
outputs:
  cloud:
    type: std/media/v1/PointCloud
    description: Points in TARGET_FRAME; unplaceable clouds are counted drops, never mislabelled.
  diag:
    description: JSON counts (in, out, drops by reason, proc_ns) as UInt8.
env:
  TARGET_FRAME: {description: Frame to transform into.}
  DORA_FRAMES: {description: Frame dictionary path.}
  DORA_EXTRINSICS: {description: Robot calibration path; must equal the dataflow's frames.extrinsics.}
  POINT_FIELDS: {default: xyzi, description: "xyz or xyzi"}
  DIAG_EVERY: {default: "10", description: Clouds between diag messages.}
```

Validate it with `$D/target/release/dora validate --node-manifest nodes/frame-transform/dora-node.yml`. If the manifest schema rejects a key, such as `type` under a port, use the key the schema error names and record it under `## Friction`.

- [ ] **Step 5: Install and run the tests**

```bash
cd $D/nodes/frame-transform && $VENV/bin/python -m pip install -e . -q
PYTHONPATH= $VENV/bin/python -m pytest tests -q
$D/target/release/dora validate --node-manifest dora-node.yml
```

Expected: 11 passed (one test is parametrized twice); `Node manifest OK.`

- [ ] **Step 6: Commit**

```bash
cd $D && git add nodes/frame-transform
git commit -m "feat(nodes): frame-transform node on dora.transform

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 11: DORA_NAV sim — headers and typed outputs

**Files:**
- Create: `N/modules/simulation/mujoco_mickrobot/src/mujoco_mickrobot/contract.py`
- Modify: `.../dora_adapter.py` (headers on `send`; new `send_array`), `.../runtime.py` (pass `output_id`-specific header), `.../main.py` (bindings for `cloud`, `odom_pose`)
- Modify: `N/modules/simulation/mujoco_mickrobot/pyproject.toml` (relax `dora-rs>=0.3,<1` to `dora-rs>=0.3`)
- Create: `.../tests/test_contract.py`, `.../dora-node.yml`

- [ ] **Step 1: Write the failing tests** (`tests/test_contract.py`)

```python
import numpy as np
import pyarrow as pa
import pytest

from mujoco_mickrobot.contract import (
    FRAME_NAMES, HeaderSource, cloud_array, pose_array, stamp_ns,
)


def test_stamp_is_exact_and_positive():
    assert stamp_ns(0.0) == 1
    assert stamp_ns(0.1) == 100_000_000
    assert stamp_ns(1e-9) == 1
    # 123.456 is 123.45600000000000306... as a double; exact arithmetic, not float scaling
    assert stamp_ns(123.456) == 123_456_000_000


def test_sim_frames_map_to_dictionary_names():
    assert FRAME_NAMES["lidar_link"] == "rslidar"
    assert FRAME_NAMES["camera_link"] == "camera_front"
    assert FRAME_NAMES["imu_link"] == "imu_link"


def test_header_source_counts_per_output_and_maps_frames():
    h = HeaderSource(source="mujoco_mickrobot")
    a = h.header("cloud", "lidar_link", 0.1)
    b = h.header("cloud", "lidar_link", 0.2)
    c = h.header("imu", "imu_link", 0.2)
    assert (a["frame_id"], a["seq"], b["seq"], c["seq"]) == ("rslidar", 0, 1, 0)
    assert a["validity"] == "ok" and "reason" not in a and a["source"] == "mujoco_mickrobot"


def test_unknown_sim_frame_is_refused():
    with pytest.raises(KeyError):
        HeaderSource(source="s").header("x", "somewhere", 0.1)


def test_strip_switch_removes_frame_id_only_on_cloud():
    h = HeaderSource(source="s", strip_frame_on=("cloud",))
    assert "frame_id" not in h.header("cloud", "lidar_link", 0.1)
    assert "frame_id" in h.header("imu", "imu_link", 0.1)


def test_cloud_array_layout():
    pts = np.array([[1, 2, 3, 4]], dtype=np.float32)
    a = cloud_array(pts)
    row = a[0].as_py()
    assert row["width"] == 1 and row["height"] == 1
    assert np.array_equal(np.frombuffer(row["points"], dtype="<f4"), [1, 2, 3, 4])


def test_pose_array_reads_xyzw():
    a = pose_array((1.0, 2.0, 0.0), (0.0, 0.0, 0.0, 1.0))
    assert a[0].as_py()["orientation"] == {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0}
```

- [ ] **Step 2: Run to verify failure**

Run: `cd $N/modules/simulation/mujoco_mickrobot && $VENV/bin/python -m pip install -e . -q && PYTHONPATH= $VENV/bin/python -m pytest tests/test_contract.py -q`
Expected: `ModuleNotFoundError: mujoco_mickrobot.contract`.

- [ ] **Step 3: Implement `contract.py`**

```python
"""Contract headers and typed payloads for the simulator's outputs.

The sim names frames as its MuJoCo model does; the frame dictionary rejects
some of those upstream names, so they are mapped here, once, explicitly.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction

import numpy as np
import pyarrow as pa

# sim model name -> frame dictionary name
FRAME_NAMES = {
    "lidar_link": "rslidar",
    "camera_link": "camera_front",
    "imu_link": "imu_link",
    "odom": "odom",
    "base_footprint": "base_footprint",
    "map": "map",
}

POINTCLOUD_TYPE = pa.struct([("points", pa.large_binary()), ("width", pa.uint32()), ("height", pa.uint32())])
_VEC3 = pa.struct([("x", pa.float64()), ("y", pa.float64()), ("z", pa.float64())])
_QUAT = pa.struct([("x", pa.float64()), ("y", pa.float64()), ("z", pa.float64()), ("w", pa.float64())])
POSE_TYPE = pa.struct([("position", _VEC3), ("orientation", _QUAT)])


def stamp_ns(seconds: float) -> int:
    """Exact nanoseconds from sim seconds (round half to even); never below 1."""
    return max(1, int(round(Fraction(seconds) * 1_000_000_000)))


@dataclass
class HeaderSource:
    source: str
    strip_frame_on: tuple[str, ...] = ()
    _seq: dict[str, int] = field(default_factory=dict)

    def header(self, output_id: str, sim_frame: str, timestamp_s: float, **extra) -> dict:
        frame = FRAME_NAMES[sim_frame]
        seq = self._seq.get(output_id, 0)
        self._seq[output_id] = seq + 1
        meta = {"frame_id": frame, "seq": seq, "stamp_ns": stamp_ns(timestamp_s),
                "source": self.source, "validity": "ok", **extra}
        if output_id in self.strip_frame_on:
            del meta["frame_id"]
        return meta


def cloud_array(points_xyzi) -> pa.Array:
    p = np.ascontiguousarray(points_xyzi, dtype="<f4")
    return pa.array([{"points": p.tobytes(), "width": len(p), "height": 1}], type=POINTCLOUD_TYPE)


def pose_array(position, orientation_xyzw) -> pa.Array:
    x, y, z, w = (float(c) for c in orientation_xyzw)
    px, py, pz = (float(c) for c in position)
    return pa.array([{"position": {"x": px, "y": py, "z": pz},
                      "orientation": {"x": x, "y": y, "z": z, "w": w}}], type=POSE_TYPE)
```

- [ ] **Step 4: Wire the outputs**

`dora_adapter.py`: change `send` to take a metadata dict and add `send_array`:

```python
    def send(self, output_id: str, payload: bytes, metadata: dict) -> None:
        values = pa.array(np.frombuffer(payload, dtype=np.uint8), type=pa.uint8())
        self._node.send_output(output_id, values, metadata)

    def send_array(self, output_id: str, array: pa.Array, metadata: dict) -> None:
        self._node.send_output(output_id, array, metadata)
```

`runtime.py`: extend `SensorBinding` with two fields that have defaults, so existing constructions keep working:

```python
    frame: str = "base_footprint"           # sim frame name, mapped by contract.FRAME_NAMES
    typed: bool = False                     # sample_and_encode returns (pa.Array, extra_meta) instead of bytes
```

Give `SimulationRuntime.__init__` a `headers: HeaderSource` keyword argument (default `HeaderSource(source="mujoco_mickrobot")`). In `_publish_due`, replace the send call:

```python
                result = binding.sample_and_encode(snapshot, timestamp_s)
                try:
                    if binding.typed:
                        array, extra = result
                        self.adapter.send_array(binding.output_id, array,
                                                self.headers.header(binding.output_id, binding.frame, timestamp_s, **extra))
                    else:
                        self.adapter.send(binding.output_id, result,
                                          self.headers.header(binding.output_id, binding.frame, timestamp_s,
                                                              timestamp=float(timestamp_s)))
```

The existing `timestamp` metadata key is kept as an extra, so the existing consumers are unaffected. Update `AdapterProtocol` in `runtime.py` to the new `send` signature and add `send_array`.

`main.py` `_bindings`: give the existing bindings `frame=config.lidar.frame_id` (pointcloud), `config.camera.frame_id` (image), `config.imu.frame_id` (imu), and `"odom"` (Odometry). `gnss` uses `"map"`. Then add:

```python
    if config.lidar.enabled:
        result.append(SensorBinding(
            "cloud", config.lidar.rate_hz,
            lambda snapshot, timestamp: (cloud_array(lidar.sample(simulator, timestamp)), {}),
            True, frame=config.lidar.frame_id, typed=True))
    if config.odometry.enabled:
        def odom_pose(snapshot, timestamp):
            sample = odometry.sample(snapshot, timestamp)
            return (pose_array(sample.position_m, sample.orientation_xyzw),
                    {"child_frame": FRAME_NAMES[sample.child_frame_id]})
        result.append(SensorBinding("odom_pose", config.odometry.rate_hz, odom_pose, False,
                                    frame="odom", typed=True))
```

Note that `cloud` samples the lidar a second time per period. That is acceptable for the experiment; record it under `## Friction` (a real change would publish one sample on both outputs). In `main()`, build `HeaderSource(source=node_id, strip_frame_on=("cloud",) if os.environ.get("SIM_STRIP_CLOUD_FRAME") == "1" else ())`, using the node id from `DORA_NODE_ID` or `"mujoco_mickrobot"`, and pass it to `SimulationRuntime`. Add imports for `cloud_array`, `pose_array`, `FRAME_NAMES`, `HeaderSource` and `os`.

- [ ] **Step 5: Manifest** (`modules/simulation/mujoco_mickrobot/dora-node.yml`)

```yaml
apiVersion: 1
name: mujoco-mickrobot
namespace: dora-rs
description: MuJoCo simulation of the MickRobot mobile base with lidar, camera, IMU, odometry and GNSS.
categories: [simulation]
keywords: [mujoco, sim, lidar]
runtime: python
entrypoint: scripts/run_mujoco_node.py
build: pip install -e .
dora: ">=1.1.0"
inputs:
  cmd_vel: {required: true, description: JSON velocity command.}
outputs:
  pointcloud: {description: "Legacy packed XYZI with a timestamp header, frame rslidar."}
  image: {description: "Legacy RGB image, frame camera_front."}
  imu: {description: "Legacy JSON IMU, frame imu_link."}
  Odometry: {description: "Legacy JSON odometry, frame odom."}
  gnss: {description: "Legacy JSON GNSS, frame map."}
  cloud: {type: "std/media/v1/PointCloud[fields=xyzi]", description: "Lidar points in rslidar."}
  odom_pose: {type: std/math/v1/Pose, description: "base_footprint in odom; child_frame in metadata."}
```

- [ ] **Step 6: Run the sim's tests**

```bash
cd $N/modules/simulation/mujoco_mickrobot && PYTHONPATH= $VENV/bin/python -m pytest tests -q
$D/target/release/dora validate --node-manifest dora-node.yml
```

Expected: the 7 new tests pass, plus any existing tests (the folder currently has only fixtures). `Node manifest OK.`

- [ ] **Step 7: Commit**

```bash
cd $N && git add modules/simulation/mujoco_mickrobot
git commit -m "feat(sim): contract headers on every output; typed cloud and odom_pose

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 12: Robot description, dataflows, checker, validate script

**Files:**
- Create: `N/robots/mickrobot-sim/frames.yml` (copy of `REF/specs/operators/frames.yaml`)
- Create: `N/robots/mickrobot-sim/extrinsics.yml` (copy of `REF/robots/simulated-mobile-robot/extrinsics.yaml`, with `robot: mickrobot-sim`)
- Create: `N/examples/contract-core/good.yml`, `bad-frame-mismatch.yml`, `bad-unknown-frame.yml`, `bad-missing-calibration.yml`, `bad-two-dynamic-edges.yml`, `checker.py`, `run_validate.sh`
- Create: `N/robots/mickrobot-sim/extrinsics-no-base.yml` (without the `base_footprint -> base_link` entry)

- [ ] **Step 1: Robot description**

```bash
mkdir -p $N/robots/mickrobot-sim
cp $REF/specs/operators/frames.yaml $N/robots/mickrobot-sim/frames.yml
sed 's/^robot: simulated-mobile-robot/robot: mickrobot-sim/' $REF/robots/simulated-mobile-robot/extrinsics.yaml > $N/robots/mickrobot-sim/extrinsics.yml
$VENV/bin/python - <<'EOF'
import re, pathlib
p = pathlib.Path("/home/demo/Public/github_dimos/DORA_NAV/robots/mickrobot-sim")
text = (p / "extrinsics.yml").read_text()
cut = re.sub(r"  - parent: base_footprint\n    child: base_link\n(    .*\n){2}", "", text)
assert cut != text
(p / "extrinsics-no-base.yml").write_text(cut)
EOF
```

- [ ] **Step 2: `good.yml`**

```yaml
frames:
  dictionary: ../../robots/mickrobot-sim/frames.yml
  extrinsics: ../../robots/mickrobot-sim/extrinsics.yml
nodes:
  - id: driver
    path: ../../modules/simulation/mujoco_mickrobot/tests/fixtures/cmd_vel_sender.py
    inputs:
      tick: dora/timer/millis/100
      Odometry: sim/Odometry
      imu: sim/imu
    outputs: [cmd_vel]

  - id: sim
    path: ../../modules/simulation/mujoco_mickrobot/scripts/run_mujoco_node.py
    inputs:
      cmd_vel: driver/cmd_vel
    outputs: [pointcloud, image, imu, Odometry, gnss, cloud, odom_pose]
    output_types:
      cloud: std/media/v1/PointCloud
      odom_pose: std/math/v1/Pose
    output_frames:
      cloud: rslidar
      odom_pose: odom
    env:
      MUJOCO_HEADLESS: "1"
      MUJOCO_GL: egl

  - id: ft
    path: dora-frame-transform
    inputs:
      cloud: sim/cloud
      pose: sim/odom_pose
    input_types:
      cloud: std/media/v1/PointCloud
      pose: std/math/v1/Pose
    input_frames:
      cloud: any
    outputs: [cloud, diag]
    output_types:
      cloud: std/media/v1/PointCloud
    output_frames:
      cloud: env:TARGET_FRAME
      diag: none
    env:
      TARGET_FRAME: odom
      POINT_FIELDS: xyzi
      DORA_FRAMES: ../../robots/mickrobot-sim/frames.yml
      DORA_EXTRINSICS: ../../robots/mickrobot-sim/extrinsics.yml

  - id: checker
    path: checker.py
    inputs:
      cloud: ft/cloud
      diag: ft/diag
      raw: sim/cloud
    input_frames:
      cloud: odom
    env:
      RUN_SECONDS: "60"
      EXPECT: transformed
      RECORD: records/contract-core.json
```

A node's `env` paths are relative to the node's working directory, which dora sets to the dataflow directory. If a node sees otherwise at run time, make the paths absolute in the run script (Task 13) and record it under `## Friction`.

- [ ] **Step 3: The four bad dataflows**

Each starts as a copy of `good.yml` with exactly one change:

| File | Change |
|---|---|
| `bad-frame-mismatch.yml` | checker `input_frames: {cloud: base_link}` |
| `bad-unknown-frame.yml` | sim `output_frames: {cloud: lidar_link, odom_pose: odom}` |
| `bad-missing-calibration.yml` | `frames.extrinsics` and ft `DORA_EXTRINSICS` both point to `../../robots/mickrobot-sim/extrinsics-no-base.yml` |
| `bad-two-dynamic-edges.yml` | ft `TARGET_FRAME: map` |

- [ ] **Step 4: `run_validate.sh`**

```bash
#!/usr/bin/env bash
# Accept good.yml; refuse each bad-*.yml with its reason.
set -uo pipefail
here=$(cd "$(dirname "$0")" && pwd)
dora=${DORA:-/home/demo/Public/github_dimos/dora/target/release/dora}
fail=0
expect() { # file, expected-exit (0|1), grep pattern
  out=$("$dora" validate "$here/$1" 2>&1); code=$?
  if [[ $2 == 0 && $code != 0 ]] || [[ $2 == 1 && $code == 0 ]] || ! grep -q -- "$3" <<<"$out"; then
    echo "FAIL $1 (exit $code)"; echo "$out" | sed 's/^/    /'; fail=1
  else echo "ok   $1"; fi
}
expect good.yml 0 "Frames OK."
expect bad-frame-mismatch.yml 1 "requires frame 'base_link'"
expect bad-unknown-frame.yml 1 "use 'rslidar'"
expect bad-missing-calibration.yml 1 "never assumed to be identity"
expect bad-two-dynamic-edges.yml 1 "crosses 2 dynamic edges"
exit $fail
```

- [ ] **Step 5: `checker.py`**

```python
"""Run-time assertions for the contract-core chain; writes a JSON record.

EXPECT=transformed: every cloud is in odom with increasing seq and validity ok
once a pose has arrived, and ground points sit at z = 0 +/- 0.03 m.
EXPECT=dropped: no cloud arrives; diag counts one bad_frame per input cloud.
"""
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np
from dora import Node

RUN_S = float(os.environ.get("RUN_SECONDS", "60"))
EXPECT = os.environ["EXPECT"]
RECORD = Path(os.environ["RECORD"])
GROUND_TOL_M = 0.03


def points(value):
    return np.frombuffer(value[0].as_py()["points"], dtype="<f4").reshape(-1, 4)


def main():
    start = time.monotonic()
    seqs, validity, ground_err, raw_in, last_diag = [], Counter(), [], 0, {}
    problems = []
    for event in Node():
        if event["type"] != "INPUT":
            continue
        if event["id"] == "raw":
            raw_in += 1
        elif event["id"] == "diag":
            last_diag = json.loads(bytes(event["value"].to_numpy()).decode())
        elif event["id"] == "cloud":
            m = event["metadata"]
            if m.get("frame_id") != "odom":
                problems.append(f"cloud frame {m.get('frame_id')!r}")
            seqs.append(m["seq"])
            validity[m["validity"]] += 1
            p = points(event["value"])
            low = p[p[:, 2] <= np.quantile(p[:, 2], 0.10)]
            ground_err.append(float(np.median(np.abs(low[:, 2]))))
        if time.monotonic() - start >= RUN_S:
            break

    if EXPECT == "transformed":
        if not seqs:
            problems.append("no transformed clouds")
        if any(b <= a for a, b in zip(seqs, seqs[1:])):
            problems.append("seq not strictly increasing")
        if seqs and max(ground_err) > GROUND_TOL_M:
            problems.append(f"ground error {max(ground_err):.3f} m > {GROUND_TOL_M}")
        if set(validity) - {"ok", "stale"}:
            problems.append(f"unexpected validity {dict(validity)}")
        if validity.get("stale", 0) > 2:  # only before the first pose settles
            problems.append(f"{validity['stale']} stale clouds")
    elif EXPECT == "dropped":
        if seqs:
            problems.append(f"{len(seqs)} clouds published despite stripped frame_id")
        bad = last_diag.get("drops", {}).get("bad_frame", 0)
        if bad < last_diag.get("in", 1) or last_diag.get("in", 0) == 0:
            problems.append(f"diag {last_diag} does not count every input as bad_frame")

    record = {"expect": EXPECT, "run_s": RUN_S, "raw_in": raw_in, "published": len(seqs),
              "validity": dict(validity), "ground_err_m": {
                  "max": max(ground_err, default=None),
                  "median": float(np.median(ground_err)) if ground_err else None},
              "last_diag": last_diag, "problems": problems}
    RECORD.parent.mkdir(parents=True, exist_ok=True)
    RECORD.write_text(json.dumps(record, indent=2) + "\n")
    print("CHECKER_OK" if not problems else f"CHECKER_FAIL {problems}")
    sys.exit(0 if not problems else 1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Run the validate script**

```bash
cd $N/examples/contract-core && chmod +x run_validate.sh && ./run_validate.sh
```

Expected: five `ok` lines, exit 0.

- [ ] **Step 7: Commit**

```bash
cd $N && git add robots examples/contract-core
git commit -m "feat(examples): contract-core dataflows, checker and validate script

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 13: Live runs on an isolated coordinator

**Files:**
- Create: `N/examples/contract-core/run_live.sh`
- Create (by the run): `N/examples/contract-core/records/contract-core.json`, `records/contract-core-stripped.json`, `records/c-header.log`

- [ ] **Step 1: `run_live.sh`**

```bash
#!/usr/bin/env bash
# Runs on its own coordinator; never touches the default-port one.
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
export DORA=/home/demo/Public/github_dimos/dora/target/release/dora
export DORA_COORDINATOR_PORT=6113
export DORA_COORDINATOR_ADDR=127.0.0.1
export DORA_DAEMON_PORT=6114
export PATH=/home/demo/Public/github_dimos/.venv-exp/bin:$PATH
export PYTHONPATH=
cleanup() { "$DORA" destroy --coordinator-port 6113 >/dev/null 2>&1 || true; }
trap cleanup EXIT
"$DORA" up
cd "$here"
"$DORA" run good.yml --name contract-core-good
cp records/contract-core.json records/contract-core.json.bak
sed -e 's/EXPECT: transformed/EXPECT: dropped/' \
    -e 's#RECORD: records/contract-core.json#RECORD: records/contract-core-stripped.json#' \
    -e 's/MUJOCO_GL: egl/MUJOCO_GL: egl\n      SIM_STRIP_CLOUD_FRAME: "1"/' \
    -e 's/RUN_SECONDS: "60"/RUN_SECONDS: "20"/' good.yml > /tmp/contract-core-stripped.yml
cp /tmp/contract-core-stripped.yml "$here/.stripped.yml"
"$DORA" run .stripped.yml --name contract-core-stripped
mv records/contract-core.json.bak records/contract-core.json
rm -f .stripped.yml
(cd /home/demo/Public/github_dimos/dora/examples/c-header && "$DORA" run dataflow.yml --name c-header) | tee "$here/records/c-header.log"
grep -q C_HEADER_OK "$here/records/c-header.log"
```

Before the first run, check how `dora up`, `dora run` and `dora destroy` take the coordinator port and daemon port in this dora version: `$DORA up --help`, `$DORA run --help`, `$DORA destroy --help`. Adjust the flags so that **every** command targets 6113 and the daemon listens on a non-default port. If `dora run` starts its own coordinator and daemon instead of using `dora up`, drop `dora up` and `destroy`, and confirm with `ss -ltnp | grep -E '6013|6113'` during a run that nothing new binds 6013. Record what was needed under `## Friction`.

- [ ] **Step 2: Confirm the shared coordinator is untouched, then run**

```bash
ss -ltnp | grep 6013 | tee /tmp/claude-6013-before.txt
cd $N/examples/contract-core && chmod +x run_live.sh && ./run_live.sh
ss -ltnp | grep 6013 | diff /tmp/claude-6013-before.txt - && echo "6013 unchanged"
```

Expected:
- the checker prints `CHECKER_OK` in both runs;
- `C_HEADER_OK` appears;
- `6013 unchanged`;
- `records/contract-core.json` shows `published` > 500, `ground_err_m.max` ≤ 0.03 and `problems: []`;
- `records/contract-core-stripped.json` shows `published: 0` and `bad_frame` equal to `in`.

If the ground error exceeds 0.03 m, first check that the sim's `base_footprint` sits on the ground plane (see `mickrobot.xml:29`, `base_link` at z = 0.1). Report the measured offset; do not widen the tolerance silently.

- [ ] **Step 3: Commit the records**

```bash
cd $N && git add examples/contract-core/run_live.sh examples/contract-core/records
git commit -m "test(examples): live contract-core runs on an isolated coordinator

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 14: Mutation sweep

**Files:**
- Create: `D/tools/contract-mutation-sweep.py`

Ten mutations, one per load-bearing promise from the reference list. Each anchor must occur exactly once in its file.

| # (ref) | Promise broken | File | Anchor → replacement |
|---|---|---|---|
| 3 | output publishes its input's frame | `nodes/frame-transform/dora_frame_transform/core.py` | `    out = Header(target_frame,` → `    out = Header(header.frame_id,` |
| 4 | upgrade granted but not counted | `libraries/message/src/header.rs` | `        (up.count)(up.reason);` → `        let _ = up;` |
| 7 | degraded validity laundered to ok | `nodes/frame-transform/dora_frame_transform/core.py` | `    validity, reason = header.validity, header.reason` → `    validity, reason = "ok", None` |
| 10 | missing extrinsic treated as identity | `libraries/transform/src/extrinsics.rs` | `                Some(edge) => out.push(edge.clone()),\n                None => return Err(` → `                Some(edge) => out.push(edge.clone()),\n                None if true => continue,\n                None => return Err(` |
| 11 | transforms compose when frames do not meet | `libraries/transform/src/rigid.rs` | `        if self.dst != other.src {` → `        if false && self.dst != other.src {` |
| 12 | quaternion read w, x, y, z | `libraries/transform/src/rigid.rs` | `    let [x, y, z, w] = q;` → `    let [w, x, y, z] = q;` |
| 13 | calibration may carry a dynamic edge | `libraries/transform/src/extrinsics.rs` | `            if frame.kind != Kind::Mounted {` → `            if frame.kind != Kind::Mounted && frame.kind != Kind::Dynamic {` |
| 14 | cloud with stale pose forwarded ok | `nodes/frame-transform/dora_frame_transform/core.py` | `        return "stale", "stale_pose"` → `        return "ok", None` |
| 15 | validator skips the route check | `libraries/core/src/descriptor/frames_check.rs` | `            match ex.route(src, dst) {` → `            match Ok::<(), FrameError>(()) {` |
| 16 | launch calibration differs from checked | `libraries/core/src/descriptor/frames_check.rs` | `                if launched != checked {` → `                if false && launched != checked {` |

- [ ] **Step 1: Write the script**

```python
#!/usr/bin/env python3
"""Apply one mutation at a time, run the suites, restore, report.

A mutation no test notices is a hole in the suite. Nothing else may run tests
in this copy while this runs. Exit status is non-zero if any mutation survives.
"""
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
VENV_PY = "/home/demo/Public/github_dimos/.venv-exp/bin/python"
FT = "nodes/frame-transform/dora_frame_transform/core.py"

MUTATIONS = [
    ("3. output publishes its input's frame", FT,
     "    out = Header(target_frame,", "    out = Header(header.frame_id,"),
    ("4. an upgrade is granted but never counted", "libraries/message/src/header.rs",
     "        (up.count)(up.reason);", "        let _ = up;"),
    ("7. a degraded validity is laundered into ok", FT,
     "    validity, reason = header.validity, header.reason", '    validity, reason = "ok", None'),
    ("10. a missing extrinsic is quietly treated as identity", "libraries/transform/src/extrinsics.rs",
     "                Some(edge) => out.push(edge.clone()),\n                None => return Err(",
     "                Some(edge) => out.push(edge.clone()),\n                None if true => continue,\n                None => return Err("),
    ("11. transforms compose even when their frames do not meet", "libraries/transform/src/rigid.rs",
     "        if self.dst != other.src {", "        if false && self.dst != other.src {"),
    ("12. rotation_xyzw is read as w, x, y, z", "libraries/transform/src/rigid.rs",
     "    let [x, y, z, w] = q;", "    let [w, x, y, z] = q;"),
    ("13. a calibration file may carry a dynamic edge", "libraries/transform/src/extrinsics.rs",
     "            if frame.kind != Kind::Mounted {", "            if frame.kind != Kind::Mounted && frame.kind != Kind::Dynamic {"),
    ("14. a cloud composed with a stale pose is forwarded as ok", FT,
     '        return "stale", "stale_pose"', "        return \"ok\", None"),
    ("15. the validator skips the transform check", "libraries/core/src/descriptor/frames_check.rs",
     "            match ex.route(src, dst) {", "            match Ok::<(), FrameError>(()) {"),
    ("16. a node may launch with a different calibration than was checked", "libraries/core/src/descriptor/frames_check.rs",
     "                if launched != checked {", "                if false && launched != checked {"),
]

SUITES = [
    ["cargo", "test", "-q", "-p", "dora-message", "header::"],
    ["cargo", "test", "-q", "-p", "dora-transform"],
    ["cargo", "test", "-q", "-p", "dora-core", "--test", "frames_check"],
    ["bash", "-c", f"cd apis/python/node && VIRTUAL_ENV=/home/demo/Public/github_dimos/.venv-exp "
                   f"/home/demo/Public/github_dimos/.venv-exp/bin/maturin develop -q --release && "
                   f"PYTHONPATH= {VENV_PY} -m pytest -q -p no:cacheprovider tests/test_transform.py"],
    ["bash", "-c", f"cd nodes/frame-transform && PYTHONPATH= {VENV_PY} -B -m pytest -q -p no:cacheprovider tests"],
]


def caught() -> bool:
    for cmd in SUITES:
        if subprocess.run(cmd, cwd=ROOT, capture_output=True).returncode != 0:
            return True
    return False


def main() -> int:
    survivors = []
    for label, rel, anchor, replacement in MUTATIONS:
        path = ROOT / rel
        original = path.read_text()
        if original.count(anchor) != 1:
            print(f"ANCHOR {label}: found {original.count(anchor)} times in {rel}")
            return 2
        path.write_text(original.replace(anchor, replacement))
        try:
            ok = caught()
        finally:
            path.write_text(original)
        print(f"{'caught  ' if ok else 'SURVIVED'} {label}")
        if not ok:
            survivors.append(label)
    # rebuild the unmutated binding so the venv is left clean
    subprocess.run(SUITES[3], cwd=ROOT, capture_output=True)
    print(f"{len(survivors)}/{len(MUTATIONS)} survive")
    return 1 if survivors else 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run it**

Run: `cd $D && $VENV/bin/python tools/contract-mutation-sweep.py`
Expected: ten `caught` lines, `0/10 survive`. A survivor means a missing test. Write the test that would catch it (in the suite of the mutated file), run the sweep again, and record the added test in the mapping.

- [ ] **Step 3: Commit**

```bash
cd $D && git add tools/contract-mutation-sweep.py
git commit -m "test(contract-core): mutation sweep over header, transform, validator and node

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 15: Test mapping, regression runs and feasibility report

**Files:**
- Create: `D/tools/check-test-mapping.py`, `D/docs/contract-core/test-mapping.md`
- Modify: `D/docs/contract-core/feasibility.md`

- [ ] **Step 1: The mapping checker**

```python
#!/usr/bin/env python3
"""Every reference test in the slice's files must appear in test-mapping.md,
mapped to a new test or marked n/a with a reason."""
import pathlib
import re
import subprocess
import sys

REF = pathlib.Path("/home/demo/Public/github_dimos/open-robot-stack-operator-contract")
FILES = [
    "packages/open-robot-operator/tests/test_envelope.py",
    "packages/open-robot-operator/tests/test_derive.py",
    "packages/open-robot-operator/tests/test_frames.py",
    "packages/open-robot-operator/tests/test_transform.py",
    "packages/open-robot-operator/tests/test_resolve.py",
    "packages/open-robot-operator/tests/test_validate.py",
    "packages/open-robot-operator/tests/test_wire.py",
    "capabilities/perception/tests/test_frame_transform.py",
]
MAPPING = pathlib.Path(__file__).resolve().parents[1] / "docs/contract-core/test-mapping.md"


def reference_tests():
    out = subprocess.run(
        ["/home/demo/Public/github_dimos/.venv-exp/bin/python", "-m", "pytest", "--collect-only", "-q", *FILES],
        cwd=REF, capture_output=True, text=True, env={"PYTHONPATH": "packages/open-robot-operator:capabilities/perception:capabilities/data-processing", "PATH": "/usr/bin:/bin"})
    return sorted({line.split("[")[0] for line in out.stdout.splitlines() if "::" in line})


def main():
    text = MAPPING.read_text()
    rows = {}
    for line in text.splitlines():
        m = re.match(r"\|\s*`([^`]+)`\s*\|\s*(.+?)\s*\|", line)
        if m:
            rows[m.group(1)] = m.group(2)
    missing = [t for t in reference_tests() if t not in rows]
    empty = [t for t, v in rows.items() if not v or v in ("-", "TBD")]
    for t in missing:
        print(f"UNMAPPED {t}")
    for t in empty:
        print(f"EMPTY    {t}")
    print(f"{len(rows)} mapped, {len(missing)} unmapped, {len(empty)} empty")
    return 1 if missing or empty else 0


if __name__ == "__main__":
    sys.exit(main())
```

If collection fails because `REF`'s tests need packages the experiment venv lacks, install `REF`'s packages into the venv in editable mode (`pip install -e $REF/packages/open-robot-operator[transform]` and the perception and data-processing packs). Note that in `feasibility.md`.

- [ ] **Step 2: Write `test-mapping.md`**

Header and format:

```markdown
# Reference test mapping

Each reference test from the operator-contract worktree, mapped to the test that
now carries its promise, or marked n/a with the reason.

| Reference test | New test or n/a (reason) |
|---|---|
| `packages/open-robot-operator/tests/test_frames.py::test_rejected_name_is_refused` | `libraries/transform/tests/frames_extrinsics.rs::rejected_name_says_what_to_use` |
| `packages/open-robot-operator/tests/test_envelope.py::test_schema_caret_refused` | n/a: run-time messages carry no schema key; dora type URNs on ports replace it |
```

Fill one row per collected test. Generate the left column with the collect command from the script, and fill the right column by reading each test. Out-of-slice reasons are: "n/a: schema versions are dora type URNs", "n/a: dora built-in sources are checked by dora's own wiring check", and "n/a: later slice (data processing)". Add the seven out-of-slice mutations (1, 2, 5a, 5b, 6, 8, 9) at the end, under a heading `## Mutations not in this slice`, with the same reasons.

Run: `cd $D && $VENV/bin/python tools/check-test-mapping.py`
Expected: `N mapped, 0 unmapped, 0 empty`, exit 0.

- [ ] **Step 3: Full regression runs**

```bash
cd $D && cargo test -p dora-message -p dora-core -p dora-transform -p dora-cli -p dora-node-api-c 2>&1 | grep -E "^test result|FAILED|panicked" | tee /tmp/claude-final-dora.txt
cd $D/apis/python/node && PYTHONPATH= $VENV/bin/python -m pytest -q tests
cd $D/nodes/frame-transform && PYTHONPATH= $VENV/bin/python -m pytest -q tests
cd $N/modules/simulation/mujoco_mickrobot && PYTHONPATH= $VENV/bin/python -m pytest -q tests
cd $N/examples/contract-core && ./run_validate.sh
```

Expected: no `FAILED`, all `test result: ok`, and totals ≥ the Task 1 baseline plus the new tests. If an existing Python API test fails for a reason unrelated to this work (for example a missing optional dependency), record it with its error text, and the baseline evidence that it also failed before.

- [ ] **Step 4: Write `feasibility.md`** (keep `## Baseline` and `## Friction` from earlier tasks; add):

```markdown
## Result

| Exit criterion (spec §9) | Evidence | Met |
|---|---|---|
| Tests pass, no regression | /tmp/claude-final-dora.txt totals vs baseline; pytest lines | yes/no |
| validate accepts good, refuses each bad with reason | run_validate.sh output | yes/no |
| Live run meets §7 | DORA_NAV examples/contract-core/records/*.json | yes/no |
| Mutation sweep 0 survivors | tools/contract-mutation-sweep.py output | yes/no |
| This report | — | yes |

## Size of each change

Output of `git diff --stat 1016eab0a..HEAD` (dora) and `git diff --stat a9257f5..HEAD` (DORA_NAV), grouped by component.

## What did not fit dora's model

One entry per friction item recorded during the tasks: what, why, and the
upstream change it implies.

## Effort for later slices

Per slice (perception row 13, agent path, data processing row 16, nav/arm
adoption rows 14 and 19): the items from the feature map, what this slice
already provides, and an estimate in engineer-days with its basis.
```

Fill every cell from the evidence produced. Write "no" where a criterion was not met, with the reason.

- [ ] **Step 5: Commit**

```bash
cd $D && git add tools/check-test-mapping.py docs/contract-core
git commit -m "docs(contract-core): test mapping and feasibility report

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

## Self-review notes

- **Spec coverage:**
  - §3 workspace: Task 1.
  - §4.1: Task 2.
  - §4.2: Task 5.
  - §4.3: Task 6.
  - §4.4: Task 7.
  - §4.5: Tasks 3 and 4.
  - §4.6: Task 8.
  - §4.7: Task 10, with the binding in Task 9.
  - §5: Tasks 11 and 12.
  - §6 data flow: Task 12 `good.yml`.
  - §7: Tasks 12 and 13.
  - §8: Tasks 2–15 tests, plus Tasks 14 and 15.
  - §9: Task 15 report.
  - §11 risks: Task 5 step 4 (PointCloud fallback), Task 1 step 3 (Python 3.11), Task 12 `MUJOCO_GL=egl`.
- **Deviations** are listed at the top; each traces to a reference file and line.
