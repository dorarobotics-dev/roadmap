"""Read and check the feature map and the original v1.3 requirement workbook."""
import openpyxl

from .model import ROWS, SHEET_REPO, Feature, Requirement

HEADER = ("ID", "Row", "Requirement", "Feature (one PR)", "Package / location", "Status",
          "Existing basis", "Owner", "Issue / PR", "Notes")
STATUSES = ("new", "basis exists", "built, to move")


class WorkbookError(ValueError):
    pass


def _s(value) -> str:
    return "" if value is None else str(value).strip()


def _row(value) -> str:
    s = _s(value)
    return s[:-2] if s.endswith(".0") else s


def _sheets(path, names) -> dict:
    """All rows (as value tuples) of the named sheets; the read-only workbook is closed again."""
    wb = openpyxl.load_workbook(path, read_only=True)
    try:
        return {name: list(wb[name].iter_rows(values_only=True)) for name in names}
    finally:
        wb.close()


def read_features(path) -> list[Feature]:
    sheets = _sheets(path, SHEET_REPO)
    out, seen = [], set()
    for sheet, repo in SHEET_REPO.items():
        rows = sheets[sheet]
        header = tuple(_s(c) for c in rows[0][:len(HEADER)])
        if header != HEADER:
            raise WorkbookError(f"{sheet}: unexpected header {header}")
        for n, r in enumerate(rows[1:], start=2):
            if not any(c is not None for c in r):
                continue
            fid, row, title, status = _s(r[0]), _row(r[1]), _s(r[3]), _s(r[5])
            where = f"{sheet}!row {n}"
            if not fid:
                raise WorkbookError(f"{where}: empty ID")
            if fid in seen:
                raise WorkbookError(f"{where}: duplicate ID {fid}")
            if row not in ROWS:
                raise WorkbookError(f"{where}: unknown row {row}")
            if not fid.startswith(row + "."):
                raise WorkbookError(f"{where}: {fid} is not in row {row}")
            if not title:
                raise WorkbookError(f"{where}: empty feature")
            if status not in STATUSES:
                raise WorkbookError(f"{where}: unknown status {status!r}")
            seen.add(fid)
            out.append(Feature(fid, row, repo, "delivery" if sheet == "delivery" else "feature",
                               title, _s(r[4]), status, _s(r[6]), _s(r[7]), _s(r[8]), _s(r[9])))
    return out


def read_requirements(map_path, source_path) -> list[Requirement]:
    rows = _sheets(map_path, ["Rows"])["Rows"][1:]
    src = _sheets(source_path, ["functions", "delivery"])
    functions = {}
    for r in src["functions"][1:]:
        if r[0] is not None:
            functions[_row(r[0])] = (_s(r[6]), _s(r[7]))
    delivery = {}
    for r in src["delivery"][1:]:
        head = _s(r[0]).split(" ", 1)[0]
        if head in ROWS:
            delivery[head] = _s(r[2])
    out = []
    for r in rows:
        if r[0] is None:
            continue
        row = _row(r[0])
        national, expansion = functions.get(row, ("", ""))
        if row != "F":
            for heading, text in (("国家要求", national), ("扩展功能及参数依据", expansion),
                                  ("量化指标要求", delivery.get(row, ""))):
                if not text:
                    raise WorkbookError(f"row {row}: empty {heading} in the v1.3 workbook")
        out.append(Requirement(row, _s(r[1]), _s(r[2]), national, expansion, delivery.get(row, "")))
    if [q.row for q in out] != list(ROWS):
        raise WorkbookError(f"Rows sheet must list {', '.join(ROWS)} in order, got {[q.row for q in out]}")
    return out
