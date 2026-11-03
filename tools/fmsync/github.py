"""Thin wrappers over `gh api` (REST and GraphQL) for the org dorarobotics-dev only."""
import json
import subprocess
import time

from .data import ORG
from .plan import IssueState
from .render import find_marker

RETRYABLE = ("rate limit", "HTTP 429", "HTTP 502", "HTTP 503")
CREATE_PAUSE_S = 1.0


class GhError(RuntimeError):
    pass


def _run(args, stdin=None) -> str:
    p = subprocess.run(["gh", *args], input=stdin, capture_output=True, text=True)
    if p.returncode != 0:
        raise GhError(f"gh {' '.join(args[:4])}: {p.stderr.strip() or p.stdout.strip()}")
    return p.stdout


class Gh:
    def __init__(self, runner=_run, sleep=time.sleep):
        self._runner, self._sleep = runner, sleep

    # -- transport -----------------------------------------------------------------------------
    def _call(self, args, stdin=None) -> str:
        for attempt in range(5):
            try:
                return self._runner(args, stdin)
            except GhError as e:
                if attempt == 4 or not any(s in str(e) for s in RETRYABLE):
                    raise
                self._sleep(60 * (attempt + 1))
        raise AssertionError("unreachable")

    def api(self, path, method="GET", body=None, paginate=False, jq=None) -> str:
        if path.startswith(("repos/", "orgs/")) and not path.startswith((f"repos/{ORG}/", f"orgs/{ORG}/")):
            raise GhError(f"refusing {method} {path}: outside {ORG}")
        args = ["api"] + (["--paginate"] if paginate else []) + (["-X", method] if method != "GET" else [])
        args.append(path)
        if jq:
            args += ["--jq", jq]
        if body is not None:
            args += ["--input", "-"]
        return self._call(args, json.dumps(body) if body is not None else None)

    def graphql(self, query, **variables) -> dict:
        out = json.loads(self._call(["api", "graphql", "--input", "-"],
                                    json.dumps({"query": query, "variables": variables})))
        if out.get("errors"):
            raise GhError("; ".join(e.get("message", str(e)) for e in out["errors"]))
        return out["data"]

    # -- issues --------------------------------------------------------------------------------
    def list_marked_issues(self, repo) -> list:
        out = self.api(f"repos/{ORG}/{repo}/issues?state=all&per_page=100", paginate=True,
                       jq=".[] | select(.pull_request == null) | "
                          "{number, id, node_id, html_url, title, body, labels: [.labels[].name]}")
        issues = []
        for line in out.splitlines():
            if not line.strip():
                continue
            d = json.loads(line)
            key = find_marker(d.get("body"))
            if key:
                issues.append(IssueState(key, repo, d["number"], d["id"], d["node_id"], d["html_url"],
                                         d["title"], d.get("body") or "", tuple(d["labels"])))
        return issues

    def create_issue(self, repo, title, body, labels, key) -> IssueState:
        d = json.loads(self.api(f"repos/{ORG}/{repo}/issues", "POST",
                                {"title": title, "body": body, "labels": list(labels)}))
        self._sleep(CREATE_PAUSE_S)
        return IssueState(key, repo, d["number"], d["id"], d["node_id"], d["html_url"], title, body, tuple(labels))

    def update_issue(self, repo, number, title, body, labels) -> None:
        self.api(f"repos/{ORG}/{repo}/issues/{number}", "PATCH",
                 {"title": title, "body": body, "labels": list(labels)})

    def comment(self, repo, number, body) -> None:
        self.api(f"repos/{ORG}/{repo}/issues/{number}/comments", "POST", {"body": body})
        self._sleep(CREATE_PAUSE_S)

    def sub_issue_ids(self, repo, number) -> list:
        out = self.api(f"repos/{ORG}/{repo}/issues/{number}/sub_issues?per_page=100", paginate=True, jq=".[].id")
        return [int(x) for x in out.split()]

    def add_sub_issue(self, repo, number, child_id) -> None:
        self.api(f"repos/{ORG}/{repo}/issues/{number}/sub_issues", "POST", {"sub_issue_id": child_id})

    def labels(self, repo) -> set:
        return set(self.api(f"repos/{ORG}/{repo}/labels?per_page=100", paginate=True, jq=".[].name").splitlines())

    def create_label(self, repo, name, color, description) -> None:
        self.api(f"repos/{ORG}/{repo}/labels", "POST", {"name": name, "color": color, "description": description})

    # -- project -------------------------------------------------------------------------------
    def find_project(self, title):
        d = self.graphql("query($org:String!){organization(login:$org){id projectsV2(first:50)"
                         "{nodes{id number title url}}}}", org=ORG)
        for p in d["organization"]["projectsV2"]["nodes"]:
            if p["title"] == title:
                return p
        return None

    def create_project(self, title) -> dict:
        org = self.graphql("query($org:String!){organization(login:$org){id}}", org=ORG)["organization"]["id"]
        d = self.graphql("mutation($o:ID!,$t:String!){createProjectV2(input:{ownerId:$o,title:$t})"
                         "{projectV2{id number title url}}}", o=org, t=title)
        return d["createProjectV2"]["projectV2"]

    def project_fields(self, project_id) -> dict:
        d = self.graphql("query($id:ID!){node(id:$id){... on ProjectV2{fields(first:50){nodes{"
                         "... on ProjectV2FieldCommon{id name dataType} "
                         "... on ProjectV2SingleSelectField{options{id name}}}}}}}", id=project_id)
        return {f["name"]: {"id": f["id"], "name": f["name"], "type": f["dataType"],
                            "options": {o["name"]: o["id"] for o in f.get("options", [])}}
                for f in d["node"]["fields"]["nodes"] if f}

    def create_field(self, project_id, name, data_type, options=()) -> None:
        inp = {"projectId": project_id, "name": name, "dataType": data_type}
        if options:
            inp["singleSelectOptions"] = [{"name": o, "color": "GRAY", "description": ""} for o in options]
        self.graphql("mutation($i:CreateProjectV2FieldInput!){createProjectV2Field(input:$i)"
                     "{projectV2Field{... on ProjectV2FieldCommon{id}}}}", i=inp)

    def set_status_options(self, field_id, options) -> None:
        colors = ("GRAY", "BLUE", "YELLOW", "PURPLE", "GREEN")
        self.graphql("mutation($i:UpdateProjectV2FieldInput!){updateProjectV2Field(input:$i)"
                     "{projectV2Field{... on ProjectV2FieldCommon{id}}}}",
                     i={"fieldId": field_id, "singleSelectOptions": [
                         {"name": o, "color": colors[n % len(colors)], "description": ""}
                         for n, o in enumerate(options)]})

    def project_items(self, project_id) -> dict:
        items, after = {}, None
        while True:
            d = self.graphql(
                "query($id:ID!,$after:String){node(id:$id){... on ProjectV2{items(first:100,after:$after){"
                "pageInfo{hasNextPage endCursor} nodes{id content{... on Issue{id}} fieldValues(first:20){nodes{"
                "... on ProjectV2ItemFieldSingleSelectValue{name field{... on ProjectV2FieldCommon{name}}} "
                "... on ProjectV2ItemFieldTextValue{text field{... on ProjectV2FieldCommon{name}}} "
                "... on ProjectV2ItemFieldNumberValue{number field{... on ProjectV2FieldCommon{name}}}}}}}}}}",
                id=project_id, after=after)
            page = d["node"]["items"]
            for n in page["nodes"]:
                if not n.get("content"):
                    continue
                fields = {}
                for v in n["fieldValues"]["nodes"]:
                    if v and "field" in v:
                        fields[v["field"]["name"]] = v.get("name", v.get("text", v.get("number")))
                items[n["content"]["id"]] = {"item_id": n["id"], "fields": fields}
            if not page["pageInfo"]["hasNextPage"]:
                return items
            after = page["pageInfo"]["endCursor"]

    def add_item(self, project_id, content_id) -> str:
        d = self.graphql("mutation($p:ID!,$c:ID!){addProjectV2ItemById(input:{projectId:$p,contentId:$c})"
                         "{item{id}}}", p=project_id, c=content_id)
        return d["addProjectV2ItemById"]["item"]["id"]

    def set_field(self, project_id, item_id, field, value) -> None:
        if field["type"] == "SINGLE_SELECT":
            if value not in field["options"]:
                raise GhError(f"no option {value!r} in field {field.get('name', field['id'])}")
            v = {"singleSelectOptionId": field["options"][value]}
        elif field["type"] == "NUMBER":
            v = {"number": float(value)}
        else:
            v = {"text": str(value)}
        self.graphql("mutation($p:ID!,$i:ID!,$f:ID!,$value:ProjectV2FieldValue!){updateProjectV2ItemFieldValue("
                     "input:{projectId:$p,itemId:$i,fieldId:$f,value:$value}){projectV2Item{id}}}",
                     p=project_id, i=item_id, f=field["id"], value=v)

    def views(self, project_id) -> dict:
        d = self.graphql("query($id:ID!){node(id:$id){... on ProjectV2{views(first:50){nodes{id name}}}}}",
                         id=project_id)
        return {v["name"]: v["id"] for v in d["node"]["views"]["nodes"]}

    def create_view(self, project_id, name, layout) -> str:
        d = self.graphql("mutation($p:ID!,$n:String!,$l:ProjectV2ViewLayout!){createProjectV2View("
                         "input:{projectId:$p,name:$n,layout:$l}){projectV2View{id}}}", p=project_id, n=name, l=layout)
        return d["createProjectV2View"]["projectV2View"]["id"]

    def update_view(self, view_id, name=None, filter=None) -> None:
        inp = {"viewId": view_id}
        if name is not None:
            inp["name"] = name
        if filter is not None:
            inp["filter"] = filter
        self.graphql("mutation($i:UpdateProjectV2ViewInput!){updateProjectV2View(input:$i){projectV2View{id}}}",
                     i=inp)
