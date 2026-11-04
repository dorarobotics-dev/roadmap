import pytest

from fakes import FakeGh, draft_section
from fmsync import plan, prose, render
from test_plan import F02, FEATS, Q13, REQS, issue, synced_state

KNOWN = {q.key for q in REQS} | {f.key for f in FEATS}


def write(tmp_path, text, name="13.md"):
    (tmp_path / name).write_text(text, encoding="utf-8")
    return tmp_path


def test_read_drafts_ignores_headings_in_code_fences(tmp_path):
    d = prose.read_drafts(write(tmp_path, draft_section("R13") + draft_section("13.02")), KNOWN)
    assert set(d) == {"R13", "13.02"}
    assert d["13.02"].startswith("## Summary\n\nSummary of 13.02.")
    assert "# inputs" in d["13.02"] and d["13.02"].endswith("```")


@pytest.mark.parametrize("text, message", [
    (draft_section("13.99"), "13.99 is not in the workbook"),
    (draft_section("13.02") + draft_section("13.02"), "13.02 also in 13.md"),
    (draft_section("13.02").replace("## Use case / Why", "## Why"), "headings"),
    (draft_section("13.02") + "\n## Extra\n", "headings"),
    (draft_section("13.02").replace("## Summary", "Lead.\n\n## Summary"), "must start with ## Summary"),
    (draft_section("13.02", "<!-- fm:end -->"), "fm marker text"),
    ("Intro.\n" + draft_section("13.02"), "before the first"),
    (draft_section("13.02") + "```\n", "unclosed"),
])
def test_read_drafts_refuses(tmp_path, text, message):
    with pytest.raises(prose.ProseError, match=message):
        prose.read_drafts(write(tmp_path, text), KNOWN)


def test_read_drafts_refuses_an_empty_directory(tmp_path):
    with pytest.raises(prose.ProseError, match="no .md draft files"):
        prose.read_drafts(tmp_path, KNOWN)


def test_read_drafts_refuses_an_id_in_two_files(tmp_path):
    write(tmp_path, draft_section("13.02"), "a.md")
    write(tmp_path, draft_section("13.02"), "b.md")
    with pytest.raises(prose.ProseError, match="13.02 also in a.md"):
        prose.read_drafts(tmp_path, KNOWN)


def test_build_writes_only_empty_prose_areas():
    st = synced_state()
    mine = st.issues["13.03"]
    st.issues["13.03"] = issue("13.03", "dora", mine.title, render.compose("## Summary\n\nMine.", mine.body),
                               mine.labels, mine.number)
    req = st.issues["R13"]
    st.issues["R13"] = issue("R13", "roadmap", req.title, "old <!-- fm:R13 -->", req.labels, req.number)
    drafts = {"RF": "## Summary\n\nA.", "R13": "x", "13.02": "## Summary\n\nB.", "13.03": "y"}
    acts = {a.key: a for a in prose.build(drafts, st)}
    assert acts["13.02"].op == "write"
    assert acts["13.02"].body == render.compose("## Summary\n\nB.", st.issues["13.02"].body)
    assert acts["RF"].op == "write"
    assert (acts["13.03"].op, acts["13.03"].reason) == ("skip", "already has prose")
    assert (acts["R13"].op, acts["R13"].reason) == ("skip", "old layout; run sync first")
    assert [a.key for a in prose.build(drafts, st, only={"13.02"})] == ["13.02"]


def test_build_skips_a_key_without_an_issue():
    [a] = prose.build({"13.02": "## Summary\n\nB."}, plan.State())
    assert (a.op, a.reason) == ("skip", "no issue yet; run sync first")


def test_execute_keeps_title_and_labels():
    g = FakeGh()
    s = g.create_issue("dora", "T", render.feature_body(F02, Q13.name), ("row:13", "bug"), "13.02")
    st = plan.State(issues={"13.02": s})
    prose.execute(g, st, prose.build({"13.02": "## Summary\n\nB."}, st), log=lambda m: None)
    new = g.issues[("dora", s.number)]
    assert new.title == "T" and new.labels == ("row:13", "bug")
    assert new.body == render.compose("## Summary\n\nB.", render.feature_body(F02, Q13.name))


def test_read_drafts_tilde_fence(tmp_path):
    text = draft_section("13.02").replace("```yaml", "~~~yaml").replace("\n```\n", "\n~~~\n")
    assert "# inputs" in prose.read_drafts(write(tmp_path, text), KNOWN)["13.02"]


def test_read_drafts_long_fence_holds_short_fence(tmp_path):
    text = draft_section("13.02").replace("```yaml\n# inputs\n## not a heading\n```", "````\n```\n# x\n## y\n````")
    assert "# x" in prose.read_drafts(write(tmp_path, text), KNOWN)["13.02"]


def test_read_drafts_indented_headings_and_bad_h1(tmp_path):
    ok = draft_section("13.02").replace("## Summary", "  ## Summary").replace("# 13.02", "  # 13.02")
    assert set(prose.read_drafts(write(tmp_path, ok), KNOWN)) == {"13.02"}
    with pytest.raises(prose.ProseError, match=r"13.md:\d+: `# ` heading must be exactly `# <ID>`"):
        prose.read_drafts(write(tmp_path, draft_section("13.02", "# R13 Navigation")), KNOWN)


def test_marker_like_prose_is_refused_not_duplicated():
    g = FakeGh()
    st = synced_state()
    for s in st.issues.values():
        g.issues[(s.repo, s.number)] = s
    s = st.issues["13.02"]
    _, block = render.split(s.body)
    g.issues[(s.repo, s.number)] = s.__class__(**{**s.__dict__, "body": "Uses `<!-- fm:ID -->` markers.\n\n" + block})
    from fmsync.apply import load_state
    loaded = load_state(g, None, repos=("roadmap", "dora"))
    assert "ID" not in loaded.issues and "13.02" in loaded.issues
    with pytest.raises(render.LayoutError, match="13.02"):
        plan.build(REQS, FEATS, loaded)
