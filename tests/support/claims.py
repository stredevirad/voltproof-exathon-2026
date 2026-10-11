"""Claims-vocabulary guard (master prompt Section 12; DECISIONS D-022): phrases VoltProof must never print."""

import re

FORBIDDEN = [
    r"compensation\s+due", r"entitled\s+to", r"\bproves?\b", r"\bproven\b", r"transformer\s+fault", r"feeder\s+fault",
    r"proven\s+common\s+cause", r"\bp\s*=\s*0(\.0+)?\b(?!\.\d*[1-9])",
]
_PATTERNS = [re.compile(p, re.IGNORECASE) for p in FORBIDDEN]


def forbidden_hits(text: str) -> list[str]:
    """Return every forbidden phrase found (word-boundary aware: 'improves' does not match 'proves')."""
    hits = []
    for pat in _PATTERNS:
        for m in pat.finditer(text):
            s = max(0, m.start() - 40)
            hits.append(f"{m.group(0)!r} in ...{text[s:m.end() + 40]!r}...")
    return hits
