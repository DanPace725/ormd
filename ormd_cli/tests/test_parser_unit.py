"""Unit tests for ORMD parser functionality.

These tests focus on parser behavior with minimal sample files and edge cases.
"""

import pytest
import tempfile
import os
from pathlib import Path
from ormd_cli.parser import parse_document, serialize_front_matter


class TestParserUnit:
    """Unit tests for ORMD parser functionality."""

    def test_minimal_valid_document(self):
        """Test parsing minimal valid ORMD document."""
        content = '''<!-- ormd:0.1 -->
---
title: "Minimal Document"
authors: ["Test Author"]
links: []
---

# Minimal Content

Just a simple paragraph.
'''
        
        front_matter, body, metadata, auto_links, errors = parse_document(content)
        
        assert not errors
        assert front_matter is not None
        assert front_matter['title'] == "Minimal Document"
        assert front_matter['authors'] == ["Test Author"]
        assert front_matter['links'] == []
        assert "# Minimal Content" in body
        assert "Just a simple paragraph." in body

    def test_empty_body_document(self):
        """Test parsing document with empty body content."""
        content = '''<!-- ormd:0.1 -->
---
title: "Empty Body Document"
authors: ["Test Author"]
links: []
---

'''
        
        front_matter, body, metadata, auto_links, errors = parse_document(content)
        
        assert not errors
        assert front_matter is not None
        assert front_matter['title'] == "Empty Body Document"
        assert body.strip() == ""

    def test_no_links_document(self):
        """Test parsing document with no links defined."""
        content = '''<!-- ormd:0.1 -->
---
title: "No Links Document"
authors: ["Test Author"]
links: []
---

# Content Without Links

This document has no semantic links defined.
No [[references]] to anything.
'''
        
        front_matter, body, metadata, auto_links, errors = parse_document(content)
        
        assert not errors
        assert front_matter['links'] == []
        assert "[[references]]" in body

    def test_plus_delimiter_parsing(self):
        """Test parsing document with +++ delimiters."""
        content = '''<!-- ormd:0.1 -->
+++
title: "Plus Delimiter Document"
authors: ["Test Author"]
links:
  - id: "test-link"
    rel: "supports"
    to: "#section"
+++

# Content

This uses +++ delimiters and references [[test-link]].
'''
        
        front_matter, body, metadata, auto_links, errors = parse_document(content)
        
        assert not errors
        assert front_matter['title'] == "Plus Delimiter Document"
        assert len(front_matter['links']) == 1
        assert front_matter['links'][0]['id'] == "test-link"

    def test_complex_front_matter_parsing(self):
        """Test parsing document with complex front-matter structure."""
        content = '''<!-- ormd:0.1 -->
---
title: "Complex Document"
authors:
  - id: "author1"
    display: "John Doe"
    email: "john@example.com"
  - "Jane Smith"
links:
  - id: "ref1"
    rel: "supports"
    to: "#section1"
  - id: "ref2"
    rel: "extends"
    to: "other.ormd"
dates:
  created: "2025-01-01T10:00:00Z"
  modified: "2025-01-02T15:30:00Z"
metrics:
  word_count: 150
  reading_time: "2 min"
permissions:
  mode: "published"
  editable: false
  signed: true
version: "1.0"
status: "published"
keywords: ["test", "complex", "metadata"]
---

# Complex Document

This document has complex front-matter with all optional fields.

## Section 1

Content referencing [[ref1]] and [[ref2]].
'''
        
        front_matter, body, metadata, auto_links, errors = parse_document(content)
        
        assert not errors
        assert front_matter['title'] == "Complex Document"
        assert len(front_matter['authors']) == 2
        assert isinstance(front_matter['authors'][0], dict)
        assert front_matter['authors'][0]['display'] == "John Doe"
        assert front_matter['authors'][1] == "Jane Smith"
        assert len(front_matter['links']) == 2
        assert front_matter['dates']['created'] == "2025-01-01T10:00:00Z"
        assert front_matter['metrics']['word_count'] == 150
        assert front_matter['permissions']['mode'] == "published"
        assert front_matter['version'] == "1.0"
        assert "complex" in front_matter['keywords']

    def test_malformed_yaml_parsing(self):
        """Test parsing document with malformed YAML."""
        content = '''<!-- ormd:0.1 -->
---
title: "Malformed Document"
authors: ["Test Author"
links: []
invalid_yaml: this is not valid: yaml: syntax
---

# Content

Body content here.
'''
        
        front_matter, body, metadata, auto_links, errors = parse_document(content)
        
        assert errors
        assert any("Invalid YAML" in error for error in errors)
        assert front_matter is None

    def test_missing_version_tag_parsing(self):
        """Test parsing document without version tag."""
        content = '''---
title: "No Version Document"
authors: ["Test Author"]
links: []
---

# Content

Body without version tag.
'''
        
        front_matter, body, metadata, auto_links, errors = parse_document(content)
        
        # Parser should fail when missing version tag
        assert front_matter is None
        assert errors
        assert any("Missing or invalid version tag" in error for error in errors)

    def test_no_front_matter_parsing(self):
        """Test parsing document with no front-matter."""
        content = '''<!-- ormd:0.1 -->

# Just Content

This document has no front-matter at all.
'''
        
        front_matter, body, metadata, auto_links, errors = parse_document(content)
        
        assert not errors
        assert front_matter == {}  # Parser converts None to empty dict
        assert "# Just Content" in body

    def test_unclosed_front_matter_parsing(self):
        """Test parsing document with unclosed front-matter."""
        content = '''<!-- ormd:0.1 -->
---
title: "Unclosed Document"
authors: ["Test Author"]
links: []

# Content

This front-matter is never closed.
'''
        
        front_matter, body, metadata, auto_links, errors = parse_document(content)
        
        # Should return None when front-matter is unclosed and treat entire content as body
        assert front_matter is None
        assert "title:" in body

    def test_legacy_meta_block_error(self):
        """Test that legacy +++meta blocks now generate errors."""
        content = '''<!-- ormd:0.1 -->
---
title: "Legacy Document"
authors: ["Test Author"]
links: []
---

# Content

Some content here.

+++meta
legacy_field: "This should generate an error"
+++end-meta

More content.
'''
        
        front_matter, body, metadata, auto_links, errors = parse_document(content)
        
        assert front_matter is not None # Parser might still return front_matter
        assert any("`+++meta` blocks are no longer supported" in error for error in errors)

    def test_multiple_yaml_blocks_error(self):
        """Test that multiple YAML blocks generate an error."""
        content = '''<!-- ormd:0.1 -->
---
title: "Initial Valid Front Matter"
authors: ["Test Author"]
links: []
---

# Body Content

This is the main body.

---
another_title: "This is a second YAML block"
problem: true
---

More body content.
'''
        front_matter, body, metadata, auto_links, errors = parse_document(content)
        assert front_matter is not None # The first FM should parse
        assert any("Multiple YAML front-matter blocks found" in error for error in errors)
        assert "another_title" in body # The second block is part of the body now

    def test_parse_invalid_legacy_meta_fixture(self):
        """Test parsing fixture with legacy +++meta block."""
        fixture_path = Path(__file__).parent / "fixtures" / "invalid_legacy_meta.ormd"
        content = fixture_path.read_text(encoding='utf-8')
        front_matter, body, metadata, auto_links, errors = parse_document(content)
        assert front_matter is not None
        assert any("`+++meta` blocks are no longer supported" in error for error in errors)

    def test_parse_invalid_multiple_yaml_fixture(self):
        """Test parsing fixture with multiple YAML blocks."""
        fixture_path = Path(__file__).parent / "fixtures" / "invalid_multiple_yaml.ormd"
        content = fixture_path.read_text(encoding='utf-8')
        front_matter, body, metadata, auto_links, errors = parse_document(content)
        assert front_matter is not None
        assert any("Multiple YAML front-matter blocks found" in error for error in errors)

    def test_serialize_front_matter_ordering(self):
        """Test that front-matter serialization maintains stable field ordering."""
        front_matter = {
            'keywords': ['test', 'ordering'],
            'title': "Test Document",
            'version': "1.0",
            'authors': ["Test Author"],
            'links': [],
            'metrics': {
                'word_count': 100,
                'reading_time': "1 min"
            },
            'status': "draft",
            'dates': {
                'created': "2025-01-01T10:00:00Z"
            }
        }
        
        serialized = serialize_front_matter(front_matter)
        
        # Check that required fields come first
        lines = serialized.split('\n')
        yaml_lines = [line for line in lines if line and not line.startswith('---')]
        
        # Find indices of key fields
        title_idx = next(i for i, line in enumerate(yaml_lines) if line.startswith('title:'))
        authors_idx = next(i for i, line in enumerate(yaml_lines) if line.startswith('authors:'))
        links_idx = next(i for i, line in enumerate(yaml_lines) if line.startswith('links:'))
        
        # Required fields should come first in order
        assert title_idx < authors_idx < links_idx
        
        # Check that organized namespaces come after required fields
        dates_idx = next((i for i, line in enumerate(yaml_lines) if line.startswith('dates:')), -1)
        metrics_idx = next((i for i, line in enumerate(yaml_lines) if line.startswith('metrics:')), -1)
        
        if dates_idx != -1:
            assert dates_idx > links_idx
        if metrics_idx != -1:
            assert metrics_idx > links_idx

    def test_serialize_empty_front_matter(self):
        """Test serializing empty front-matter."""
        serialized = serialize_front_matter({})
        
        assert serialized == "---\n---\n"

    def test_serialize_minimal_front_matter(self):
        """Test serializing minimal required front-matter."""
        front_matter = {
            'title': "Minimal Document",
            'authors': ["Test Author"],
            'links': []
        }
        
        serialized = serialize_front_matter(front_matter)
        
        assert 'title: Minimal Document' in serialized
        assert 'authors:' in serialized
        assert '- Test Author' in serialized
        assert 'links: []' in serialized
        assert serialized.startswith('---\n')
        assert serialized.endswith('---\n')

    def test_delimiter_collision_handling(self):
        """Test parsing when body content contains front-matter delimiters."""
        content = '''<!-- ormd:0.1 -->
---
title: "Delimiter Collision Document"
authors: ["Test Author"]
links: []
---

# Content with Delimiters

This content has some --- delimiters in it.

```yaml
---
some: yaml
---
```

And some +++ text too.

+++
not front-matter
+++
'''
        
        front_matter, body, metadata, auto_links, errors = parse_document(content)
        
        assert not errors
        assert front_matter['title'] == "Delimiter Collision Document"
        assert "---" in body
        assert "+++" in body
        assert "not front-matter" in body

    def test_parse_single_inline_link_with_rel(self):
        """Test parsing a single inline semantic link with a relationship."""
        content = '''<!-- ormd:0.1 -->
---
title: "Inline Link Test"
authors: ["Test Author"]
links: []
---

This is a [display text](https://example.com/target "supports") link.
'''
        # Expected return: front_matter, body, metadata (None), auto_links, errors
        front_matter, body, metadata, auto_links, errors = parse_document(content)
        
        assert not errors
        assert front_matter is not None
        assert len(auto_links) == 1
        link1 = auto_links[0]
        assert link1['id'] == 'auto-link-1'
        assert link1['text'] == 'display text'
        assert link1['target'] == 'https://example.com/target'
        assert link1['rel'] == 'supports'
        assert link1['source'] == 'inline'
        assert "This is a [display text](https://example.com/target \"supports\") link." in body # Body remains unchanged by parser for this

    def test_parse_single_inline_link_no_rel(self):
        """Test parsing a single inline semantic link without a relationship."""
        content = '''<!-- ormd:0.1 -->
---
title: "Inline Link No Rel Test"
authors: ["Test Author"]
links: []
---

Link: [another text](#internal-target).
'''
        front_matter, body, metadata, auto_links, errors = parse_document(content)
        
        assert not errors
        assert front_matter is not None
        assert len(auto_links) == 1
        link1 = auto_links[0]
        assert link1['id'] == 'auto-link-1'
        assert link1['text'] == 'another text'
        assert link1['target'] == '#internal-target'
        assert link1['rel'] is None
        assert link1['source'] == 'inline'

    def test_parse_multiple_inline_links(self):
        """Test parsing multiple inline semantic links in order."""
        content = '''<!-- ormd:0.1 -->
---
title: "Multiple Inline Links"
authors: ["Test Author"]
links: []
---

First [link1](target1 "rel1") and second [link2](target2).
Then a third one [link3](target3 "rel3").
'''
        front_matter, body, metadata, auto_links, errors = parse_document(content)
        
        assert not errors
        assert front_matter is not None
        assert len(auto_links) == 3
        
        assert auto_links[0]['id'] == 'auto-link-1'
        assert auto_links[0]['text'] == 'link1'
        assert auto_links[0]['target'] == 'target1'
        assert auto_links[0]['rel'] == 'rel1'
        assert auto_links[0]['source'] == 'inline'
        
        assert auto_links[1]['id'] == 'auto-link-2'
        assert auto_links[1]['text'] == 'link2'
        assert auto_links[1]['target'] == 'target2'
        assert auto_links[1]['rel'] is None
        assert auto_links[1]['source'] == 'inline'
        
        assert auto_links[2]['id'] == 'auto-link-3'
        assert auto_links[2]['text'] == 'link3'
        assert auto_links[2]['target'] == 'target3'
        assert auto_links[2]['rel'] == 'rel3'
        assert auto_links[2]['source'] == 'inline'

    def test_parse_inline_links_with_special_chars_in_text_target(self):
        """Test inline links with special characters in text and target."""
        # Note: "rel" typically doesn't have many special chars.
        # Targets can be complex URLs.
        content = '''<!-- ormd:0.1 -->
---
title: "Special Chars Links"
authors: ["Test"]
links: []
---

A link [with *markdown* `chars`!](https://example.com/path?q=v&s=t#fragment "relates").
Another [link with spaces](target with spaces).
'''
        front_matter, body, metadata, auto_links, errors = parse_document(content)
        assert not errors
        assert len(auto_links) == 2

        assert auto_links[0]['id'] == 'auto-link-1'
        assert auto_links[0]['text'] == 'with *markdown* `chars`!'
        assert auto_links[0]['target'] == 'https://example.com/path?q=v&s=t#fragment'
        assert auto_links[0]['rel'] == 'relates'
        
        assert auto_links[1]['id'] == 'auto-link-2'
        assert auto_links[1]['text'] == 'link with spaces'
        assert auto_links[1]['target'] == 'target with spaces' # Markdown allows spaces in target if not encoded
        assert auto_links[1]['rel'] is None


    def test_parse_no_inline_links_in_body(self):
        """Test parsing a document with no inline semantic links in the body."""
        content = '''<!-- ormd:0.1 -->
---
title: "No Inline Links"
authors: ["Test"]
links: []
---

This body has no inline semantic links. Only [[legacy-style]] ones.
'''
        front_matter, body, metadata, auto_links, errors = parse_document(content)
        assert not errors
        assert len(auto_links) == 0

    def test_parse_empty_document_for_inline_links(self):
        """Test parsing an empty document (except version tag) for inline links."""
        content = '''<!-- ormd:0.1 -->
'''
        # Parsing allows a version-only document; validation enforces required front-matter.
        front_matter, body, metadata, auto_links, errors = parse_document(content)
        assert not errors
        assert front_matter == {}
        assert body == "" 
        assert len(auto_links) == 0


    def test_parse_document_with_only_front_matter_no_body_for_inline_links(self):
        """Test parsing a document with front-matter but an empty or non-existent body."""
        content = '''<!-- ormd:0.1 -->
---
title: "FM Only"
authors: ["Test"]
links: []
---
'''
        front_matter, body, metadata, auto_links, errors = parse_document(content)
        assert not errors
        assert front_matter is not None
        assert body.strip() == "" # Body is empty
        assert len(auto_links) == 0
        
        content_no_body_section = '''<!-- ormd:0.1 -->
---
title: "FM Only No Body Section"
authors: ["Test"]
links: []
---''' # No newline after closing ---
        front_matter, body, metadata, auto_links, errors = parse_document(content_no_body_section)
        assert not errors
        assert front_matter is not None
        assert body.strip() == "" # Body is effectively empty
        assert len(auto_links) == 0

    def test_inline_links_at_start_and_end_of_body(self):
        """Test inline links appearing at the very start or end of the body."""
        content = '''<!-- ormd:0.1 -->
---
title: "Edge Case Links"
authors: ["Test"]
links: []
---
[start link](start)This is body text[end link](end "last").
'''
        front_matter, body, metadata, auto_links, errors = parse_document(content)
        assert not errors
        assert len(auto_links) == 2
        assert auto_links[0]['id'] == 'auto-link-1'
        assert auto_links[0]['text'] == 'start link'
        assert auto_links[0]['target'] == 'start'
        assert auto_links[0]['rel'] is None

        assert auto_links[1]['id'] == 'auto-link-2'
        assert auto_links[1]['text'] == 'end link'
        assert auto_links[1]['target'] == 'end'
        assert auto_links[1]['rel'] == 'last'
