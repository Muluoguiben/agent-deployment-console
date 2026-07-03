from agent_service.retrieval import KBIndex


def test_index_builds_chunks(data_dir):
    index = KBIndex(data_dir / "kb")
    assert len(index.chunks) > 15
    docs = {c.doc for c in index.chunks}
    assert "video-playback-troubleshooting.md" in docs
    assert "escalation-policy.md" in docs


def test_black_screen_finds_ki001(data_dir):
    index = KBIndex(data_dir / "kb")
    results = index.search("black screen audio plays but no picture webview", top_k=3)
    assert results, "expected at least one hit"
    top_text = " ".join(chunk.text for chunk, _ in results)
    assert "KI-001" in top_text


def test_region_mismatch_finds_ki005(data_dir):
    index = KBIndex(data_dir / "kb")
    results = index.search("service not available in your region vehicle imported", top_k=3)
    combined = " ".join(chunk.text for chunk, _ in results)
    assert "KI-005" in combined


def test_empty_query_returns_nothing(data_dir):
    index = KBIndex(data_dir / "kb")
    assert index.search("!!! ???", top_k=3) == []
