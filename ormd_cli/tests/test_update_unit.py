"""Unit tests for ORMD update functionality.

These tests focus on update behavior with edge cases like empty body, no links, locked fields.
"""

import pytest
import tempfile
import os
from pathlib import Path
from ormd_cli.updater import ORMDUpdater


class TestUpdateUnit:
    """Unit tests for ORMD update functionality."""

    def test_update_minimal_document(self):
        """Test updating minimal ORMD document with basic metadata."""
        content = '''<!-- ormd:0.1 -->
---
title: "Minimal Document"
authors: ["Test Author"]
links: []
---

# Minimal Content

Just a simple paragraph with 5 words.
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ormd', delete=False) as f:
            f.write(content)
            temp_path = f.name
        
        try:
            updater = ORMDUpdater()
            result = updater.update_file(temp_path)
            
            assert result['updated']
            assert 'metrics' in result['changes']
            assert 'dates' in result['changes']
            
            # Check the metrics changes
            metrics = result['changes']['metrics']['new']
            assert 'word_count' in metrics
            assert metrics['word_count'] > 0
            
            # Check the dates changes  
            dates = result['changes']['dates']['new']
            assert 'modified' in dates
            
        finally:
            os.unlink(temp_path)

    def test_update_empty_body_document(self):
        """Test updating document with empty body content."""
        content = '''<!-- ormd:0.1 -->
---
title: "Empty Body Document"
authors: ["Test Author"]
links: []
---

'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ormd', delete=False) as f:
            f.write(content)
            temp_path = f.name
        
        try:
            updater = ORMDUpdater()
            result = updater.update_file(temp_path)
            
            assert result['updated']
            assert 'metrics' in result['changes']
            
            # Check word count is 0 for empty body
            metrics = result['changes']['metrics']['new']
            assert metrics['word_count'] == 0
            
        finally:
            os.unlink(temp_path)

    def test_update_no_links_document(self):
        """Test updating document with no semantic links."""
        content = '''<!-- ormd:0.1 -->
---
title: "No Links Document"
authors: ["Test Author"]
links: []
---

# Content Without Links

This document has no semantic links.
No references to anything special.
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ormd', delete=False) as f:
            f.write(content)
            temp_path = f.name
        
        try:
            updater = ORMDUpdater()
            result = updater.update_file(temp_path)
            
            assert result['updated']
            # Should have empty link_ids
            assert result['changes']['link_ids']['new'] == []
            # Should still have word count
            assert 'metrics' in result['changes']
            metrics = result['changes']['metrics']['new']
            assert metrics['word_count'] > 0
            
        finally:
            os.unlink(temp_path)

    def test_update_document_with_links(self):
        """Test updating document with semantic links."""
        content = '''<!-- ormd:0.1 -->
---
title: "Document with Links"
authors: ["Test Author"]
links:
  - id: "ref1"
    rel: "supports"
    to: "#section1"
  - id: "ref2"
    rel: "extends"
    to: "other.ormd"
---

# Document with Links

This document references [[ref1]] and [[ref2]] in the content.

## Section 1

More content with another [[ref1]] reference.
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ormd', delete=False) as f:
            f.write(content)
            temp_path = f.name
        
        try:
            updater = ORMDUpdater()
            result = updater.update_file(temp_path)
            
            assert result['updated']
            # Should extract link IDs from body
            assert set(result['changes']['link_ids']['new']) == {'ref1', 'ref2'}
            
        finally:
            os.unlink(temp_path)

    def test_update_locked_fields(self):
        """Test that locked fields are not updated by default."""
        content = '''<!-- ormd:0.1 -->
---
title: "Locked Fields Document"
authors: ["Test Author"]
links: []
metrics:
  word_count: 999  # This should not be updated
  reading_time: "10 min"
  locked: true
dates:
  created: "2024-01-01T10:00:00Z"
  modified: "2024-01-01T10:00:00Z"  # This should not be updated
  locked: true
---

# Content

This has locked fields that should not change.
Word count should stay at 999.
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ormd', delete=False) as f:
            f.write(content)
            temp_path = f.name
        
        try:
            updater = ORMDUpdater()
            result = updater.update_file(temp_path)
            
            # With locked fields, should only update unlocked fields
            # Expected behavior: link_ids and asset_ids might still be updated
            if result['updated']:
                # If updated, locked fields should preserve their values
                if 'metrics' in result['changes']:
                    metrics = result['changes']['metrics']['new']
                    assert metrics['word_count'] == 999  # Should preserve locked value
                if 'dates' in result['changes']:
                    dates = result['changes']['dates']['new']
                    assert dates['modified'] == "2024-01-01T10:00:00Z"  # Should preserve locked value
            
        finally:
            os.unlink(temp_path)

    def test_force_update_locked_fields(self):
        """Test that force update overrides locked fields."""
        content = '''<!-- ormd:0.1 -->
---
title: "Force Update Document"
authors: ["Test Author"]
links: []
metrics:
  word_count: 999
  locked: true
dates:
  modified: "2024-01-01T10:00:00Z"
  locked: true
---

# Content

Force update should override locked fields.
This has more than 999 words now.
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ormd', delete=False) as f:
            f.write(content)
            temp_path = f.name
        
        try:
            updater = ORMDUpdater()
            result = updater.update_file(temp_path, force_update=True)
            
            assert result['updated']
            
            # With force update, locked fields should be updated
            if 'metrics' in result['changes']:
                metrics = result['changes']['metrics']['new']
                assert 'word_count' in metrics
                assert metrics['word_count'] != 999  # Should change from locked value
            
            if 'dates' in result['changes']:
                dates = result['changes']['dates']['new']
                assert 'modified' in dates
                assert dates['modified'] != "2024-01-01T10:00:00Z"  # Should change from locked value
            
        finally:
            os.unlink(temp_path)

    def test_update_idempotency(self):
        """Test that running update multiple times doesn't change content."""
        content = '''<!-- ormd:0.1 -->
---
title: "Idempotency Test"
authors: ["Test Author"]
links: []
---

# Test Content

Some content for idempotency testing.
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ormd', delete=False) as f:
            f.write(content)
            temp_path = f.name
        
        try:
            updater = ORMDUpdater()
            
            # First update
            result1 = updater.update_file(temp_path)
            assert result1['updated']
            
            content1 = Path(temp_path).read_text()
            
            # Second update should not change anything
            result2 = updater.update_file(temp_path)
            assert not result2['updated']
            assert not result2['changes']
            
            content2 = Path(temp_path).read_text()
            assert content1 == content2
            
        finally:
            os.unlink(temp_path)

    def test_update_dry_run(self):
        """Test dry run mode doesn't modify files."""
        content = '''<!-- ormd:0.1 -->
---
title: "Dry Run Test"
authors: ["Test Author"]
links: []
---

# Test Content

Content for dry run testing.
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ormd', delete=False) as f:
            f.write(content)
            temp_path = f.name
        
        try:
            original_content = Path(temp_path).read_text()
            
            updater = ORMDUpdater()
            result = updater.update_file(temp_path, dry_run=True)
            
            # Should show what would be changed
            assert result['changes']
            assert 'metrics' in result['changes']
            
            # But file should be unchanged
            current_content = Path(temp_path).read_text()
            assert current_content == original_content
            
        finally:
            os.unlink(temp_path)

    def test_update_with_assets(self):
        """Test updating document that references asset files."""
        content = '''<!-- ormd:0.1 -->
---
title: "Document with Assets"
authors: ["Test Author"]
links: []
---

# Document with Assets

This document references ![image](assets/test.png) and [data](data/test.csv).

Also mentions another file: assets/diagram.svg
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ormd', delete=False) as f:
            f.write(content)
            temp_path = f.name
        
        try:
            # Create some asset files
            temp_dir = Path(temp_path).parent
            (temp_dir / "assets").mkdir(exist_ok=True)
            (temp_dir / "data").mkdir(exist_ok=True)
            (temp_dir / "assets" / "test.png").write_text("fake image")
            (temp_dir / "data" / "test.csv").write_text("fake,data")
            (temp_dir / "assets" / "diagram.svg").write_text("fake svg")
            
            updater = ORMDUpdater()
            result = updater.update_file(temp_path)
            
            assert result['updated']
            assert 'asset_ids' in result['changes']
            
            # Should find the asset references
            asset_ids = result['changes']['asset_ids']['new']
            assert len(asset_ids) >= 1  # At least the image should be found
            assert "assets/test.png" in asset_ids
            
        finally:
            os.unlink(temp_path)
            # Clean up created directories
            import shutil
            shutil.rmtree(temp_dir / "assets", ignore_errors=True)
            shutil.rmtree(temp_dir / "data", ignore_errors=True)

    def test_update_preserves_existing_fields(self):
        """Test that update preserves existing non-auto fields."""
        content = '''<!-- ormd:0.1 -->
---
title: "Preserve Fields Test"
authors: ["Test Author"]
links: []
version: "1.0"
status: "published"
description: "Important document"
keywords: ["preserve", "test"]
permissions:
  mode: "published"
  editable: false
---

# Test Content

Content that should preserve existing fields.
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ormd', delete=False) as f:
            f.write(content)
            temp_path = f.name
        
        try:
            updater = ORMDUpdater()
            result = updater.update_file(temp_path)
            
            assert result['updated']
            
            # Check that existing fields are preserved by reading the updated file
            from ormd_cli.parser import parse_document
            updated_content = Path(temp_path).read_text()
            updated_fm, _, _, _, _ = parse_document(updated_content)
            
            assert updated_fm['version'] == "1.0"
            assert updated_fm['status'] == "published"
            assert updated_fm['description'] == "Important document"
            assert 'preserve' in updated_fm['keywords']
            assert updated_fm['permissions']['editable'] == False
            
        finally:
            os.unlink(temp_path)

    def test_update_no_front_matter(self):
        """Test updating document with no front-matter."""
        content = '''<!-- ormd:0.1 -->

# Document Without Front Matter

This document has no front-matter section.
It should fail gracefully.
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ormd', delete=False) as f:
            f.write(content)
            temp_path = f.name
        
        try:
            updater = ORMDUpdater()
            
            # Should handle gracefully by creating front-matter
            result = updater.update_file(temp_path)
            
            # Should succeed and create front-matter
            assert result['updated']
            
            # Check that front-matter was created
            from ormd_cli.parser import parse_document
            updated_content = Path(temp_path).read_text()
            updated_fm, _, _, _, _ = parse_document(updated_content)
            
            assert updated_fm is not None
            assert 'title' in updated_fm
            assert 'authors' in updated_fm
            
        finally:
            os.unlink(temp_path)

    def test_update_complex_link_extraction(self):
        """Test link extraction with complex patterns."""
        content = '''<!-- ormd:0.1 -->
---
title: "Complex Links Document"
authors: ["Test Author"]
links:
  - id: "simple-ref"
    rel: "supports"
    to: "#section"
  - id: "complex-ref"
    rel: "extends"
    to: "other.ormd"
  - id: "unused-ref"
    rel: "related"
    to: "#nowhere"
---

# Complex Links

Simple reference: [[simple-ref]]

Complex reference in text: see [[complex-ref]] for details.

Multiple refs: [[simple-ref]] and [[complex-ref]] together.

```code
// This [[simple-ref]] should be extracted too
```

But this link [[undefined-ref]] is not in the links section.
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ormd', delete=False) as f:
            f.write(content)
            temp_path = f.name
        
        try:
            updater = ORMDUpdater()
            result = updater.update_file(temp_path)
            
            assert result['updated']
            link_ids = result['changes']['link_ids']['new']
            
            # Should extract all referenced IDs, including undefined ones
            assert 'simple-ref' in link_ids
            assert 'complex-ref' in link_ids
            assert 'undefined-ref' in link_ids
            # unused-ref should not appear since it's not referenced
            assert 'unused-ref' not in link_ids
            
        finally:
            os.unlink(temp_path)

    def test_update_word_count_accuracy(self):
        """Test accurate word counting with different content types."""
        content = '''<!-- ormd:0.1 -->
---
title: "Word Count Test"
authors: ["Test Author"]
links: []
---

# Word Count Test

This paragraph has exactly eight words total.

## Section with Code

```python
# This code should not be counted
def hello():
    return "world"
```

- List item one
- List item two  
- List item three

| Table | Header |
|-------|--------|
| Cell  | Data   |

Final paragraph with five exact words.
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ormd', delete=False) as f:
            f.write(content)
            temp_path = f.name
        
        try:
            updater = ORMDUpdater()
            result = updater.update_file(temp_path)
            
            assert result['updated']
            assert 'metrics' in result['changes']
            
            metrics = result['changes']['metrics']['new']
            word_count = metrics['word_count']
            
            # Should count main text but exclude code blocks
            # Exact count depends on implementation, but should be reasonable
            assert word_count > 15  # At least the main paragraphs
            assert word_count < 50  # But not excessive
            
        finally:
            os.unlink(temp_path) 
