"""Every printed page of an evidence report carries the disclaimer and the data source (the PDF page footer), and
the synthetic set's footer never carries the Prayas attribution."""

from __future__ import annotations

from app.api.report import DISCLAIMER, _footer
from app.api.service import ATTRIBUTION, SYNTHETIC_ATTRIBUTION


def _data(synthetic: bool, attribution: str) -> dict:
    return {"synthetic": synthetic, "disclaimer": DISCLAIMER, "provenance": {"attribution": attribution}}


def test_real_report_pages_carry_disclaimer_and_attribution():
    footer = _footer(_data(False, ATTRIBUTION))
    assert DISCLAIMER in footer
    assert "Data: Prayas (Energy Group), Electricity Supply Monitoring Initiative (ESMI), CC0 1.0." in footer
    assert 'class="pageNumber"' in footer and 'class="totalPages"' in footer
    assert "SYNTHETIC" not in footer


def test_synthetic_report_pages_carry_disclaimer_and_label_but_no_prayas_attribution():
    footer = _footer(_data(True, SYNTHETIC_ATTRIBUTION))
    assert DISCLAIMER in footer
    assert "<b>SYNTHETIC DEMO DATA, not ESMI data</b>" in footer
    assert "Prayas" not in footer and "CC0" not in footer


def test_footer_text_is_escaped():
    footer = _footer(_data(False, 'Data: <img src=x onerror="alert(1)"> & co'))
    assert "<img" not in footer and "&lt;img" in footer and "&amp; co" in footer
