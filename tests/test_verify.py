from backend.pipeline.verify import QuoteStats, find_exact, find_fuzzy, is_verbatim, verify_quote

TEXT = "Approved — let’s go with Ledgerly from 6 July.\n\nKeep  Helen in the loop on spend."


def test_exact_match_returns_original_span():
    hit = find_exact("approved - let's go with ledgerly", TEXT)  # model normalised dash, apostrophe and case
    assert hit == "Approved — let’s go with Ledgerly" and hit in TEXT


def test_whitespace_differences_are_tolerated():
    assert find_exact("Keep Helen in the loop", TEXT) == "Keep  Helen in the loop"


def test_fuzzy_snaps_to_whole_words():
    hit = find_fuzzy("let's go with Ledgerly from 6 Jully", TEXT)
    assert hit is not None and hit in TEXT and hit.endswith("July")


def test_verify_reanchors_and_drops():
    texts = {"<a>": ("nothing relevant here", ""), "<b>": (TEXT, "")}
    st = QuoteStats()
    q = verify_quote("<a>", "Keep Helen in the loop on spend", "approval", texts, st)
    assert q.verified and q.message_id == "<b>" and is_verbatim(q.quote, *texts["<b>"])
    q = verify_quote("<b>", "We will switch to Stripe next week", "decision", texts, st)
    assert not q.verified
    assert st.as_dict() == {"quotes_total": 2, "quotes_exact": 0, "quotes_snapped": 1, "quotes_reanchored": 1,
                            "quotes_dropped": 1}


def test_forwarded_region_is_searched():
    texts = {"<f>": ("FYI see below.", "the batch runs thursday this time.")}
    q = verify_quote("<f>", "the batch runs Thursday", "recap", texts, QuoteStats())
    assert q.verified and q.quote == "the batch runs thursday"
