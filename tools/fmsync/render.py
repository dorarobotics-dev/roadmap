"""Issue titles, bodies, labels and markers. Pure functions of the records."""
import re

from .data import EXPERIMENT, EXPERIMENT_EVIDENCE, ROW_ESTIMATE_NOTES

MARKER_RE = re.compile(r"<!-- fm:([A-Z0-9.]+) -->")
COMMENT_MARKER_RE = re.compile(r"<!-- fm-comment:([A-Z0-9.]+) -->")
STATUS_LABEL = {"new": "status:new", "basis exists": "status:basis-exists",
                "built, to move": "status:built-to-move"}

BEGIN = "<!-- fm:begin -->"
END = "<!-- fm:end -->"


class LayoutError(ValueError):
    """An issue body whose managed block cannot be found safely."""


def marker(key: str) -> str:
    return f"<!-- fm:{key} -->"


def find_marker(body):
    body = body or ""
    i = body.find(BEGIN)
    m = MARKER_RE.search(body[i:] if i >= 0 else body)
    return m.group(1) if m else None


def comment_marker(key: str) -> str:
    return f"<!-- fm-comment:{key} -->"


def find_comment_marker(body):
    m = COMMENT_MARKER_RE.search(body or "")
    return m.group(1) if m else None


def normalize(text) -> str:
    lines = (text or "").replace("\r\n", "\n").strip().split("\n")
    return "\n".join(line.rstrip() for line in lines)


def _block(parts) -> str:
    """The sync-owned part of an issue body."""
    return "\n".join([BEGIN, "## Tracking", "", *parts, END])


def split(body, where="issue"):
    """(prose, block). (None, body) for a body from before the managed block existed."""
    text = (body or "").replace("\r\n", "\n")
    nb, ne = text.count(BEGIN), text.count(END)
    if nb == 0 and ne == 0:
        return None, text
    if nb != 1 or ne != 1:
        raise LayoutError(f"{where}: expected one {BEGIN} and one {END}, found {nb} and {ne}; fix the body by hand")
    i, e = text.index(BEGIN), text.index(END)
    if e < i:
        raise LayoutError(f"{where}: {END} before {BEGIN}; fix the body by hand")
    j = e + len(END)
    if text[j:].strip():
        raise LayoutError(f"{where}: text after {END}; move it above {BEGIN}")
    prose = text[:i].rstrip()
    if MARKER_RE.search(prose):
        raise LayoutError(f"{where}: an fm marker in the prose area; remove it by hand")
    return prose, text[i:j]


def compose(prose, block) -> str:
    prose = (prose or "").rstrip()
    if not prose.strip():
        return block
    return f"{prose}\n\n{block}"


def requirement_title(q) -> str:
    return f"[R{q.row}] {q.name}"


def requirement_body(q) -> str:
    parts = [f"Requirement group **{q.row}** of the v1.3 embodied-middleware feature map.", "",
             "### Acceptance (summary)", "", q.acceptance_en or "—"]
    for heading, text in (("国家要求（必须完成）", q.national_zh), ("扩展功能及参数依据", q.expansion_zh),
                          ("量化指标要求", q.acceptance_zh)):
        if text:
            parts += ["", f"### {heading}", "", text]
    notes = ROW_ESTIMATE_NOTES.get(q.row)
    if notes:
        parts += ["", "### Effort (feasibility report)", ""] + [f"- {n}" for n in notes]
    parts += ["", "Features are the sub-issues of this issue. Source: "
              "`docs/requirements/2026-10-26-feature-map-by-repo.xlsx` in this repo.", "", marker(q.key)]
    return _block(parts)


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
    return _block([lead, "", *table, "", marker(f.key)])


def labels_for_requirement(q) -> tuple:
    return (f"row:{q.row}", "kind:requirement")


def labels_for_feature(f) -> tuple:
    return (f"row:{f.row}", f"kind:{f.kind}", STATUS_LABEL[f.status])


def experiment_comment(fid: str) -> str:
    status, delivered, missing = EXPERIMENT[fid]
    return "\n".join([f"**Experiment ({status}).** Delivered on `exp/contract-core`: {delivered}.", "",
                      f"Not delivered: {missing}.", "", EXPERIMENT_EVIDENCE, "", comment_marker(fid)])
