#!/usr/bin/env python3
"""One-off edits to the feature map decided on 2026-11-03 (spec §2, plan decision 4).

Safe to run twice: corrections compare before writing, and rows are appended only
when their ID is not already present.
"""
import pathlib
import sys

import openpyxl

MAP = pathlib.Path(__file__).resolve().parents[1] / "docs/requirements/2026-10-26-feature-map-by-repo.xlsx"
FOUNDATION = "基础 · Foundation"
F03_NOTE = "Frame, rate and max-age remain (feasibility report, F.03)."

# sheet, ID, feature, package / location, status, existing basis, notes
ADDED = [
    ("dora", "F.13", "Rebase exp/contract-core onto maintenance-freeze-2026-11-03",
     "whole repo (branch exp/contract-core)", "built, to move",
     "26 experiment commits on 1016eab0a; the freeze tag is 107 commits newer and touches 18 files (~1.9k lines) in the contract areas",
     "Open item 1 of the 2026-11-03 handoff"),
    ("octos", "F.14", "Plan the octos work (F.08–F.10) against upstream main, not the diverged local clone",
     "crates/octos-dora-mcp", "basis exists",
     "The fork starts at upstream main 19ca7995; the local clone diverged on 2026-04-24 with 267 commits of its own",
     "Open item 2 of the 2026-11-03 handoff"),
    ("dora", "F.15", "Enforce a type's required metadata keys in dora validate (optionally on send in debug builds)",
     "libraries/core types, binaries/cli validate.rs", "new",
     "TypeDef.metadata in the std type files is parsed but read nowhere",
     "feasibility.md, did not fit item 3"),
    ("dora", "F.16", "Typed header send API (send_output_with_header) in Rust, Python and C that writes the header keys last and refuses shadowing",
     "apis/rust/node, apis/python/node, apis/c/node", "basis exists",
     "Header::write and dora.header exist; dora metadata is an open map the node owns",
     "feasibility.md, did not fit item 4"),
    ("dora", "F.17", "Daemon injects the frame dictionary and extrinsics paths from the dataflow frames: key, replacing DORA_FRAMES/DORA_EXTRINSICS and the validator's launch-dir mirror",
     "binaries/daemon spawn, libraries/core", "new",
     "Node manifests refuse DORA_* env (ENV_DENY_PREFIX); the validator mirrors the daemon's working-directory rule",
     "feasibility.md, did not fit items 6 and 7"),
    ("dora", "F.18", "Type check treats an unparameterised side as its declared default (or warns), e.g. PointCloud = PointCloud[fields=xyz]",
     "libraries/core/src/types.rs", "basis exists",
     "params_agree treats an empty side as a wildcard",
     "feasibility.md, did not fit item 19"),
    ("dora", "F.19", "child_frame field on ports, so dora validate checks both sides of a pose's dynamic edge and the runtime can be as strict",
     "libraries/message descriptor, libraries/core frames_check.rs", "new",
     "output_frames/input_frames exist; no descriptor field declares a port's child_frame",
     "feasibility.md, did not fit item 20"),
    ("dora", "F.20", "Expose Node.id in the Python node API",
     "apis/python/node/src/lib.rs", "basis exists",
     "Rust Node::id() exists but is not a #[pymethods] method; dora sets no DORA_NODE_ID",
     "feasibility.md, did not fit item 21"),
]


def row_of(ws, fid):
    for row in ws.iter_rows(min_row=2):
        if row[0].value == fid:
            return row
    raise SystemExit(f"{ws.title}: {fid} not found")


def main(path=MAP):
    wb = openpyxl.load_workbook(path)
    changed = []

    f05 = row_of(wb["dora"], "F.05")
    if f05[5].value != "basis exists":
        f05[5].value = "basis exists"
        f05[6].value = ("dora master has action and service patterns (goal_id, request_id); "
                        "the client-API helpers still need upstream design discussion")
        changed.append("F.05 status")

    f03 = row_of(wb["dora"], "F.03")
    notes = f03[9].value or ""
    if F03_NOTE not in notes:
        f03[9].value = (notes + " " + F03_NOTE).strip()
        changed.append("F.03 notes")

    for sheet, fid, feature, location, status, basis, note in ADDED:
        ws = wb[sheet]
        if any(r[0].value == fid for r in ws.iter_rows(min_row=2)):
            continue
        ws.append([fid, "F", FOUNDATION, feature, location, status, basis, None, None, note])
        changed.append(fid)

    if changed:
        wb.save(path)
    print("changed:", ", ".join(changed) or "nothing")


if __name__ == "__main__":
    main(*(sys.argv[1:2]))
