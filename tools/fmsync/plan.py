"""Compare the workbook with GitHub and list the actions that make GitHub match. Pure."""
from dataclasses import dataclass, field

from . import render
from .data import ESTIMATES, EXPERIMENT, REQ_ESTIMATES, ROW_NAMES


class PlanError(ValueError):
    pass


@dataclass(frozen=True)
class IssueState:
    key: str
    repo: str
    number: int
    id: int          # REST id (sub-issue API)
    node_id: str     # GraphQL id (project API)
    url: str
    title: str
    body: str
    labels: tuple


@dataclass
class State:
    issues: dict = field(default_factory=dict)      # key -> IssueState
    items: dict = field(default_factory=dict)       # key -> {field name: value}; present = in the project
    item_ids: dict = field(default_factory=dict)    # key -> project item id
    sub_issues: dict = field(default_factory=dict)  # requirement key -> set of child keys
    comments: set = field(default_factory=set)      # keys whose issue has its fm-comment marker


@dataclass(frozen=True)
class Action:
    op: str          # create_issue, update_issue, comment, add_item, set_field, add_sub_issue
    key: str
    repo: str = ""
    title: str = ""
    body: str = ""
    labels: tuple = ()
    field: str = ""
    value: object = None
    parent: str = ""


def _selected(only, row, key) -> bool:
    return only is None or row in only or key in only


def build(requirements, features, state, only=None):
    actions, warnings = [], []
    names = {q.row: q.name for q in requirements}
    feature_rows = {f.row for f in features if _selected(only, f.row, f.key)}
    for q in requirements:
        if _selected(only, q.row, q.key) or q.row in feature_rows:
            fields = {"Row": ROW_NAMES[q.row], "Target repo": "roadmap", "Kind": "requirement", "Feature ID": q.key}
            if q.row in REQ_ESTIMATES:
                fields["Estimate (days)"] = REQ_ESTIMATES[q.row]
            actions += _issue_actions(state, q.key, "roadmap", render.requirement_title(q),
                                      render.requirement_body(q), render.labels_for_requirement(q),
                                      fields, "Todo", None, None)
        for f in features:
            if f.row != q.row or not _selected(only, f.row, f.key):
                continue
            fields = {"Row": ROW_NAMES[f.row], "Target repo": f.repo, "Kind": f.kind, "Basis": f.status,
                      "Feature ID": f.id}
            if f.id in ESTIMATES:
                fields["Estimate (days)"] = ESTIMATES[f.id]
            experiment = f.id in EXPERIMENT
            actions += _issue_actions(state, f.key, f.repo, render.feature_title(f),
                                      render.feature_body(f, names[f.row]), render.labels_for_feature(f),
                                      fields, EXPERIMENT[f.id][0] if experiment else "Todo", q.key,
                                      render.experiment_comment(f.id) if experiment else None)
    wanted = {q.key for q in requirements} | {f.key for f in features}
    for key in sorted(set(state.issues) - wanted):
        warnings.append(f"{key}: {state.issues[key].url} is not in the workbook; left as it is")
    return actions, warnings


def _issue_actions(state, key, repo, title, body, labels, fields, status, parent, comment):
    out = []
    existing = state.issues.get(key)
    if existing is None:
        out.append(Action("create_issue", key, repo=repo, title=title, body=body, labels=tuple(labels)))
    else:
        if existing.repo != repo:
            raise PlanError(f"{key} is in {existing.repo}, the workbook says {repo}; move it by hand")
        prose, block = render.split(existing.body, f"{existing.repo}#{existing.number} ({key})")
        have = {name.lower() for name in existing.labels}
        missing = [name for name in labels if name.lower() not in have]
        if (render.normalize(existing.title) != render.normalize(title)
                or render.normalize(block) != render.normalize(body) or missing):
            out.append(Action("update_issue", key, repo=repo, title=title, body=render.compose(prose, body),
                              labels=tuple(sorted(set(existing.labels) | set(missing)))))
    if comment and key not in state.comments:
        out.append(Action("comment", key, repo=repo, body=comment))
    current = state.items.get(key)
    if current is None:
        out.append(Action("add_item", key))
        current = {}
    if "Status" not in current:  # new to the project, or a run stopped before Status was set
        out.append(Action("set_field", key, field="Status", value=status))
    for name, value in fields.items():
        if current.get(name) != value:
            out.append(Action("set_field", key, field=name, value=value))
    if parent and key not in state.sub_issues.get(parent, set()):
        out.append(Action("add_sub_issue", key, parent=parent))
    return out
