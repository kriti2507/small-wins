import migrate_to_supabase as m


def test_to_doc_passthrough_for_docs():
    doc = {"type": "doc", "content": []}
    assert m.to_doc(doc) is doc


def test_to_doc_converts_legacy_blocks():
    blocks = [{"type": "text", "text": "a\n\nb"},
              {"type": "image", "url": "/api/uploads/x.jpg"}]
    assert m.to_doc(blocks) == {"type": "doc", "content": [
        {"type": "paragraph", "content": [{"type": "text", "text": "a"}]},
        {"type": "paragraph", "content": [{"type": "text", "text": "b"}]},
        {"type": "figure", "attrs": {"src": "/api/uploads/x.jpg", "width": "normal"}},
    ]}


def test_rewrite_srcs_maps_known_urls_and_leaves_original():
    doc = {"type": "doc", "content": [
        {"type": "figure", "attrs": {"src": "/api/uploads/x.jpg", "width": "wide"}}]}
    out = m.rewrite_srcs(doc, {"/api/uploads/x.jpg": "https://cdn/x.jpg"})
    assert out["content"][0]["attrs"]["src"] == "https://cdn/x.jpg"
    assert out["content"][0]["attrs"]["width"] == "wide"
    assert doc["content"][0]["attrs"]["src"] == "/api/uploads/x.jpg"
