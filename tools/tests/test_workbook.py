import re
import shutil
from collections import Counter

import openpyxl
import pytest

from conftest import MAP, SOURCE
from fmsync import workbook
from fmsync.model import ROWS


def test_features_per_repo():
    feats = workbook.read_features(MAP)
    assert Counter(f.repo for f in feats) == {
        "dora": 43, "DORA_NAV": 23, "dora-moveit2": 9, "dora-studio": 4,
        "octos": 4, "dora-hub": 33, "roadmap": 16}
    assert len({f.id for f in feats}) == 132


def test_feature_fields():
    f = {x.id: x for x in workbook.read_features(MAP)}
    assert f["F.04"].repo == "dora" and f["F.04"].row == "F" and f["F.04"].kind == "feature"
    assert f["F.04"].status == "built, to move"
    assert f["F.05"].status == "basis exists"
    assert f["13.02"].row == "13"
    assert f["F.12"].kind == "delivery" and f["F.12"].repo == "roadmap"
    assert f["F.20"].title == "Expose Node.id in the Python node API"


def test_requirements():
    reqs = workbook.read_requirements(MAP, SOURCE)
    assert [q.row for q in reqs] == list(ROWS)
    q = {x.row: x for x in reqs}
    assert q["13"].name == "感知类算子 · Perception operators"
    assert q["13"].national_zh.startswith("覆盖多模态传感器融合")
    assert q["13"].expansion_zh.startswith("在既有导航与操作算子集的基础上扩展感知类算子")
    assert q["13"].acceptance_zh.startswith("融合算子接入不少于两类传感器")
    assert q["13"].acceptance_en.startswith("Fusion:")
    assert q["F"].national_zh == "" and q["F"].acceptance_zh == ""
    assert q["F"].key == "RF" and q["25"].key == "R25"


def _doctored(tmp_path, sheet, cell, value, source=MAP):
    path = tmp_path / source.name
    shutil.copy(source, path)
    wb = openpyxl.load_workbook(path)
    wb[sheet][cell] = value
    wb.save(path)
    return path


@pytest.mark.parametrize("sheet,cell,value,message", [
    ("dora", "A3", "F.01", "duplicate ID F.01"),
    ("dora", "B2", "99", "unknown row 99"),
    ("dora", "F2", "maybe", "unknown status 'maybe'"),
    ("dora", "D2", None, "empty feature"),
    ("dora", "A2", "13.01", "13.01 is not in row F"),
    ("octos", "A1", "Id", "unexpected header"),
])
def test_bad_workbook_is_refused(tmp_path, sheet, cell, value, message):
    with pytest.raises(workbook.WorkbookError, match=re.escape(message)):
        workbook.read_features(_doctored(tmp_path, sheet, cell, value))


@pytest.mark.parametrize("sheet,cell,message", [
    ("functions", "G2", "row 13: empty 国家要求 in the v1.3 workbook"),
    ("functions", "H3", "row 14: empty 扩展功能及参数依据 in the v1.3 workbook"),
    ("delivery", "C4", "row 14: empty 量化指标要求 in the v1.3 workbook"),
])
def test_empty_v13_text_is_refused(tmp_path, sheet, cell, message):
    source = _doctored(tmp_path, sheet, cell, None, source=SOURCE)
    with pytest.raises(workbook.WorkbookError, match=re.escape(message)):
        workbook.read_requirements(MAP, source)
