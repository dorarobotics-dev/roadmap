import shutil

import fm_sync
from conftest import MAP
from fakes import FakeGh


def run(argv, g):
    out = []
    code = fm_sync.main(argv, gh=g, out=out.append)
    return code, out


def test_sync_dry_run_without_project_plans_everything():
    g = FakeGh()
    code, out = run(["sync"], g)
    assert code == 0 and g.issues == {}
    assert out[-2].startswith("plan: create_issue 145, update_issue 0, comment 9, add_item 145, set_field ")
    assert out[-2].endswith(", add_sub_issue 131")
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
