from tests.support.claims import forbidden_hits


def test_forbidden_phrases_are_detected():
    for bad in ["Compensation due: Rs 500", "you are entitled to a refund", "this proves a fault", "a transformer fault",
                "Feeder fault at 18:27", "p = 0", "p=0.0"]:
        assert forbidden_hits(bad), bad


def test_internal_references_are_detected():
    for bad in ["see the review ledger", "as the Idea Book said", "idea-book D5", "MASTER_PROMPT.md", "master prompt",
                "docs/private/evidence", r"docs\private\evidence"]:
        assert forbidden_hits(bad), bad


def test_ids_are_not_mistaken_for_internal_references():
    for ok in ["fixture F01", "VERIFICATION_LOG X31", "decision D-030", "check G1a", "private by default"]:
        assert not forbidden_hits(ok), ok


def test_allowed_wording_passes():
    for ok in ["The service improves", "not proof of a common cause", "potential shared supply event",
               "may warrant review", "p = 0.05", "none of 20 shifted variants reached the observed count"]:
        assert not forbidden_hits(ok), ok
