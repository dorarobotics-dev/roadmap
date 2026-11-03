"""Records read from the feature-map workbooks."""
from dataclasses import dataclass

ROWS = ("F", "13", "14", "15", "16", "17", "18", "19", "20", "21", "22", "23", "24", "25")

# workbook sheet -> GitHub repo in the org
SHEET_REPO = {
    "dora": "dora", "DORA_NAV": "DORA_NAV", "dora-moveit2": "dora-moveit2",
    "dora-studio": "dora-studio", "octos": "octos", "dora-hub": "dora-hub",
    "delivery": "roadmap",
}


@dataclass(frozen=True)
class Requirement:
    row: str
    name: str            # "感知类算子 · Perception operators"
    acceptance_en: str   # Rows sheet, condensed English
    national_zh: str     # v1.3 functions sheet: 国家要求 ("" for F)
    expansion_zh: str    # v1.3 functions sheet: 扩展功能及参数依据
    acceptance_zh: str   # v1.3 delivery sheet: 量化指标要求

    @property
    def key(self) -> str:
        return f"R{self.row}"


@dataclass(frozen=True)
class Feature:
    id: str
    row: str
    repo: str
    kind: str            # "feature" or "delivery"
    title: str
    location: str
    status: str          # "new", "basis exists", "built, to move"
    basis: str
    owner: str
    issue: str
    notes: str

    @property
    def key(self) -> str:
        return self.id
