#!/usr/bin/env python3
"""Sync the feature-map workbook to GitHub issues and the org project. Dry run unless --apply."""
import argparse
import pathlib
import sys
from collections import Counter

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from fmsync import apply as ap  # noqa: E402
from fmsync import plan, workbook, writeback  # noqa: E402
from fmsync.data import PROJECT_TITLE  # noqa: E402

REQ = pathlib.Path(__file__).resolve().parents[1] / "docs" / "requirements"
MAP = REQ / "2026-10-26-feature-map-by-repo.xlsx"
SOURCE = REQ / "具身智能本体中间件_扩展功能_v1.3_withoutbudget.xlsx"
OPS = ("create_issue", "update_issue", "comment", "add_item", "set_field", "add_sub_issue")


def describe(a) -> str:
    if a.op in ("create_issue", "update_issue"):
        return f"{a.op:14} {a.key:7} {a.repo:13} {a.title}"
    if a.op == "set_field":
        return f"{a.op:14} {a.key:7} {a.field} = {a.value}"
    if a.op == "add_sub_issue":
        return f"{a.op:14} {a.key:7} under {a.parent}"
    return f"{a.op:14} {a.key}"


def main(argv=None, gh=None, out=print) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=["setup", "sync", "writeback"])
    p.add_argument("--apply", action="store_true", help="change GitHub (or the workbook, for writeback)")
    p.add_argument("--only", default="", help="comma-separated rows (F, 13, ...) or IDs (F.04, R13, ...)")
    p.add_argument("--map", default=str(MAP))
    p.add_argument("--source", default=str(SOURCE))
    a = p.parse_args(argv)
    if gh is None:
        from fmsync.github import Gh
        gh = Gh()

    if a.command == "setup":
        ap.setup(gh, a.apply, out)
        if not a.apply:
            out("dry run: nothing changed (add --apply)")
        return 0

    project = gh.find_project(PROJECT_TITLE)
    state = ap.load_state(gh, project)
    if a.command == "writeback":
        urls = {k: s.url for k, s in state.issues.items()}
        if not a.apply:
            out(f"dry run: {len(urls)} issue URLs to write (add --apply)")
            return 0
        out(f"{writeback.write_issue_urls(a.map, urls)} cells written; recalculate the workbook before committing")
        return 0

    reqs, feats = workbook.read_requirements(a.map, a.source), workbook.read_features(a.map)
    only = {x.strip() for x in a.only.split(",") if x.strip()} or None
    actions, warnings = plan.build(reqs, feats, state, only)
    for w in warnings:
        out("WARNING " + w)
    for action in actions:
        out(describe(action))
    counts = Counter(x.op for x in actions)
    out("plan: " + ", ".join(f"{op} {counts.get(op, 0)}" for op in OPS))
    if not a.apply:
        out("dry run: nothing changed (add --apply)")
        return 0
    if project is None:
        out("no project: run `fm_sync.py setup --apply` first")
        return 1
    ap.execute(gh, project, actions, state, out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
