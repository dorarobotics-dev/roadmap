#!/usr/bin/env python3
"""Features added to the feature map after the 2026-11-05 reallocation, one entry per decision.

Safe to run twice: a row is added only when its ID is not on its sheet yet. It goes after
the last row of the same requirement row, styled like the sheet's other rows. Then run
`fm_sync.py sync` (creates the issue) and `writeback`.
"""
import openpyxl

from workbook_realloc import MAP, _data_rows, _fills, _rewrite, _template, _values

# date, sheet, ID, row, requirement, feature, package / location, status, existing basis, notes
ADDED = [
    ("2026-11-05", "dora", "13.18", 13, "感知类算子 · Perception operators",
     "Time-indexed transform buffer: moving edges fed from pose and joint-state streams, lookup at a "
     "timestamp with interpolation, routes across several moving edges (like tf2_ros::Buffer)",
     "libraries/transform (buffer module; Rust core, Python and C++ bindings)", "new",
     "libraries/transform on exp/contract-core: static lookup from frames.yml and extrinsics.yml, "
     "and pose_transform/resolve for one moving edge using the latest pose; no time index, no interpolation",
     "Needed for lookups at a sensor's capture time and for arm chains with several moving joints "
     "(e.g. a wrist camera). Builds on 13.01."),
]


def main(path=MAP):
    wb = openpyxl.load_workbook(path)
    fills = _fills(wb)
    changed = []
    for date, sheet, fid, row, req, feature, location, status, basis, note in ADDED:
        ws = wb[sheet]
        rows = [_values(r) for r in _data_rows(ws)]
        if any(v[0] == fid for v in rows):
            continue
        template = _template(ws)
        at = max((i for i, v in enumerate(rows) if str(v[1]) == str(row)), default=len(rows) - 1) + 1
        rows.insert(at, [fid, row, req, feature, location, status, basis, None, None, f"{note} Added {date}."])
        _rewrite(ws, rows, fills, template)
        changed.append(f"{fid} added to {sheet}")
    if changed:
        wb.save(path)
    print("changed:", ", ".join(changed) if changed else "nothing")


if __name__ == "__main__":
    main()
