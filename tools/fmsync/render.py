"""Issue titles, bodies, labels and markers. Pure functions of the records."""
import re

from .data import EXPERIMENT, EXPERIMENT_EVIDENCE, ROW_ESTIMATE_NOTES

MARKER_RE = re.compile(r"<!-- fm:([A-Z0-9.]+) -->")
STATUS_LABEL = {"new": "status:new", "basis exists": "status:basis-exists",
                "built, to move": "status:built-to-move"}


def marker(key: str) -> str:
    return f"<!-- fm:{key} -->"


def find_marker(body):
    m = MARKER_RE.search(body or "")
    return m.group(1) if m else None


def normalize(text) -> str:
    lines = (text or "").replace("\r\n", "\n").strip().split("\n")
    return "\n".join(line.rstrip() for line in lines)


def requirement_title(q) -> str:
    return f"[R{q.row}] {q.name}"


def requirement_body(q) -> str:
    parts = [f"Requirement group **{q.row}** of the v1.3 embodied-middleware feature map.", "",
             "## Acceptance (summary)", "", q.acceptance_en or "—"]
    for heading, text in (("国家要求（必须完成）", q.national_zh), ("扩展功能及参数依据", q.expansion_zh),
                          ("量化指标要求", q.acceptance_zh)):
        if text:
            parts += ["", f"## {heading}", "", text]
    notes = ROW_ESTIMATE_NOTES.get(q.row)
    if notes:
        parts += ["", "## Effort (feasibility report)", ""] + [f"- {n}" for n in notes]
    parts += ["", "Features are the sub-issues of this issue. Source: "
              "`docs/requirements/2026-10-26-feature-map-by-repo.xlsx` in this repo.", "", marker(q.key)]
    return "\n".join(parts)


def feature_title(f) -> str:
    return f"[{f.id}] {f.title}"


def _cell(value) -> str:
    return (value or "—").replace("|", "\\|").replace("\n", " ")


def feature_body(f, requirement_name: str) -> str:
    lead = (f"Feature **{f.id}** — one PR into `{f.repo}`." if f.kind == "feature"
            else f"Deliverable **{f.id}** (not a PR to a code repo).")
    rows = [("Requirement", f"{f.row} · {requirement_name} (parent issue)"),
            ("Package / location", f.location), ("Status", f.status),
            ("Existing basis", f.basis), ("Notes", f.notes)]
    table = ["| | |", "|---|---|"] + [f"| {k} | {_cell(v)} |" for k, v in rows]
    return "\n".join([lead, "", *table, "", marker(f.key)])


def labels_for_requirement(q) -> tuple:
    return (f"row:{q.row}", "kind:requirement")


def labels_for_feature(f) -> tuple:
    return (f"row:{f.row}", f"kind:{f.kind}", STATUS_LABEL[f.status])


def experiment_comment(fid: str) -> str:
    status, delivered, missing = EXPERIMENT[fid]
    return "\n".join([f"**Experiment ({status}).** Delivered on `exp/contract-core`: {delivered}.", "",
                      f"Not delivered: {missing}.", "", EXPERIMENT_EVIDENCE])
