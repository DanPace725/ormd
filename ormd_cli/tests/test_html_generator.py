import pytest
from ormd_cli.html_generator import _preprocess_body_links # Test the core processing
from ormd_cli.parser import parse_document # To get auto_links for tests

# Minimal ORMD boilerplate for tests
ORM_VERSION_TAG = "<!-- ormd:0.1 -->\n"
BASIC_FM_LINES = "---\ntitle: \"Test HTML Gen\"\nauthors: [\"Test\"]\nlinks: []\n---\n"

class TestHtmlLinkRendering:

    def test_render_inline_semantic_link_with_rel(self):
        body_md = "This is a [display text](https://example.com/target \"supports\") link."
        # Simulate parser output for this specific link
        auto_links_from_parser = [{
            "id": "auto-link-1", "text": "display text", 
            "target": "https://example.com/target", "rel": "supports", "source": "inline"
        }]
        # Merged FM links are empty for this test of inline rendering
        merged_fm_links = [] 

        processed_body = _preprocess_body_links(body_md, auto_links_from_parser, merged_fm_links)
        assert processed_body == 'This is a <a href="https://example.com/target" data-link-id="auto-link-1" data-rel="supports">display text</a> link.'

    def test_render_inline_semantic_link_no_rel(self):
        body_md = "Link: [another text](#internal-target)."
        auto_links_from_parser = [{
            "id": "auto-link-1", "text": "another text", 
            "target": "#internal-target", "rel": None, "source": "inline"
        }]
        merged_fm_links = []
        processed_body = _preprocess_body_links(body_md, auto_links_from_parser, merged_fm_links)
        assert processed_body == 'Link: <a href="#internal-target" data-link-id="auto-link-1">another text</a>.'

    def test_render_legacy_link_id_found_manual_with_title(self):
        body_md = "Reference to [[manual1]]."
        auto_links_from_parser = [] # No inline links for this test
        merged_fm_links = [{
            "id": "manual1", "to": "#section1", "rel": "cites", "title": "Section One"
        }]
        processed_body = _preprocess_body_links(body_md, auto_links_from_parser, merged_fm_links)
        assert processed_body == 'Reference to <a href="#section1" data-link-id="manual1" data-rel="cites">Section One</a>.'

    def test_render_legacy_link_id_found_manual_no_title_uses_id(self):
        body_md = "Reference to [[manual2]]."
        auto_links_from_parser = []
        merged_fm_links = [{
            "id": "manual2", "to": "https://example.com/manual", "rel": "references"
        }]
        processed_body = _preprocess_body_links(body_md, auto_links_from_parser, merged_fm_links)
        assert processed_body == 'Reference to <a href="https://example.com/manual" data-link-id="manual2" data-rel="references">manual2</a>.'

    def test_render_legacy_link_id_found_merged_auto_link_with_text(self):
        body_md = "Refers to [[auto-link-5]]."
        auto_links_from_parser = [] # This tests rendering of a [[id]], not the inline form
        merged_fm_links = [{
            "id": "auto-link-5", "text": "Previously Inline Text", 
            "target": "#target-of-auto", "to": "#target-of-auto", # Ensure 'to' is present for map
            "rel": "supports", "source": "inline"
        }]
        processed_body = _preprocess_body_links(body_md, auto_links_from_parser, merged_fm_links)
        # Display text uses 'text' field for merged auto-links
        assert processed_body == 'Refers to <a href="#target-of-auto" data-link-id="auto-link-5" data-rel="supports">Previously Inline Text</a>.'

    def test_render_legacy_link_id_undefined(self):
        body_md = "Link to [[undefined-id]]."
        auto_links_from_parser = []
        merged_fm_links = [] # No definition for undefined-id
        processed_body = _preprocess_body_links(body_md, auto_links_from_parser, merged_fm_links)
        assert processed_body == 'Link to <span class="ormd-link ormd-link-undefined" data-link-id="undefined-id">undefined-id</span>.'

    def test_render_mixed_link_types(self):
        # This test uses parse_document to simulate a more integrated scenario for auto_links
        ormd_content = ORM_VERSION_TAG + """---
title: "Mixed Links Test"
authors: ["Test"]
links:
  - id: "manual-link"
    to: "#manual-target"
    rel: "cites"
    title: "Manual Target Section"
---
This body has an [inline link](https://example.com/auto "auto-rel") which will be auto-link-1.
It also references [[manual-link]] and another [inline link no rel](page.html).
Finally, a reference to [[auto-link-1]] (if it were updated into FM) and [[non-existent]].
"""
        # 1. Parse the document to get body and auto_links_from_parser
        fm, body, _, auto_links, _ = parse_document(ormd_content)
        
        merged_fm_links_for_test = fm.get('links', [])
        
        # Simulate that auto-link-1 (parsed from the body) is also defined in the merged links
        # This would happen if an updater had run, or if we want to test [[auto-link-1]] resolution
        first_auto_link_details = next((al for al in auto_links if al['id'] == 'auto-link-1'), None)
        if first_auto_link_details:
            merged_auto_link = {
                "id": first_auto_link_details['id'],
                "to": first_auto_link_details['target'], # map 'target' to 'to' for merged_links_map
                "text": first_auto_link_details['text'],
                "rel": first_auto_link_details['rel'],
                "source": first_auto_link_details['source']
            }
            # Avoid adding if an item with the same id already exists from manual FM
            if not any(l.get('id') == merged_auto_link['id'] for l in merged_fm_links_for_test):
                 merged_fm_links_for_test.append(merged_auto_link)

        processed_body = _preprocess_body_links(body, auto_links, merged_fm_links_for_test)

        expected_html_parts = [
            'This body has an <a href="https://example.com/auto" data-link-id="auto-link-1" data-rel="auto-rel">inline link</a> which will be auto-link-1.',
            'It also references <a href="#manual-target" data-link-id="manual-link" data-rel="cites">Manual Target Section</a> and another <a href="page.html" data-link-id="auto-link-2">inline link no rel</a>.',
            'Finally, a reference to <a href="https://example.com/auto" data-link-id="auto-link-1" data-rel="auto-rel">inline link</a> (if it were updated into FM) and <span class="ormd-link ormd-link-undefined" data-link-id="non-existent">non-existent</span>.'
        ]
        
        current_pos = 0
        for part in expected_html_parts:
            assert part in processed_body
            # Optional: Check order if necessary, though simple "in" covers presence
            # found_pos = processed_body.find(part, current_pos)
            # assert found_pos != -1, f"Part not found or out of order: {part}"
            # current_pos = found_pos + len(part)


    def test_render_inline_link_with_markdown_chars_in_text(self):
        body_md = "A link with [text *containing* `markdown`](target)."
        auto_links_from_parser = [{
            "id": "auto-link-1", "text": "text *containing* `markdown`", 
            "target": "target", "rel": None, "source": "inline"
        }]
        merged_fm_links = []
        processed_body = _preprocess_body_links(body_md, auto_links_from_parser, merged_fm_links)
        # The text part of <a> tag should be exactly as parsed, markdown rendering is separate.
        assert processed_body == 'A link with <a href="target" data-link-id="auto-link-1">text *containing* `markdown`</a>.'

    def test_render_multiple_identical_inline_links_get_distinct_ids_in_sequence(self):
        body_md = "First [same link](target). Second [same link](target)."
        # Parser should generate distinct IDs based on sequence
        auto_links_from_parser = [
            {"id": "auto-link-1", "text": "same link", "target": "target", "rel": None, "source": "inline"},
            {"id": "auto-link-2", "text": "same link", "target": "target", "rel": None, "source": "inline"}
        ]
        merged_fm_links = []
        processed_body = _preprocess_body_links(body_md, auto_links_from_parser, merged_fm_links)
        assert '<a href="target" data-link-id="auto-link-1">same link</a>' in processed_body
        assert '<a href="target" data-link-id="auto-link-2">same link</a>' in processed_body
        assert processed_body.count("[same link](target)") == 0 # Ensure original markdown is replaced

    def test_empty_body_no_links(self):
        body_md = ""
        auto_links_from_parser = []
        merged_fm_links = []
        processed_body = _preprocess_body_links(body_md, auto_links_from_parser, merged_fm_links)
        assert processed_body == ""

    def test_body_with_no_links_passes_through(self):
        body_md = "This is some text without any links."
        auto_links_from_parser = []
        merged_fm_links = []
        processed_body = _preprocess_body_links(body_md, auto_links_from_parser, merged_fm_links)
        assert processed_body == body_md

    def test_legacy_link_display_text_priority(self):
        """Test display text priority: 'text' (from auto), then 'title' (manual), then 'id'."""
        body_md = "[[link1]] [[link2]] [[link3]]"
        auto_links_from_parser = []
        merged_fm_links = [
            {"id": "link1", "to": "#t1", "text": "Display Text from Auto", "title": "Should be Ignored", "source": "inline"},
            {"id": "link2", "to": "#t2", "title": "Display Text from Manual Title"},
            {"id": "link3", "to": "#t3"} # No text or title, should use id
        ]
        processed_body = _preprocess_body_links(body_md, auto_links_from_parser, merged_fm_links)
        assert '<a href="#t1" data-link-id="link1">Display Text from Auto</a>' in processed_body
        assert '<a href="#t2" data-link-id="link2">Display Text from Manual Title</a>' in processed_body
        assert '<a href="#t3" data-link-id="link3">link3</a>' in processed_body

