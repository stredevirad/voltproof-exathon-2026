"""The run guides name the app's buttons and menu items exactly as the app shows them (docs council D-A). Each label
below must appear in the document that quotes it and in the web app's source, so renaming a button without updating
the guides (or the other way round) fails here."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
WEB_SRC = REPO / "app" / "web" / "src"

LABELS = {
    "README.md": [
        "Start guided demo", "How to use", "Show the short tour of the start page", "Upload your data",
        "Upload and preview", "Check the file", "Use my answers and check again", "Analyse this file",
        "Open this dataset", "Delete this upload", "Yes, delete", "Cancel and delete",
        "Uploaded data — not verified by VoltProof",
    ],
    "docs/SETUP_WINDOWS.md": [
        "Start guided demo", "How to use", "Upload your data", "Only one analysis can run at a time",
    ],
    "docs/deliverables/LIVE_DEMO_RUNBOOK.md": [
        "Start guided demo", "Skip the tour", "Outages on this day", "open evidence →", "Generate evidence report",
        "Upload your data", "Upload and preview", "Check the file", "Analyse this file", "Open this dataset",
        "How to use", "Uploaded data — not verified by VoltProof",
    ],
}


def _flat(text: str) -> str:
    """Line breaks inside a sentence (Markdown or JSX source) do not change the words."""
    return " ".join(text.split())


def _web_source() -> str:
    return _flat("\n".join(p.read_text(encoding="utf-8") for p in sorted(WEB_SRC.rglob("*.tsx"))))


@pytest.mark.parametrize("doc", sorted(LABELS))
def test_quoted_labels_exist_in_the_doc_and_in_the_app(doc):
    text = _flat((REPO / doc).read_text(encoding="utf-8"))
    source = _web_source()
    missing_in_doc = [label for label in LABELS[doc] if label not in text]
    missing_in_app = [label for label in LABELS[doc] if label not in source]
    assert not missing_in_doc, f"{doc} no longer quotes: {missing_in_doc}"
    assert not missing_in_app, f"{doc} quotes labels the app does not show: {missing_in_app}"
