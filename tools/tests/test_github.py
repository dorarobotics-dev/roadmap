import json

import pytest

from fmsync.github import Gh, GhError


class Runner:
    """Records gh calls and answers them from a list of canned outputs (str or exception)."""

    def __init__(self, *answers):
        self.answers, self.calls = list(answers), []

    def __call__(self, args, stdin=None):
        self.calls.append((args, json.loads(stdin) if stdin else None))
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer


def gh(*answers):
    r = Runner(*answers)
    return Gh(runner=r, sleep=lambda s: None), r


def test_create_issue_posts_json_and_returns_state():
    g, r = gh(json.dumps({"number": 7, "id": 77, "node_id": "I_7", "html_url": "u7"}))
    s = g.create_issue("dora", "[F.04] t", "body <!-- fm:F.04 -->", ("row:F",), "F.04")
    args, body = r.calls[0]
    assert args == ["api", "-X", "POST", "repos/dorarobotics-dev/dora/issues", "--input", "-"]
    assert body == {"title": "[F.04] t", "body": "body <!-- fm:F.04 -->", "labels": ["row:F"]}
    assert (s.key, s.repo, s.number, s.id, s.node_id, s.url) == ("F.04", "dora", 7, 77, "I_7", "u7")


def test_list_marked_issues_skips_unmarked():
    lines = "\n".join(json.dumps(x) for x in [
        {"number": 1, "id": 11, "node_id": "I_1", "html_url": "u1", "title": "a", "body": "x <!-- fm:R13 -->",
         "labels": ["row:13"]},
        {"number": 2, "id": 12, "node_id": "I_2", "html_url": "u2", "title": "b", "body": None, "labels": []},
    ])
    g, r = gh(lines + "\n")
    issues = g.list_marked_issues("roadmap")
    assert [i.key for i in issues] == ["R13"] and issues[0].labels == ("row:13",)
    assert r.calls[0][0][:3] == ["api", "--paginate", "repos/dorarobotics-dev/roadmap/issues?state=all&per_page=100"]


def test_owner_guard():
    g, _ = gh()
    with pytest.raises(GhError, match="outside dorarobotics-dev"):
        g.api("repos/dora-rs/dora/issues", method="POST", body={})


def test_graphql_errors_raise():
    g, _ = gh(json.dumps({"errors": [{"message": "nope"}]}))
    with pytest.raises(GhError, match="nope"):
        g.graphql("query { viewer { login } }")


def test_rate_limit_is_retried():
    g, r = gh(GhError("HTTP 403: You have exceeded a secondary rate limit"), json.dumps({"data": {"x": 1}}))
    assert g.graphql("query { x }") == {"x": 1}
    assert len(r.calls) == 2


def test_other_errors_are_not_retried():
    g, r = gh(GhError("HTTP 422: Validation Failed"))
    with pytest.raises(GhError, match="422"):
        g.graphql("query { x }")
    assert len(r.calls) == 1


def test_set_field_value_shapes():
    ok = json.dumps({"data": {"updateProjectV2ItemFieldValue": {"projectV2Item": {"id": "PVTI"}}}})
    g, r = gh(ok, ok, ok)
    g.set_field("P", "PVTI", {"id": "F1", "type": "SINGLE_SELECT", "options": {"dora": "O1"}}, "dora")
    g.set_field("P", "PVTI", {"id": "F2", "type": "TEXT", "options": {}}, "F.04")
    g.set_field("P", "PVTI", {"id": "F3", "type": "NUMBER", "options": {}}, 3)
    values = [c[1]["variables"]["value"] for c in r.calls]
    assert values == [{"singleSelectOptionId": "O1"}, {"text": "F.04"}, {"number": 3.0}]


def test_unknown_option_is_an_error():
    g, _ = gh()
    with pytest.raises(GhError, match="no option 'x' in field Repo"):
        g.set_field("P", "I", {"id": "F", "name": "Repo", "type": "SINGLE_SELECT", "options": {}}, "x")


def test_comment_markers_reads_all_comment_bodies():
    bodies = "Experiment text\nmore\n\n<!-- fm-comment:13.02 -->\nan unrelated comment\n"
    g, r = gh(bodies)
    assert g.comment_markers("dora", 5) == {"13.02"}
    assert r.calls[0][0] == ["api", "--paginate", "repos/dorarobotics-dev/dora/issues/5/comments?per_page=100",
                             "--jq", ".[].body"]


def test_comment_markers_none():
    g, _ = gh("")
    assert g.comment_markers("dora", 5) == set()


def test_views_returns_id_and_filter():
    g, r = gh(json.dumps({"data": {"node": {"views": {"nodes": [
        {"id": "V1", "name": "Overview", "filter": None},
        {"id": "V2", "name": "Row 13", "filter": 'row:"13 感知类算子 Perception"'}]}}}}))
    assert g.views("P") == {"Overview": {"id": "V1", "filter": ""},
                            "Row 13": {"id": "V2", "filter": 'row:"13 感知类算子 Perception"'}}
    assert "filter" in r.calls[0][1]["query"]
