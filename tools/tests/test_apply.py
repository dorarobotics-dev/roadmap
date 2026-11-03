from conftest import MAP, SOURCE
from fakes import FakeGh
from fmsync import apply, plan, workbook
from fmsync.data import FIELDS, LABELS, PROJECT_TITLE, REPOS, STATUS_OPTIONS, VIEWS


def test_setup_dry_run_changes_nothing():
    g = FakeGh()
    log = []
    apply.setup(g, apply=False, log=log.append)
    assert g.project is None and g.repo_labels == {}
    assert f"project {PROJECT_TITLE!r}" in log
    assert sum(1 for line in log if line.startswith("label ")) == len(REPOS) * len(LABELS)


def test_setup_apply_creates_everything_and_is_idempotent():
    g = FakeGh()
    apply.setup(g, apply=True, log=lambda s: None)
    assert all(g.repo_labels[r] == set(LABELS) for r in REPOS)
    assert list(g.fields["Status"]["options"]) == list(STATUS_OPTIONS)
    assert set(FIELDS) <= set(g.fields)
    assert list(g.view_ids) == [name for name, _, _ in VIEWS]
    assert g.view_filters[g.view_ids["Row 13"]] == 'row:"13 感知类算子 Perception"'
    log = []
    apply.setup(g, apply=True, log=log.append)
    assert log == []


def test_full_sync_then_nothing_to_do():
    g = FakeGh()
    apply.setup(g, apply=True, log=lambda s: None)
    reqs, feats = workbook.read_requirements(MAP, SOURCE), workbook.read_features(MAP)
    state = apply.load_state(g, g.project)
    actions, warnings = plan.build(reqs, feats, state)
    assert warnings == []
    apply.execute(g, g.project, actions, state, log=lambda s: None)
    assert len(g.issues) == 14 + 131
    assert len(g.comments) == 9
    roadmap_r13 = next(s for s in g.issues.values() if s.key == "R13")
    assert len(g.subs[("roadmap", roadmap_r13.number)]) == sum(1 for f in feats if f.row == "13")
    again, _ = plan.build(reqs, feats, apply.load_state(g, g.project))
    assert again == []


def test_load_state_refuses_a_marker_on_two_issues():
    g = FakeGh()
    g.create_issue("roadmap", "a", "x <!-- fm:R13 -->", (), "R13")
    g.create_issue("dora", "b", "y <!-- fm:R13 -->", (), "R13")
    try:
        apply.load_state(g, None)
    except ValueError as e:
        assert "R13" in str(e)
    else:
        raise AssertionError("expected ValueError")


def test_load_state_reads_comment_markers_of_experiment_issues_only():
    from fmsync import render
    g = FakeGh()
    s02 = g.create_issue("dora", "a", "x <!-- fm:13.02 -->", (), "13.02")
    g.create_issue("dora", "b", "y <!-- fm:13.03 -->", (), "13.03")
    assert apply.load_state(g, None).comments == set()
    g.comment("dora", s02.number, "unrelated")
    assert apply.load_state(g, None).comments == set()
    g.comment("dora", s02.number, render.experiment_comment("13.02"))
    assert apply.load_state(g, None).comments == {"13.02"}
    asked = {c[1:] for c in g.calls if c[0] == "comment_markers"}
    assert asked == {("dora", s02.number)}


def test_rerun_after_a_crash_finishes_status_and_comment_once():
    g = FakeGh()
    apply.setup(g, apply=True, log=lambda s: None)
    reqs, feats = workbook.read_requirements(MAP, SOURCE), workbook.read_features(MAP)
    state = apply.load_state(g, g.project)
    apply.execute(g, g.project, plan.build(reqs, feats, state, only={"13.02"})[0], state, log=lambda s: None)
    s02 = next(s for s in g.issues.values() if s.key == "13.02")
    g.comments.clear()                                    # crashed before the comment ...
    del g.items[s02.node_id]["fields"]["Status"]          # ... and before Status was set
    state = apply.load_state(g, g.project)
    actions, _ = plan.build(reqs, feats, state, only={"13.02"})
    assert [(a.op, a.key, a.field) for a in actions] == [("comment", "13.02", ""), ("set_field", "13.02", "Status")]
    apply.execute(g, g.project, actions, state, log=lambda s: None)
    assert len(g.comments) == 1
    assert g.items[s02.node_id]["fields"]["Status"] == "Done (experiment)"
    assert plan.build(reqs, feats, apply.load_state(g, g.project), only={"13.02"})[0] == []
