import src.public_demo as public_demo


def setup_function() -> None:
    """
    Start every test with empty public-demo state.
    """

    public_demo.clear_public_demo_state()


def teardown_function() -> None:
    """
    Prevent test state from leaking into later tests.
    """

    public_demo.clear_public_demo_state()


def test_rate_limit_allows_requests_below_limit(
    monkeypatch,
) -> None:
    """
    Requests below the configured limit should be allowed.
    """

    monkeypatch.setattr(
        public_demo,
        "RATE_LIMIT_REQUESTS",
        3,
    )

    monkeypatch.setattr(
        public_demo,
        "RATE_LIMIT_WINDOW_SECONDS",
        60,
    )

    allowed_1, retry_1 = (
        public_demo.check_rate_limit(
            "client-a"
        )
    )

    allowed_2, retry_2 = (
        public_demo.check_rate_limit(
            "client-a"
        )
    )

    allowed_3, retry_3 = (
        public_demo.check_rate_limit(
            "client-a"
        )
    )

    assert allowed_1 is True
    assert retry_1 == 0

    assert allowed_2 is True
    assert retry_2 == 0

    assert allowed_3 is True
    assert retry_3 == 0


def test_rate_limit_blocks_request_over_limit(
    monkeypatch,
) -> None:
    """
    A request above the configured limit should be rejected.
    """

    monkeypatch.setattr(
        public_demo,
        "RATE_LIMIT_REQUESTS",
        2,
    )

    monkeypatch.setattr(
        public_demo,
        "RATE_LIMIT_WINDOW_SECONDS",
        60,
    )

    public_demo.check_rate_limit(
        "client-a"
    )

    public_demo.check_rate_limit(
        "client-a"
    )

    allowed, retry_after = (
        public_demo.check_rate_limit(
            "client-a"
        )
    )

    assert allowed is False
    assert retry_after >= 1


def test_rate_limit_is_separate_per_client(
    monkeypatch,
) -> None:
    """
    One client's limit should not block another client.
    """

    monkeypatch.setattr(
        public_demo,
        "RATE_LIMIT_REQUESTS",
        1,
    )

    monkeypatch.setattr(
        public_demo,
        "RATE_LIMIT_WINDOW_SECONDS",
        60,
    )

    allowed_a, _ = (
        public_demo.check_rate_limit(
            "client-a"
        )
    )

    blocked_a, _ = (
        public_demo.check_rate_limit(
            "client-a"
        )
    )

    allowed_b, _ = (
        public_demo.check_rate_limit(
            "client-b"
        )
    )

    assert allowed_a is True
    assert blocked_a is False
    assert allowed_b is True


def test_question_normalization() -> None:
    """
    Cache keys should ignore case and redundant whitespace.
    """

    normalized = (
        public_demo.normalize_question(
            "  How MANY   orders are there?  "
        )
    )

    assert normalized == (
        "how many orders are there?"
    )


def test_cache_matches_normalized_questions() -> None:
    """
    Equivalent question formatting should hit the same cache key.
    """

    value = {
        "answer": "99,441",
    }

    public_demo.cache_answer(
        "How many orders are there?",
        value,
    )

    cached = (
        public_demo.get_cached_answer(
            "  HOW MANY   orders are there? "
        )
    )

    assert cached == value


def test_cache_entry_expires(
    monkeypatch,
) -> None:
    """
    Cached answers should disappear after the configured TTL.
    """

    current_time = [100.0]

    monkeypatch.setattr(
        public_demo.time,
        "monotonic",
        lambda: current_time[0],
    )

    monkeypatch.setattr(
        public_demo,
        "CACHE_TTL_SECONDS",
        10,
    )

    public_demo.cache_answer(
        "How many orders?",
        "cached-result",
    )

    assert (
        public_demo.get_cached_answer(
            "How many orders?"
        )
        == "cached-result"
    )

    current_time[0] = 111.0

    assert (
        public_demo.get_cached_answer(
            "How many orders?"
        )
        is None
    )


def test_cache_respects_maximum_size(
    monkeypatch,
) -> None:
    """
    The oldest cache entry should be evicted when the cache
    exceeds its configured maximum size.
    """

    monkeypatch.setattr(
        public_demo,
        "CACHE_MAX_ENTRIES",
        2,
    )

    public_demo.cache_answer(
        "question one",
        "answer one",
    )

    public_demo.cache_answer(
        "question two",
        "answer two",
    )

    public_demo.cache_answer(
        "question three",
        "answer three",
    )

    assert (
        public_demo.get_cached_answer(
            "question one"
        )
        is None
    )

    assert (
        public_demo.get_cached_answer(
            "question two"
        )
        == "answer two"
    )

    assert (
        public_demo.get_cached_answer(
            "question three"
        )
        == "answer three"
    )