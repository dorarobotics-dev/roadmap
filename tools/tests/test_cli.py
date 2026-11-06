import shutil

import fm_sync
from conftest import MAP
from fakes import FakeGh, draft_section


def run(argv, g):
    out = []
    code = fm_sync.main(argv, gh=g, out=out.append)
    return code, out


def test_sync_dry_run_without_project_plans_everything():
    g = FakeGh()
    code, out = run(["sync"], g)
    assert code == 0 and g.issues == {}
    assert out[-2].startswith("plan: create_issue 147, update_issue 0, comment 9, add_item 147, set_field ")
    assert out[-2].endswith(", add_sub_issue 133")
    assert out[-1] == "dry run: nothing changed (add --apply)"


def test_sync_apply_needs_a_project():
    code, out = run(["sync", "--apply"], FakeGh())
    assert code == 1 and out[-1] == "no project: run `fm_sync.py setup --apply` first"


def test_setup_then_sync_then_idempotent():
    g = FakeGh()
    assert run(["setup", "--apply"], g)[0] == 0
    assert run(["sync", "--apply", "--only", "F"], g)[0] == 0
    assert {s.key for s in g.issues.values()} == {"RF"} | {f"F.{n:02d}" for n in range(1, 21)}
    assert run(["sync", "--apply"], g)[0] == 0
    code, out = run(["sync"], g)
    assert out[-2] == ("plan: create_issue 0, update_issue 0, comment 0, add_item 0, set_field 0, "
                       "add_sub_issue 0")


def test_writeback(tmp_path):
    path = tmp_path / "map.xlsx"
    shutil.copy(MAP, path)
    g = FakeGh()
    run(["setup", "--apply"], g)
    run(["sync", "--apply", "--only", "F.04", "--map", str(path)], g)
    code, out = run(["writeback", "--map", str(path)], g)
    assert out[-1] == "dry run: 2 issue URLs to write (add --apply)"  # RF and F.04; RF has no workbook cell
    code, out = run(["writeback", "--apply", "--map", str(path)], g)
    assert out[-1] == "1 cells written; recalculate the workbook before committing"


def test_setup_dry_run_creates_nothing():
    g = FakeGh()
    code, out = run(["setup"], g)
    assert code == 0 and out[-1] == "dry run: nothing changed (add --apply)"
    assert g.repo_labels == {} and g.project is None and g.fields == {} and g.view_ids == {}
    g.create_project("Embodied middleware v1.3")
    fields, views = dict(g.fields), dict(g.view_ids)
    code, out = run(["setup"], g)
    assert g.repo_labels == {} and g.fields == fields and g.view_ids == views and g.view_filters == {}
    assert any(line.startswith("field Row") for line in out) and any(line.startswith("view Row 13") for line in out)


def test_only_with_spaces_is_parsed():
    g = FakeGh()
    code, out = run(["sync", "--only", " F , 13.02 "], g)
    created = [line.split()[1] for line in out if line.startswith("create_issue")]
    assert created[0] == "RF" and created[-2:] == ["R13", "13.02"]
    assert sorted(created[1:-2]) == [f"F.{n:02d}" for n in range(1, 21)]


def test_orphan_issues_are_warned_about():
    g = FakeGh()
    run(["setup", "--apply"], g)
    g.create_issue("dora", "[F.99] gone", "old <!-- fm:F.99 -->", (), "F.99")
    code, out = run(["sync"], g)
    assert code == 0
    assert "WARNING F.99: https://github.com/dorarobotics-dev/dora/issues/1 is not in the workbook; left as it is" in out


def test_prose_dry_run_apply_and_skip(tmp_path):
    g = FakeGh()
    run(["setup", "--apply"], g)
    run(["sync", "--apply", "--only", "F"], g)
    (tmp_path / "F.md").write_text(draft_section("RF") + draft_section("F.01"), encoding="utf-8")
    code, out = run(["prose", str(tmp_path)], g)
    assert code == 0 and out[0].startswith("WARNING no draft for 145:")
    assert out[-2] == "prose: write 2, skip 0" and out[-1] == "dry run: nothing changed (add --apply)"
    assert all(s.body.startswith("<!-- fm:begin -->") for s in g.issues.values())
    assert run(["prose", str(tmp_path), "--apply"], g)[0] == 0
    rf = next(s for s in g.issues.values() if s.key == "RF")
    assert rf.body.startswith("## Summary\n\nSummary of RF.")
    assert run(["prose", str(tmp_path)], g)[1][-2] == "prose: write 0, skip 2"
    assert run(["sync", "--only", "F"], g)[1][-2] == ("plan: create_issue 0, update_issue 0, comment 0, "
                                                       "add_item 0, set_field 0, add_sub_issue 0")


def test_prose_refuses_bad_drafts_and_needs_a_directory(tmp_path):
    (tmp_path / "F.md").write_text(draft_section("F.99"), encoding="utf-8")
    code, out = run(["prose", str(tmp_path)], FakeGh())
    assert code == 1 and out[-1] == "ERROR F.md # F.99: F.99 is not in the workbook"
    code, out = run(["prose"], FakeGh())
    assert code == 2 and out[-1] == "prose needs a drafts directory"


def test_prose_only_warns_about_entries_without_a_draft(tmp_path):
    g = FakeGh()
    run(["setup", "--apply"], g)
    (tmp_path / "d.md").write_text(draft_section("F.04"), encoding="utf-8")
    code, out = run(["prose", str(tmp_path), "--only", "F.04,13"], g)
    assert "WARNING --only entries with no draft: 13" in out


def test_sync_reports_a_broken_layout():
    g = FakeGh()
    run(["setup", "--apply"], g)
    run(["sync", "--apply", "--only", "F.04"], g)
    (key, s), = [(k, v) for k, v in g.issues.items() if v.key == "F.04"]
    g.issues[key] = s.__class__(**{**s.__dict__, "body": s.body + "\nstray"})
    before = dict(g.issues)
    n = len(g.calls)
    code, out = run(["sync", "--apply", "--only", "F.04"], g)
    assert code == 1 and any(l.startswith("ERROR ") and "F.04" in l for l in out)
    assert g.issues == before and not [c for c in g.calls[n:] if c[0] != "comment_markers"]
