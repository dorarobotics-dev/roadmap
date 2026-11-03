"""Create the project scaffolding, read GitHub state, and carry out planned actions."""
from .data import EXPERIMENT, FIELDS, LABELS, PROJECT_TITLE, REPOS, STATUS_OPTIONS, VIEWS
from .plan import State


def setup(gh, apply, log=print):
    """Labels in every repo; the project with its Status options, fields and views. Returns the project."""
    for repo in REPOS:
        have = gh.labels(repo)
        for name, (color, description) in LABELS.items():
            if name not in have:
                log(f"label {repo} {name}")
                if apply:
                    gh.create_label(repo, name, color, description)
    project = gh.find_project(PROJECT_TITLE)
    if project is None:
        log(f"project {PROJECT_TITLE!r}")
        if not apply:
            log("fields and views follow once the project exists")
            return None
        project = gh.create_project(PROJECT_TITLE)
    fields = gh.project_fields(project["id"])
    if list(fields["Status"]["options"]) != list(STATUS_OPTIONS):
        log("Status options: " + ", ".join(STATUS_OPTIONS))
        if apply:
            gh.set_status_options(fields["Status"]["id"], STATUS_OPTIONS)
    for name, (data_type, options) in FIELDS.items():
        if name not in fields:
            log(f"field {name} ({data_type})")
            if apply:
                gh.create_field(project["id"], name, data_type, options)
        elif options and list(fields[name]["options"]) != list(options):
            raise ValueError(f"field {name} exists with options {list(fields[name]['options'])}; fix it by hand")
    views = gh.views(project["id"])
    if "Overview" not in views and "View 1" in views:
        log("view View 1 -> Overview")
        if apply:
            gh.update_view(views["View 1"], name="Overview")
        views["Overview"] = views.pop("View 1")
    for name, layout, view_filter in VIEWS:
        if name not in views:
            log(f"view {name} ({layout}) {view_filter}".rstrip())
            if apply:
                view_id = gh.create_view(project["id"], name, layout)
                if view_filter:
                    gh.update_view(view_id, filter=view_filter)
    return project


def load_state(gh, project, repos=REPOS) -> State:
    state = State()
    for repo in repos:
        for s in gh.list_marked_issues(repo):
            if s.key in state.issues:
                raise ValueError(f"marker {s.key} is on two issues: {state.issues[s.key].url} and {s.url}")
            state.issues[s.key] = s
    by_node = {s.node_id: k for k, s in state.issues.items()}
    by_id = {s.id: k for k, s in state.issues.items()}
    if project:
        for node_id, item in gh.project_items(project["id"]).items():
            key = by_node.get(node_id)
            if key:
                state.items[key] = item["fields"]
                state.item_ids[key] = item["item_id"]
    for key, s in state.issues.items():
        if key in EXPERIMENT and key in gh.comment_markers(s.repo, s.number):
            state.comments.add(key)
        if key.startswith("R"):
            state.sub_issues[key] = {by_id[i] for i in gh.sub_issue_ids(s.repo, s.number) if i in by_id}
    return state


def execute(gh, project, actions, state, log=print) -> dict:
    issues, item_ids = dict(state.issues), dict(state.item_ids)
    fields = gh.project_fields(project["id"])
    for a in actions:
        if a.op == "create_issue":
            issues[a.key] = gh.create_issue(a.repo, a.title, a.body, a.labels, a.key)
            log(f"created {a.key} {issues[a.key].url}")
        elif a.op == "update_issue":
            s = issues[a.key]
            gh.update_issue(s.repo, s.number, a.title, a.body, a.labels)
            log(f"updated {a.key} {s.url}")
        elif a.op == "comment":
            s = issues[a.key]
            gh.comment(s.repo, s.number, a.body)
        elif a.op == "add_item":
            item_ids[a.key] = gh.add_item(project["id"], issues[a.key].node_id)
        elif a.op == "set_field":
            gh.set_field(project["id"], item_ids[a.key], fields[a.field], a.value)
        elif a.op == "add_sub_issue":
            parent = issues[a.parent]
            gh.add_sub_issue(parent.repo, parent.number, issues[a.key].id)
        else:
            raise ValueError(f"unknown action {a.op}")
    return issues
