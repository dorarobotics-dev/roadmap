from fmsync import render
from fmsync.model import Feature, Requirement

Q = Requirement("13", "感知类算子 · Perception operators", "Fusion: two sensors.", "覆盖多模态", "扩展感知", "融合算子")
F = Feature("13.02", "13", "dora", "feature", "frame_transform node", "nodes/frame-transform",
            "built, to move", "Reference op", "", "", "a | b")
D = Feature("13.15", "13", "roadmap", "delivery", "Fusion record", "", "new", "", "", "", "")


def test_markers_round_trip():
    body = render.requirement_body(Q)
    assert body.endswith("<!-- fm:R13 -->")
    assert render.find_marker(body) == "R13"
    assert render.find_marker(render.feature_body(F, Q.name)) == "13.02"
    assert render.find_marker("no marker here") is None


def test_requirement_title_and_body():
    assert render.requirement_title(Q) == "[R13] 感知类算子 · Perception operators"
    body = render.requirement_body(Q)
    for text in ("Fusion: two sensors.", "## 国家要求（必须完成）", "覆盖多模态", "## 扩展功能及参数依据",
                 "## 量化指标要求", "融合算子", "## Effort (feasibility report)", "Row total 40"):
        assert text in body


def test_requirement_f_has_no_empty_chinese_sections():
    body = render.requirement_body(Requirement("F", "基础 · Foundation", "Prerequisites.", "", "", ""))
    assert "国家要求" not in body and "量化指标要求" not in body


def test_feature_title_body_and_labels():
    assert render.feature_title(F) == "[13.02] frame_transform node"
    body = render.feature_body(F, Q.name)
    assert "one PR into `dora`" in body
    assert "| Package / location | nodes/frame-transform |" in body
    assert "a \\| b" in body
    assert "13 · 感知类算子 · Perception operators (parent issue)" in body
    assert render.labels_for_feature(F) == ("row:13", "kind:feature", "status:built-to-move")
    assert render.labels_for_requirement(Q) == ("row:13", "kind:requirement")
    assert "Deliverable **13.15**" in render.feature_body(D, Q.name)


def test_experiment_comment():
    text = render.experiment_comment("13.02")
    assert text.startswith("**Experiment (Done (experiment)).**")
    assert "nodes/frame-transform" in text and "feasibility.md" in text
    # figures from feasibility.md section 1 (cargo test totals at f70c3de9c)
    assert ("Rust 1336 (dora-message, dora-core, dora-transform, dora-cli, dora-node-api-c) "
            "and Python 254 tests pass") in text
    assert "Rust 800" not in text
    assert text.endswith("<!-- fm-comment:13.02 -->")
    assert render.find_comment_marker(text) == "13.02"
    assert render.find_marker(text) is None  # not mistaken for an issue marker
    assert render.find_comment_marker("plain comment") is None


def test_normalize_ignores_crlf_and_trailing_space():
    assert render.normalize("a \r\nb\n") == render.normalize("a\nb")
