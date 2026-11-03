"""In-memory stand-in for fmsync.github.Gh, with the same method names and return shapes."""
import itertools

from fmsync.github import GhError
from fmsync.plan import IssueState
from fmsync.render import COMMENT_MARKER_RE, find_marker


class FakeGh:
    def __init__(self):
        self.ids = itertools.count(1)
        self.issues = {}          # (repo, number) -> IssueState
        self.comments = []        # (repo, number, body)
        self.subs = {}            # (repo, number) -> [child REST id]
        self.repo_labels = {}     # repo -> set
        self.project = None
        self.fields = {}          # name -> {"id","name","type","options"}
        self.items = {}           # content node id -> {"item_id", "fields"}
        self.view_ids = {}        # name -> id
        self.view_filters = {}    # id -> filter
        self.calls = []

    # issues
    def list_marked_issues(self, repo):
        return [s for (r, _), s in sorted(self.issues.items()) if r == repo and find_marker(s.body)]

    def create_issue(self, repo, title, body, labels, key):
        n = next(self.ids)
        s = IssueState(key, repo, n, 1000 + n, f"I_{n}", f"https://github.com/dorarobotics-dev/{repo}/issues/{n}",
                       title, body, tuple(labels))
        self.issues[(repo, n)] = s
        self.calls.append(("create_issue", key))
        return s

    def update_issue(self, repo, number, title, body, labels):
        old = self.issues[(repo, number)]
        self.issues[(repo, number)] = IssueState(old.key, repo, number, old.id, old.node_id, old.url,
                                                 title, body, tuple(labels))
        self.calls.append(("update_issue", old.key))

    def comment(self, repo, number, body):
        self.comments.append((repo, number, body))

    def comment_markers(self, repo, number):
        self.calls.append(("comment_markers", repo, number))
        return {k for r, n, b in self.comments if (r, n) == (repo, number) for k in COMMENT_MARKER_RE.findall(b)}

    def sub_issue_ids(self, repo, number):
        return list(self.subs.get((repo, number), []))

    def add_sub_issue(self, repo, number, child_id):
        if any(child_id in children for children in self.subs.values()):
            raise GhError(f"HTTP 422: issue {child_id} already has a parent")
        self.subs.setdefault((repo, number), []).append(child_id)

    def labels(self, repo):
        return set(self.repo_labels.get(repo, set()))

    def create_label(self, repo, name, color, description):
        if name.lower() in {n.lower() for n in self.repo_labels.get(repo, set())}:
            raise GhError(f"HTTP 422: label {name} already exists in {repo}")
        self.repo_labels.setdefault(repo, set()).add(name)

    # project
    def find_project(self, title):
        return self.project if self.project and self.project["title"] == title else None

    def create_project(self, title):
        self.project = {"id": "PVT_1", "number": 1, "title": title, "url": "https://github.com/orgs/x/projects/1"}
        self.fields = {"Title": {"id": "F_T", "name": "Title", "type": "TITLE", "options": {}},
                       "Status": {"id": "F_S", "name": "Status", "type": "SINGLE_SELECT",
                                  "options": {"Todo": "s1", "In Progress": "s2", "Done": "s3"}}}
        self.view_ids = {"View 1": "V_0"}
        return self.project

    def project_fields(self, project_id):
        return {k: dict(v, options=dict(v["options"])) for k, v in self.fields.items()}

    def create_field(self, project_id, name, data_type, options=()):
        if name in self.fields:
            raise GhError(f"field {name} already exists")
        self.fields[name] = {"id": f"F_{name}", "name": name, "type": data_type,
                             "options": {o: f"{name}:{o}" for o in options}}

    def set_status_options(self, field_id, options):
        self.fields["Status"]["options"] = {o: f"Status:{o}" for o in options}

    def project_items(self, project_id):
        return {k: {"item_id": v["item_id"], "fields": dict(v["fields"])} for k, v in self.items.items()}

    def add_item(self, project_id, content_id):
        self.items[content_id] = {"item_id": f"PVTI_{content_id}", "fields": {}}
        return f"PVTI_{content_id}"

    def set_field(self, project_id, item_id, field, value):
        for item in self.items.values():
            if item["item_id"] == item_id:
                if field["type"] == "SINGLE_SELECT" and value not in field["options"]:
                    raise GhError(f"no option {value!r} in field {field['name']}")
                item["fields"][field["name"]] = float(value) if field["type"] == "NUMBER" else value
                return
        raise KeyError(item_id)

    def views(self, project_id):
        return {name: {"id": vid, "filter": self.view_filters.get(vid, "")} for name, vid in self.view_ids.items()}

    def create_view(self, project_id, name, layout):
        vid = f"V_{len(self.view_ids)}"
        self.view_ids[name] = vid
        return vid

    def update_view(self, view_id, name=None, filter=None):
        if name is not None:
            old = next(k for k, v in self.view_ids.items() if v == view_id)
            self.view_ids[name] = self.view_ids.pop(old)
        if filter is not None:
            self.view_filters[view_id] = filter
