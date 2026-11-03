import re
from collections import Counter

import pytest

from fmsync import plan, render
from fmsync.model import Feature, Requirement

Q13 = Requirement("13", "感知类算子 · Perception operators", "Fusion.", "国", "扩", "验")
QF = Requirement("F", "基础 · Foundation", "Prerequisites.", "", "", "")
F02 = Feature("13.02", "13", "dora", "feature", "frame_transform node", "nodes/frame-transform",
              "built, to move", "ref", "", "", "")
F03 = Feature("13.03", "13", "dora", "feature", "Perception schemas", "libraries/core/types",
              "new", "", "", "", "")
REQS, FEATS = [QF, Q13], [F02, F03]


def issue(key, repo, title, body, labels, n=1):
    return plan.IssueState(key, repo, n, 1000 + n, f"I_{n}", f"https://github.com/o/{repo}/issues/{n}",
                           title, body, tuple(labels))


def synced_state():
    """State as it is right after a full apply of REQS and FEATS."""
    st = plan.State()
    for n, q in enumerate(REQS, 1):
        st.issues[q.key] = issue(q.key, "roadmap", render.requirement_title(q), render.requirement_body(q),
                                 render.labels_for_requirement(q), n)
    for n, f in enumerate(FEATS, 10):
        st.issues[f.key] = issue(f.key, "dora", render.feature_title(f), render.feature_body(f, Q13.name),
                                 render.labels_for_feature(f), n)
    for a in plan.build(REQS, FEATS, plan.State())[0]:
        if a.op == "add_item":
            st.items[a.key] = {}
            st.item_ids[a.key] = "PVTI_" + a.key
        elif a.op == "set_field":
            st.items[a.key][a.field] = a.value
        elif a.op == "add_sub_issue":
            st.sub_issues.setdefault(a.parent, set()).add(a.key)
        elif a.op == "comment":
            st.comments.add(a.key)
    return st


def test_empty_state_creates_everything():
    actions, warnings = plan.build(REQS, FEATS, plan.State())
    ops = Counter(a.op for a in actions)
    assert ops["create_issue"] == 4 and ops["add_item"] == 4 and ops["add_sub_issue"] == 2
    assert ops["comment"] == 1  # 13.02 is an experiment item
    assert warnings == []
    first = [a.key for a in actions if a.op == "create_issue"]
    assert first == ["RF", "R13", "13.02", "13.03"]  # each requirement before its features


def test_status_on_create_only():
    actions, _ = plan.build(REQS, FEATS, plan.State())
    status = {a.key: a.value for a in actions if a.op == "set_field" and a.field == "Status"}
    assert status == {"RF": "Todo", "R13": "Todo", "13.02": "Done (experiment)", "13.03": "Todo"}
    st = synced_state()
    st.items["13.03"]["Status"] = "In progress"  # moved by a person
    actions, _ = plan.build(REQS, FEATS, st)
    assert actions == []


def test_fields():
    actions, _ = plan.build(REQS, FEATS, plan.State())
    f = {(a.key, a.field): a.value for a in actions if a.op == "set_field"}
    assert f[("13.02", "Row")] == "13 感知类算子 Perception"
    assert f[("13.02", "Repo")] == "dora" and f[("13.02", "Kind")] == "feature"
    assert f[("13.02", "Basis")] == "built, to move" and f[("13.02", "Feature ID")] == "13.02"
    assert f[("13.03", "Estimate (days)")] == 3 and f[("R13", "Estimate (days)")] == 40
    assert ("RF", "Estimate (days)") not in f and ("R13", "Basis") not in f


def test_synced_state_plans_nothing():
    assert plan.build(REQS, FEATS, synced_state()) == ([], [])


def test_changed_body_is_updated_and_labels_kept():
    st = synced_state()
    old = st.issues["13.03"]
    st.issues["13.03"] = plan.IssueState(old.key, old.repo, old.number, old.id, old.node_id, old.url,
                                         old.title, "old body", ("bug", "row:13"))
    actions, _ = plan.build(REQS, FEATS, st)
    assert [a.op for a in actions] == ["update_issue"]
    assert set(actions[0].labels) == {"bug", "row:13", "kind:feature", "status:new"}


def test_crlf_body_is_not_a_change():
    st = synced_state()
    old = st.issues["R13"]
    st.issues["R13"] = plan.IssueState(old.key, old.repo, old.number, old.id, old.node_id, old.url,
                                       old.title, old.body.replace("\n", "\r\n") + "\r\n", old.labels)
    assert plan.build(REQS, FEATS, st)[0] == []


def test_removed_feature_is_reported_not_touched():
    st = synced_state()
    actions, warnings = plan.build(REQS, [F02], st)
    assert actions == []
    assert warnings == ["13.03: https://github.com/o/dora/issues/11 is not in the workbook; left as it is"]


def test_only_selects_row_or_id_and_pulls_in_the_parent():
    actions, _ = plan.build(REQS, FEATS, plan.State(), only={"13.03"})
    assert [a.key for a in actions if a.op == "create_issue"] == ["R13", "13.03"]
    actions, _ = plan.build(REQS, FEATS, plan.State(), only={"F"})
    assert [a.key for a in actions if a.op == "create_issue"] == ["RF"]


def test_issue_in_wrong_repo_is_an_error():
    st = synced_state()
    old = st.issues["13.03"]
    st.issues["13.03"] = plan.IssueState(old.key, "DORA_NAV", old.number, old.id, old.node_id, old.url,
                                         old.title, old.body, old.labels)
    with pytest.raises(plan.PlanError, match=re.escape("13.03 is in DORA_NAV, the workbook says dora")):
        plan.build(REQS, FEATS, st)


def test_label_comparison_ignores_case():
    st = synced_state()
    old = st.issues["13.03"]
    st.issues["13.03"] = plan.IssueState(old.key, old.repo, old.number, old.id, old.node_id, old.url,
                                         old.title, old.body, ("Row:13", "KIND:feature", "Status:New"))
    assert plan.build(REQS, FEATS, st)[0] == []
    st.issues["13.03"] = plan.IssueState(old.key, old.repo, old.number, old.id, old.node_id, old.url,
                                         old.title, old.body, ("Row:13", "KIND:feature"))
    actions, _ = plan.build(REQS, FEATS, st)
    assert [a.op for a in actions] == ["update_issue"]
    assert sorted(actions[0].labels) == ["KIND:feature", "Row:13", "status:new"]


def test_status_set_when_item_has_none():
    st = synced_state()
    del st.items["13.02"]["Status"]  # crash between add_item and set_field Status
    actions, _ = plan.build(REQS, FEATS, st)
    assert [(a.op, a.key, a.field, a.value) for a in actions] == [
        ("set_field", "13.02", "Status", "Done (experiment)")]


def test_experiment_comment_is_planned_when_missing_on_an_existing_issue():
    st = synced_state()
    st.comments.discard("13.02")  # crash between create_issue and comment
    actions, _ = plan.build(REQS, FEATS, st)
    assert [(a.op, a.key) for a in actions] == [("comment", "13.02")]
    assert render.find_comment_marker(actions[0].body) == "13.02"
    assert actions[0].repo == "dora"
