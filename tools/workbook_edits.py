#!/usr/bin/env python3
"""One-off edits to the feature map decided on 2026-11-03 (spec §2, plan decision 4).

Safe to run twice: corrections compare before writing, and rows are appended only
when their ID is not already present.
"""
import pathlib
import sys
from copy import copy

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


STYLE_ATTRS = ("font", "fill", "border", "alignment", "number_format", "protection")
ADDED_IDS = {a[1] for a in ADDED}


def status_fills(wb):
    """Status text -> fill, read from the rows that were not added by this script."""
    fills = {}
    for ws in wb.worksheets:
        for row in ws.iter_rows(min_row=2):
            if row[0].value in ADDED_IDS or row[0].value in (None, "F.05"):
                continue
            if len(row) < 6:
                continue
            c = row[5]
            if isinstance(c.value, str) and c.fill.fill_type:
                fills.setdefault(c.value, copy(c.fill))
    return fills


def style_row(ws, row, template, fill):
    """Copy the template row's styles onto row; set the status cell's fill. Return True if changed."""
    changed = False
    for src, dst in zip(template, row):
        for attr in STYLE_ATTRS:
            if attr == "fill" and dst.column == 6 and fill is not None:
                continue  # the status cell takes the status fill below
            if copy(getattr(dst, attr)) != copy(getattr(src, attr)):
                setattr(dst, attr, copy(getattr(src, attr)))
                changed = True
    if fill is not None and copy(row[5].fill) != copy(fill):
        row[5].fill = copy(fill)
        changed = True
    h = ws.row_dimensions[template[0].row].height
    if ws.row_dimensions[row[0].row].height != h:
        ws.row_dimensions[row[0].row].height = h
        changed = True
    return changed


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

    fills = status_fills(wb)
    restyle = [("dora", "F.05")] + [(a[0], a[1]) for a in ADDED]
    for sheet, fid in restyle:
        ws = wb[sheet]
        template = [r for r in ws.iter_rows(min_row=2) if r[0].value not in ADDED_IDS and r[0].value != "F.05"][-1]
        row = row_of(ws, fid)
        if style_row(ws, row, template, fills[row[5].value]) and fid not in changed:
            changed.append(fid + " style")

    for sheet in {a[0] for a in ADDED}:
        ws = wb[sheet]
        ref = f"A1:{openpyxl.utils.get_column_letter(ws.max_column)}{ws.max_row}"
        if ws.auto_filter.ref != ref:
            ws.auto_filter.ref = ref
            changed.append(f"{sheet} autofilter")

    if changed:
        wb.save(path)
    print("changed:", ", ".join(changed) or "nothing")


if __name__ == "__main__":
    main(*(sys.argv[1:2]))
