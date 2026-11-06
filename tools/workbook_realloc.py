#!/usr/bin/env python3
"""One-off repo reallocation of the feature map, decided on 2026-11-05.

dora stays the slim core (runtime, APIs, descriptor and validate, shared std types,
transform library, record/replay, telemetry, daemon security and scheduling) and works
without dora-hub. DORA_NAV takes the nav2 role, dora-moveit2 the MoveIt 2 role. Every
optional algorithm or device/platform integration (perception, cognition, data
processing, inference, drivers, teleop devices, gateway, exporters) moves to dora-hub.
Dependencies run dora <- dora-hub <- DORA_NAV / dora-moveit2.

Safe to run twice: a row is moved only while it is still on its old sheet, and every
text change compares before writing. The GitHub issues are moved separately
(`gh issue transfer`), then `fm_sync.py sync` and `writeback` catch up.
"""
import pathlib
from copy import copy

import openpyxl

from workbook_edits import STYLE_ATTRS

MAP = pathlib.Path(__file__).resolve().parents[1] / "docs/requirements/2026-10-26-feature-map-by-repo.xlsx"
HUB = "dora-hub"
DATE = "2026-11-05"
DP = "node-hub/dora-data-processing"
PERC = "node-hub/dora-perception"
GW = "node-hub/dora-gateway (new)"

# ID -> (old sheet, new package / location, new feature title or None)
MOVES = {
    "13.02": ("dora", "node-hub/dora-frame-transform (new; experiment code in dora@exp/contract-core nodes/frame-transform)", None),
    "13.04": ("dora", "node-hub/dora-camera-geometry (new, like image_geometry)",
              "Camera intrinsics and image↔3-D projection library (like image_geometry)"),
    "13.05": ("dora", "node-hub/dora-time-align (new)", None),
    "19.07": ("dora", "node-hub/dora-time-align (with 13.05)", None),
    "16.01": ("dora", f"{DP} (new): filter", None),
    "16.02": ("dora", f"{DP}: compress", None),
    "16.03": ("dora", f"{DP}: clean", None),
    "16.05": ("dora", f"{DP}: stage stats and A/B comparison (per-node metrics from dora telemetry)", None),
    "17.03": ("dora", "node-hub/dora-inference (new, Python library): inference base", None),
    "20.02": ("dora", "node-hub/dora-inference: NPU backend", None),
    "18.02": ("dora", "node-hub/dora-recording-upload (new); reader integrity API in dora (18.08)", None),
    "21.01": ("dora", GW, None),
    "21.03": ("dora", GW, None),
    "21.04": ("dora", GW, None),
    "21.05": ("dora", GW, None),
    "21.06": ("dora", GW, None),
    "23.05": ("dora", "node-hub/dora-alert-exporter (new)", None),
    "25.06": ("dora", "node-hub/dora-dataset-record (existing node, extend)", None),
    "13.06": ("DORA_NAV", f"{PERC} (new): lidar + RGB fusion", None),
    "13.09": ("DORA_NAV", f"{PERC}: ground segmentation", None),
    "13.10": ("DORA_NAV", f"{PERC}: clustering", None),
    "13.12": ("DORA_NAV", f"{PERC}: 2-D → 3-D lifting", None),
    "13.13": ("DORA_NAV", f"{PERC}: association and velocity", None),
    "15.02": ("DORA_NAV", "node-hub/dora-trajectory-prediction (new)", None),
    "19.01": ("DORA_NAV", "node-hub/dora-rslidar, dora-livox (code moves from DORA_NAV modules/drivers)", None),
    "15.03": ("dora-moveit2", "node-hub/dora-intent-recognition (new)", None),
    "25.02": ("dora-moveit2", "node-hub/dora-teleop-calibration (new)", None),
    "25.03": ("dora-moveit2", "node-hub/dora-gesture (new)", None),
}

# Moved to dora-hub at first, then returned: an integration dataflow that wires hub nodes
# to a DORA_NAV robot lives in DORA_NAV (like 15.06). ID -> (sheet, location)
RETURNS = {
    "13.14": ("DORA_NAV", "examples/perception (wires the dora-hub perception nodes to the DORA_NAV sim)"),
}

# sheet, ID, row, requirement, feature, package / location, status, existing basis, notes
ADDED = [
    ("dora", "18.08", 18, "云端适配对接 · Cloud data platform",
     "Recording reader reports a missing footer and a torn last record",
     "libraries/recording (reader API)", "new",
     "RecordingReader stops at the footer magic without parsing it and treats a missing footer "
     "or a torn tail as normal EOF, so a truncated file reads as complete",
     f"Needed by 18.02 (upload, dora-hub). Added {DATE} with the repo reallocation."),
]

SUMMARY = {
    "dora": ("rclcpp / rclpy, launch, ros2 CLI, rosbag2, common_interfaces, tf2, actions, SROS2",
             "Slim core; works without dora-hub. Runtime, node and client APIs, CLI, descriptor and validate. "
             "Header keys, validity, frames, shared std types (cross-repo contracts), transform library, "
             "daemon identity and transport security, scheduling, telemetry and alerts, record/replay, ROS 2 bridge."),
    "DORA_NAV": ("nav2, plus the robot description and bringup packages",
                 "Navigation, pinned a9257f5: localization, mapping, planners, controllers, behaviour, missions, "
                 "chassis configs, robot descriptions, nav2 bridge, MuJoCo mobile-base sim, and the dataflows "
                 "that wire dora-hub perception and cognition into navigation."),
    "dora-moveit2": ("moveit2, including moveit_servo",
                     "Manipulation: planning scene, IK, planning, execution, limit layer, task status, "
                     "VLA action input, teleop limits and manual stop, MuJoCo arm sim."),
    "dora-hub": ("separately released packages (pcl_ros, image_transport plugins, message_filters-style nodes, "
                 "drivers, rosbridge, vision and model packages)",
                 "Optional nodes and libraries: perception, cognition, data processing, inference base and backends, "
                 "sensor drivers, teleop devices, frame-transform and time-align nodes, gateway, exporters, "
                 "plus patches to existing nodes. Depends on dora only, never on DORA_NAV or dora-moveit2."),
}
LEGEND_A3 = ("dora-hub: optional nodes and libraries (new packages and patches to existing ones); "
             "depends on dora only. delivery: tender deliverables, not PRs to any dora repo.")
REALLOC_NOTE = "Repo allocation {date}: moved from {old}."


def _id_key(fid):
    row, num = fid.split(".")
    return ("0" if row == "F" else row, int(num))


def _data_rows(ws):
    return [r for r in ws.iter_rows(min_row=2) if r[0].value is not None]


def _values(row):
    return [c.value for c in row[:10]] + [None] * (10 - len(row[:10]))


def _rewrite(ws, rows, fills, template_styles):
    """Write rows (lists of 10 values) from row 2 on, styled like the template; clear the rest."""
    old_max = ws.max_row
    for i, vals in enumerate(rows, start=2):
        for col, v in enumerate(vals, start=1):
            ws.cell(i, col).value = v
        cells = [ws.cell(i, col) for col in range(1, 11)]
        for src, dst in zip(template_styles, cells):
            for attr in STYLE_ATTRS:
                setattr(dst, attr, copy(src[attr]))
        cells[5].fill = copy(fills[vals[5]])
        ws.row_dimensions[i].height = template_styles[0]["height"]
    last = len(rows) + 1
    if old_max > last:
        ws.delete_rows(last + 1, old_max - last)
    ws.auto_filter.ref = f"A1:J{last}"


def _template(ws):
    row = _data_rows(ws)[0]
    styles = [{a: copy(getattr(c, a)) for a in STYLE_ATTRS} for c in row[:10]]
    styles[0]["height"] = ws.row_dimensions[row[0].row].height
    return styles


def _fills(wb):
    fills = {}
    for ws in wb.worksheets:
        for row in ws.iter_rows(min_row=2):
            if len(row) >= 6 and isinstance(row[5].value, str) and row[5].fill.fill_type:
                fills.setdefault(row[5].value, copy(row[5].fill))
    return fills


def main(path=MAP):
    wb = openpyxl.load_workbook(path)
    fills = _fills(wb)
    changed = []

    sheets = {name: [_values(r) for r in _data_rows(wb[name])] for name in ("dora", "DORA_NAV", "dora-moveit2", HUB)}
    templates = {name: _template(wb[name]) for name in sheets}

    for fid, (old, location, title) in MOVES.items():
        hit = [v for v in sheets[old] if v[0] == fid]
        if not hit:
            if not any(v[0] == fid for v in sheets[HUB]):
                raise SystemExit(f"{fid}: neither on {old} nor on {HUB}")
            continue
        vals = hit[0]
        sheets[old].remove(vals)
        vals[4] = location
        if title:
            vals[3] = title
        note = REALLOC_NOTE.format(date=DATE, old=old)
        vals[9] = f"{vals[9]} {note}".strip() if vals[9] else note
        sheets[HUB].append(vals)
        changed.append(f"{fid} {old}->{HUB}")

    for fid, (sheet, location) in RETURNS.items():
        hit = [v for v in sheets[HUB] if v[0] == fid]
        if hit:
            vals = hit[0]
            sheets[HUB].remove(vals)
            vals[4] = location
            vals[9] = REALLOC_NOTE.format(date=DATE, old=HUB).replace("moved from", "returned from")
            at = max((i for i, v in enumerate(sheets[sheet]) if _id_key(v[0]) < _id_key(fid)), default=-1) + 1
            sheets[sheet].insert(at, vals)
            changed.append(f"{fid} {HUB}->{sheet}")

    for sheet, fid, row, req, feature, location, status, basis, note in ADDED:
        rows = sheets[sheet]
        if not any(v[0] == fid for v in rows):
            # after the last row of the same requirement row, keeping the sheet's order
            at = max((i for i, v in enumerate(rows) if str(v[1]) == str(row)), default=len(rows) - 1) + 1
            rows.insert(at, [fid, row, req, feature, location, status, basis, None, None, note])
            changed.append(f"{fid} added to {sheet}")

    if changed:
        sheets[HUB].sort(key=lambda v: _id_key(v[0]))
        for name, rows in sheets.items():
            _rewrite(wb[name], rows, fills, templates[name])

    summary = wb["Summary"]
    for row in summary.iter_rows(min_row=2):
        if row[0].value in SUMMARY:
            ros, scope = SUMMARY[row[0].value]
            if row[1].value != ros or row[2].value != scope:
                row[1].value, row[2].value = ros, scope
                changed.append(f"Summary {row[0].value}")
    legend = wb["Legend"]
    if legend["A3"].value != LEGEND_A3:
        legend["A3"].value = LEGEND_A3
        changed.append("Legend A3")

    if changed:
        wb.save(path)
    print("changed:", ", ".join(changed) if changed else "nothing")


if __name__ == "__main__":
    main()
