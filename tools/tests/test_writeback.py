import shutil

import openpyxl

from conftest import MAP
from fmsync import writeback


def test_writes_only_the_issue_column(tmp_path):
    path = tmp_path / "map.xlsx"
    shutil.copy(MAP, path)
    urls = {"F.04": "https://github.com/dorarobotics-dev/dora/issues/4",
            "F.12": "https://github.com/dorarobotics-dev/roadmap/issues/9"}
    assert writeback.write_issue_urls(path, urls) == 2
    assert writeback.write_issue_urls(path, urls) == 0
    wb = openpyxl.load_workbook(path)
    dora = {r[0].value: r for r in wb["dora"].iter_rows(min_row=2)}
    assert dora["F.04"][8].value == urls["F.04"]
    assert dora["F.04"][3].value.startswith("dora validate checks")
    assert wb["Summary"]["D2"].value == "=COUNTA(dora!$A:$A)-1"
    delivery = {r[0].value: r for r in wb["delivery"].iter_rows(min_row=2)}
    assert delivery["F.12"][8].value == urls["F.12"]
