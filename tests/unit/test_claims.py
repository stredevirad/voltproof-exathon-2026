from tests.support.claims import forbidden_hits


def test_forbidden_phrases_are_detected():
    for bad in ["Compensation due: Rs 500", "you are entitled to a refund", "this proves a fault", "a transformer fault",
                "Feeder fault at 18:27", "p = 0", "p=0.0"]:
        assert forbidden_hits(bad), bad


def test_allowed_wording_passes():
    for ok in ["The service improves", "not proof of a common cause", "potential shared supply event",
               "may warrant review", "p = 0.05", "none of 20 shifted variants reached the observed count"]:
        assert not forbidden_hits(ok), ok
