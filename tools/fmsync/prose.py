"""Hand-written issue prose from draft files. Fills only empty prose areas; never rewrites prose."""
import pathlib
import re
from dataclasses import dataclass

from . import render

HEADINGS = ("Summary", "Use case / Why", "Proposed expected behavior", "Proposed API / Design")
ID_RE = re.compile(r"^ {0,3}# (\S+)\s*$")
H2_RE = re.compile(r"^ {0,3}## (.+?)\s*$")
H1_RE = re.compile(r"^ {0,3}# ")
FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")


class ProseError(ValueError):
    pass


@dataclass(frozen=True)
class ProseAction:
    op: str          # "write" or "skip"
    key: str
    reason: str = ""
    body: str = ""


def _fence(line, open_fence):
    """The fence state after `line`: None (outside) or (char, length) of the open fence."""
    m = FENCE_RE.match(line)
    if not m:
        return open_fence
    run, rest = m.groups()
    if open_fence is None:
        return None if (run[0] == "`" and "`" in rest) else (run[0], len(run))
    if run[0] == open_fence[0] and len(run) >= open_fence[1] and not rest.strip():
        return None
    return open_fence


def _sections(path):
    """[(key, lines)] for the `# ID` sections of one file. Headings inside ``` fences do not count."""
    sections, fence = [], None
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        was = fence
        fence = _fence(line, fence)
        inside = was is not None or fence is not None
        m = None if inside else ID_RE.match(line)
        if not inside and not m and H1_RE.match(line):
            raise ProseError(f"{path.name}:{n}: `# ` heading must be exactly `# <ID>`")
        if m:
            sections.append((m.group(1), []))
        elif sections:
            sections[-1][1].append(line)
        elif line.strip():
            raise ProseError(f"{path.name}:{n}: text before the first `# ID` heading")
    if fence:
        raise ProseError(f"{path.name}: unclosed code fence")
    return sections


def _headings(lines):
    out, fence = [], None
    for line in lines:
        was = fence
        fence = _fence(line, fence)
        if was is None and fence is None:
            m = H2_RE.match(line)
            if m:
                out.append(m.group(1))
    return out


def read_drafts(directory, known) -> dict:
    """{key: prose} from every *.md in directory. Refuses anything that does not fit the layout."""
    files = sorted(pathlib.Path(directory).glob("*.md"))
    if not files:
        raise ProseError(f"{directory}: no .md draft files")
    drafts, where = {}, {}
    for path in files:
        for key, lines in _sections(path):
            loc = f"{path.name} # {key}"
            if key not in known:
                raise ProseError(f"{loc}: {key} is not in the workbook")
            if key in drafts:
                raise ProseError(f"{loc}: {key} also in {where[key]}")
            heads = _headings(lines)
            if heads != list(HEADINGS):
                raise ProseError(f"{loc}: headings {heads}, expected {list(HEADINGS)}")
            text = "\n".join(lines).strip()
            if not text.startswith("## Summary"):
                raise ProseError(f"{loc}: must start with ## Summary")
            if "<!-- fm" in text:
                raise ProseError(f"{loc}: contains fm marker text")
            drafts[key], where[key] = text, path.name
    return drafts


def build(drafts, state, only=None) -> list:
    out = []
    for key in sorted(drafts):
        if only and key not in only:
            continue
        s = state.issues.get(key)
        if s is None:
            out.append(ProseAction("skip", key, "no issue yet; run sync first"))
            continue
        prose, block = render.split(s.body, f"{s.repo}#{s.number} ({key})")
        if prose is None:
            out.append(ProseAction("skip", key, "old layout; run sync first"))
        elif prose.strip():
            out.append(ProseAction("skip", key, "already has prose"))
        else:
            out.append(ProseAction("write", key, s.url, render.compose(drafts[key], block)))
    return out


def execute(gh, state, actions, log=print) -> None:
    for a in actions:
        if a.op == "write":
            s = state.issues[a.key]
            gh.update_issue(s.repo, s.number, s.title, a.body, s.labels)
            log(f"wrote {a.key} {s.url}")
