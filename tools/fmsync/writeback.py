"""Write issue URLs into the `Issue / PR` column (I) of the feature sheets; nothing else."""
import openpyxl

from .model import SHEET_REPO

ISSUE_COL = 8  # zero-based index of column I


def write_issue_urls(path, urls: dict) -> int:
    wb = openpyxl.load_workbook(path)
    changed = 0
    for sheet in SHEET_REPO:
        for row in wb[sheet].iter_rows(min_row=2):
            fid = str(row[0].value or "").strip()
            if fid in urls and row[ISSUE_COL].value != urls[fid]:
                row[ISSUE_COL].value = urls[fid]
                changed += 1
    if changed:
        wb.save(path)
    return changed
