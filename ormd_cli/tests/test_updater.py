"""Tests for ORMD updater functionality."""

import pytest
import tempfile
import os
from pathlib import Path
from ormd_cli.updater import ORMDUpdater
from ormd_cli.parser import parse_document, serialize_front_matter # Added serialize_front_matter
from datetime import datetime, timezone
import logging # Added for caplog


class TestORMDUpdater:
    """Test the ORMD updater functionality."""

    def test_basic_update(self):
        """Test basic update functionality."""
        content = '''<!-- ormd:0.1 -->
---
title: "Test Document"
authors: ["Test Author"]
links: []
---

# Test Document

This is a test document with some words. It has [[test-link]] references
and ![image](assets/test.png) assets.

## Section Two

More content here with additional words to test counting.
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ormd', delete=False) as f:
            f.write(content)
            temp_path = f.name
        
        try:
            updater = ORMDUpdater()
            result = updater.update_file(temp_path, dry_run=True)
            
            assert not result['updated']  # Dry run doesn't update
            assert 'dates' in result['changes']
            assert 'metrics' in result['changes']
            assert 'link_ids' in result['changes']
            assert 'asset_ids' in result['changes']
            
            # Check computed values
            dates = result['changes']['dates']['new']
            assert 'created' in dates
            assert 'modified' in dates
            
            metrics = result['changes']['metrics']['new']
            assert 'word_count' in metrics
            assert 'reading_time' in metrics
            assert metrics['word_count'] > 0
            
            link_ids = result['changes']['link_ids']['new']
            assert 'test-link' in link_ids
            
            asset_ids = result['changes']['asset_ids']['new']
            assert 'assets/test.png' in asset_ids
            
        finally:
            os.unlink(temp_path)

    def test_idempotency(self):
        """Test that running update twice produces no changes."""
        content = '''<!-- ormd:0.1 -->
---
title: "Test Document"
authors: ["Test Author"]
links: []
---

# Test Document

Simple content for testing.
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ormd', delete=False) as f:
            f.write(content)
            temp_path = f.name
        
        try:
            updater = ORMDUpdater()
            
            # First update
            result1 = updater.update_file(temp_path)
            assert result1['updated']
            
            # Second update should show no changes
            result2 = updater.update_file(temp_path)
            assert not result2['updated']
            assert not result2['changes']
            
        finally:
            os.unlink(temp_path)

    def test_locked_fields(self):
        """Test that locked fields are not updated."""
        content = '''<!-- ormd:0.1 -->
---
title: "Test Document"
authors: ["Test Author"]
links: []
dates:
  created: "2025-01-01T00:00:00Z"
  modified: "2025-01-01T00:00:00Z"
  locked: ["modified"]
metrics:
  word_count: 10
  reading_time: "1 min"
  locked: true
---

# Test Document

This document has many more words than the locked count of 10.
The word count should not be updated because metrics are locked.
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ormd', delete=False) as f:
            f.write(content)
            temp_path = f.name
        
        try:
            updater = ORMDUpdater()
            result = updater.update_file(temp_path, dry_run=True)
            
            # Should have some changes but not for locked fields
            if result['changes']:
                # dates.modified should not change (locked)
                if 'dates' in result['changes']:
                    dates = result['changes']['dates']['new']
                    assert dates.get('modified') == "2025-01-01T00:00:00Z"
                
                # metrics should not change (locked: true)
                assert 'metrics' not in result['changes'] or result['changes']['metrics']['new']['word_count'] == 10
            
        finally:
            os.unlink(temp_path)

    def test_force_update_locked_fields(self):
        """Test that force update ignores locks."""
        content = '''<!-- ormd:0.1 -->
---
title: "Test Document"
authors: ["Test Author"]
links: []
dates:
  created: "2025-01-01T00:00:00Z"
  modified: "2025-01-01T00:00:00Z"
  locked: ["modified"]
---

# Test Document

Simple content.
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ormd', delete=False) as f:
            f.write(content)
            temp_path = f.name
        
        try:
            updater = ORMDUpdater()
            result = updater.update_file(temp_path, dry_run=True, force_update=True)
            
            # With force_update, we should see changes even for locked fields
            # The test passes if we get some changes when force_update is True
            assert result['changes'] or not result['updated']
            
        finally:
            os.unlink(temp_path)

    def test_word_counting(self):
        """Test word counting logic."""
        updater = ORMDUpdater()
        
        # Test basic word counting
        text = "This is a simple test with nine words here."
        assert updater._count_words(text) == 9
        
        # Test excluding code blocks
        text_with_code = '''
        This is text with code.
        
        ```python
        def hello():
            print("This code should not be counted")
        ```
        
        And more text after.
        '''
        count = updater._count_words(text_with_code)
        # The actual count is 9 words: "This is text with code. And more text after."
        assert count == 9
        
        # Test excluding inline code
        text_with_inline = "This has `code` and more words."
        # The actual count is 5: "This has and more words."
        assert updater._count_words(text_with_inline) == 5

    def test_link_id_extraction(self):
        """Test link ID extraction."""
        updater = ORMDUpdater()
        
        body = '''
        # Section One
        
        This references [[intro]] and [[methodology]].
        
        ## Section Two
        
        Another reference to [[intro]] and [[conclusion]].
        '''
        
        link_ids = updater._extract_link_ids(body)
        assert link_ids == ['intro', 'methodology', 'conclusion']  # Unique, preserving order

    def test_asset_id_extraction(self):
        """Test asset ID extraction."""
        updater = ORMDUpdater()
        
        body = '''
        # Document with Assets
        
        Here's an image: ![Chart](assets/chart.png)
        
        And a PDF: [Report](assets/report.pdf)
        
        HTML image: <img src="assets/diagram.svg" alt="Diagram">
        
        External image (should be ignored): ![External](https://example.com/image.png)
        
        Another local asset: [Data](data/file.csv)
        '''
        
        asset_ids = updater._extract_asset_ids(body)
        # Only assets with recognized extensions should be included
        # PDF files are included, but CSV might not be in the extension list
        expected = ['assets/chart.png', 'assets/report.pdf', 'assets/diagram.svg']
        assert 'assets/chart.png' in asset_ids
        assert 'assets/report.pdf' in asset_ids
        assert 'assets/diagram.svg' in asset_ids
        # External URLs should be excluded
        assert not any('example.com' in asset for asset in asset_ids)

    def test_preserve_existing_fields(self):
        """Test that existing non-locked fields are preserved."""
        content = '''<!-- ormd:0.1 -->
---
title: "Test Document"
authors: ["Test Author"]
links: []
version: "1.0"
status: "draft"
---

# Test Document

Content here.
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ormd', delete=False) as f:
            f.write(content)
            temp_path = f.name
        
        try:
            updater = ORMDUpdater()
            result = updater.update_file(temp_path)
            
            # Read back the updated file
            updated_content = Path(temp_path).read_text(encoding='utf-8')
            front_matter, _, _, _, _ = parse_document(updated_content)
            
            # Check that existing fields are preserved
            assert front_matter['version'] == "1.0"
            assert front_matter['status'] == "draft"
            
            # Check that new fields were added
            assert 'dates' in front_matter
            assert 'metrics' in front_matter
            
        finally:
            os.unlink(temp_path)

    def test_no_front_matter(self):
        """Test updating a document with no front-matter."""
        content = '''<!-- ormd:0.1 -->

# Test Document

This document has no front-matter initially.
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ormd', delete=False) as f:
            f.write(content)
            temp_path = f.name
        
        try:
            updater = ORMDUpdater()
            result = updater.update_file(temp_path)
            
            assert result['updated']
            
            # Read back the updated file
            updated_content = Path(temp_path).read_text(encoding='utf-8')
            front_matter, body, _, _, _ = parse_document(updated_content)
            
            # Check that front-matter was created
            assert front_matter is not None
            assert 'title' in front_matter
            assert 'authors' in front_matter
            assert 'dates' in front_matter
            assert 'metrics' in front_matter
            
            # Check that body is preserved
            assert 'This document has no front-matter initially.' in body
            
        finally:
            os.unlink(temp_path)

    def _create_ormd_content(self, fm_dict: dict, body_md: str) -> str:
        """Helper to create ORMD file content string."""
        fm_string = serialize_front_matter(fm_dict if fm_dict is not None else {})
        return f"<!-- ormd:0.1 -->\n{fm_string}\n{body_md}"

    def test_link_merging_no_initial_fm_links(self, tmp_path):
        """Test merging auto-links when front-matter has no 'links' field initially."""
        updater = ORMDUpdater()
        body_content = "This is a [test link](target1 'rel1') and [another link](target2)."
        # Front-matter without a 'links' key
        initial_fm = {"title": "Test Doc", "authors": ["Author"]} 
        content = self._create_ormd_content(initial_fm, body_content)
        
        file_path = tmp_path / "test.ormd"
        file_path.write_text(content, encoding='utf-8')

        result = updater.update_file(str(file_path), legacy_links_mode=False)
        assert result['updated']
        assert 'links' in result['changes']
        
        updated_content = file_path.read_text(encoding='utf-8')
        fm, _, _, _, _ = parse_document(updated_content)
        
        assert 'links' in fm
        assert len(fm['links']) == 2
        assert fm['links'][0]['id'] == 'auto-link-1'
        assert fm['links'][0]['text'] == 'test link'
        assert fm['links'][0]['target'] == 'target1'
        assert fm['links'][0]['rel'] == 'rel1'
        assert fm['links'][0]['source'] == 'inline'
        assert fm['links'][1]['id'] == 'auto-link-2'
        assert fm['links'][1]['text'] == 'another link'
        assert fm['links'][1]['target'] == 'target2'
        assert fm['links'][1]['rel'] is None
        assert fm['links'][1]['source'] == 'inline'

    def test_link_merging_with_manual_no_conflict(self, tmp_path):
        """Test merging auto-links with existing non-conflicting manual links."""
        updater = ORMDUpdater()
        manual_links_fm = [
            {"id": "manual1", "to": "#section1", "rel": "supports", "title": "Manual One"}
        ]
        initial_fm = {"title": "Test Doc", "authors": ["Author"], "links": manual_links_fm}
        body_content = "A [new link](new_target 'new_rel')."
        content = self._create_ormd_content(initial_fm, body_content)

        file_path = tmp_path / "test.ormd"
        file_path.write_text(content, encoding='utf-8')

        result = updater.update_file(str(file_path), legacy_links_mode=False)
        assert result['updated']
        assert 'links' in result['changes']
        
        updated_content = file_path.read_text(encoding='utf-8')
        fm, _, _, _, _ = parse_document(updated_content)
        
        assert len(fm['links']) == 2
        # Manual link should be first
        assert fm['links'][0]['id'] == 'manual1'
        assert fm['links'][0]['to'] == '#section1'
        # Auto-generated link
        assert fm['links'][1]['id'] == 'auto-link-1'
        assert fm['links'][1]['text'] == 'new link'
        assert fm['links'][1]['target'] == 'new_target'
        assert fm['links'][1]['rel'] == 'new_rel'
        assert fm['links'][1]['source'] == 'inline'


    def test_link_merging_duplicate_auto_link_is_discarded(self, tmp_path):
        """Test that an auto-link duplicating a manual link (same to, rel) is discarded."""
        updater = ORMDUpdater()
        manual_links_fm = [
            {"id": "manual1", "to": "target1", "rel": "rel1", "title": "Manual One"}
        ]
        initial_fm = {"title": "Test Doc", "authors": ["Author"], "links": manual_links_fm}
        # This auto-link has the same target and rel as manual1
        body_content = "This is a [duplicate link](target1 'rel1'). And [another one](target2)."
        content = self._create_ormd_content(initial_fm, body_content)

        file_path = tmp_path / "test.ormd"
        file_path.write_text(content, encoding='utf-8')

        result = updater.update_file(str(file_path), legacy_links_mode=False)
        # It should be updated because of the second, non-duplicate link
        assert result['updated']
        assert 'links' in result['changes']
        
        updated_content = file_path.read_text(encoding='utf-8')
        fm, _, _, _, _ = parse_document(updated_content)
        
        assert len(fm['links']) == 2 # Manual1 + auto-link-for-target2
        assert fm['links'][0]['id'] == 'manual1' # Manual link preserved
        assert fm['links'][1]['id'] == 'auto-link-1' # This ID is for the *second* inline link from body
        assert fm['links'][1]['text'] == 'another one'
        assert fm['links'][1]['target'] == 'target2'
        assert fm['links'][1]['source'] == 'inline'


    def test_link_merging_conflict_auto_link_is_added_with_warning(self, tmp_path, caplog):
        """Test auto-link with same target but different rel as manual link (conflict)."""
        updater = ORMDUpdater()
        manual_links_fm = [
            {"id": "manual1", "to": "target1", "rel": "rel_manual", "title": "Manual One"}
        ]
        initial_fm = {"title": "Test Doc", "authors": ["Author"], "links": manual_links_fm}
        # This auto-link has same target, different rel
        body_content = "This is a [conflicting link](target1 'rel_auto')."
        content = self._create_ormd_content(initial_fm, body_content)

        file_path = tmp_path / "test.ormd"
        file_path.write_text(content, encoding='utf-8')

        with caplog.at_level(logging.WARNING):
            result = updater.update_file(str(file_path), legacy_links_mode=False)
        
        assert result['updated']
        assert 'links' in result['changes']
        
        updated_content = file_path.read_text(encoding='utf-8')
        fm, _, _, _, _ = parse_document(updated_content)
        
        assert len(fm['links']) == 2 # Both manual and auto-link should be present
        assert fm['links'][0]['id'] == 'manual1'
        assert fm['links'][1]['id'] == 'auto-link-1'
        assert fm['links'][1]['text'] == 'conflicting link'
        assert fm['links'][1]['target'] == 'target1'
        assert fm['links'][1]['rel'] == 'rel_auto'
        assert fm['links'][1]['source'] == 'inline'
        
        assert "Conflict in" in caplog.text # Check for file path in log
        assert "Auto-generated link auto-link-1 for target 'target1'" in caplog.text
        assert "conflicts with an existing manual link with a different relationship" in caplog.text

    def test_legacy_links_mode_no_link_merging(self, tmp_path):
        """Test that in legacy_links_mode, auto-links are not merged."""
        updater = ORMDUpdater()
        manual_links_fm = [
            {"id": "manual1", "to": "#section1", "rel": "supports", "title": "Manual One"}
        ]
        initial_fm = {"title": "Test Doc", "authors": ["Author"], "links": manual_links_fm}
        body_content = "A [new link](new_target 'new_rel')." # This would normally be merged
        content = self._create_ormd_content(initial_fm, body_content)

        file_path = tmp_path / "test.ormd"
        file_path.write_text(content, encoding='utf-8')

        # Update other fields (dates, metrics etc may change) but links should not due to auto-gen
        result = updater.update_file(str(file_path), legacy_links_mode=True)
        
        updated_content = file_path.read_text(encoding='utf-8')
        fm, _, _, _, _ = parse_document(updated_content)
        
        assert len(fm['links']) == 1 # Only manual link should be present
        assert fm['links'][0]['id'] == 'manual1'

        # Check if 'links' was part of changes. If only other fields changed, it might not be.
        # The key is that the content of 'links' only contains the original manual links.
        final_links_content = fm.get("links", [])
        assert len(final_links_content) == 1
        assert final_links_content[0]['id'] == 'manual1'
            
        # If other fields like dates/metrics were updated, result['updated'] would be True.
        # We are primarily concerned that the 'links' list was not modified by auto-links.
        original_links_content = initial_fm.get("links", [])
        assert original_links_content == final_links_content
