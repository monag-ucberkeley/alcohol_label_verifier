from app.extract import ABV_RE, NET_RE

def test_regexes_cover_common_formats():
    assert ABV_RE.search("12.5% ABV")
    assert ABV_RE.search("7%")
    assert NET_RE.search("750 mL")
    assert NET_RE.search("12 fl oz")
