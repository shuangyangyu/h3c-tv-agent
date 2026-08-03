from h3c_tv_agent.models import parse_want


def test_parse_want_plain():
    assert parse_want("ON") == "ON"
    assert parse_want("off") == "OFF"
    assert parse_want(b"ON") == "ON"


def test_parse_want_json():
    assert parse_want('{"state":"ON"}') == "ON"
    assert parse_want('{"state":"off"}') == "OFF"


def test_parse_want_bad():
    assert parse_want("maybe") is None
    assert parse_want("{") is None
