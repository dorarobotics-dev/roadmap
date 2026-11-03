import pathlib
import sys

TOOLS = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
REQ = TOOLS.parent / "docs" / "requirements"
MAP = REQ / "2026-10-26-feature-map-by-repo.xlsx"
SOURCE = REQ / "具身智能本体中间件_扩展功能_v1.3_withoutbudget.xlsx"
