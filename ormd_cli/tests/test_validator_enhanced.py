"""Tests for enhanced ORMD validator functionality.

These tests cover the comprehensive Phase 1 validation checks:
- Required field enforcement with clear guidance
- Semantic link consistency
- Asset existence checks  
- Strict YAML schema compliance
"""

import pytest
import tempfile
import os
from pathlib import Path
from ormd_cli.validator import ORMDValidator


class TestEnhancedValidator:
    """Test the enhanced ORMD validator functionality."""

    def test_missing_version_tag_guidance(self):
        """Test clear guidance for missing version tag."""
        content = '''---
title: "Test Document"
authors: ["Test Author"]
links: []
---

# Test

Content here.
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ormd', delete=False) as f:
            f.write(content)
            temp_path = f.name
        
        try:
            validator = ORMDValidator()
            result = validator.validate_file(temp_path)
            
            assert not result
            assert any("Add '<!-- ormd:0.1 -->' at the top" in error for error in validator.errors)
            
        finally:
            os.unlink(temp_path)

    def _create_test_file_content(self, fm_dict: dict, body_md: str) -> str:
        """Helper to create ORMD file content string for validator tests."""
        # Assuming serialize_front_matter is available or front_matter is pre-serialized
        # For simplicity, let's assume fm_dict is directly convertible to YAML string lines
        # This helper is simplified for direct string construction in tests
        fm_lines = ["---"]
        if fm_dict:
            for key, value in fm_dict.items():
                if isinstance(value, list) and key == "links": # Special handling for links list
                    fm_lines.append(f"{key}:")
                    for item in value:
                        # Ensure string values within link items are quoted
                        item_parts = []
                        for k,v_item in item.items():
                            if isinstance(v_item, str):
                                item_parts.append(f"{k}: \"{v_item}\"")
                            else: # numbers, booleans, nulls (None)
                                item_parts.append(f"{k}: {str(v_item).lower() if isinstance(v_item, bool) else v_item}")
                        fm_lines.append(f"  - {{{', '.join(item_parts)}}}")
                elif isinstance(value, list):
                    authors_list = [f"\"{a}\"" if isinstance(a, str) else str(a) for a in value] # Quote string authors
                    fm_lines.append(f"{key}: [{', '.join(authors_list)}]")
                elif isinstance(value, str):
                    fm_lines.append(f"{key}: \"{value}\"")
                else:
                    fm_lines.append(f"{key}: {value}")
        fm_lines.append("---")
        fm_string = "\n".join(fm_lines)
        return f"<!-- ormd:0.1 -->\n{fm_string}\n\n{body_md}"

    # --- Tests for Target Validation ---
    def test_valid_internal_anchor_slugified_heading(self, tmp_path):
        validator = ORMDValidator()
        content = self._create_test_file_content(
            {"title": "Test", "authors": ["Auth"], "links": [{"id": "l1", "to": "#my-heading", "rel": "cites"}]},
            "# My Heading\nSome text."
        )
        file_path = tmp_path / "test.ormd"
        file_path.write_text(content)
        assert validator.validate_file(str(file_path))
        assert not validator.errors

    def test_invalid_internal_anchor_not_found(self, tmp_path):
        validator = ORMDValidator()
        content = self._create_test_file_content(
            {"title": "Test", "authors": ["Auth"], "links": [{"id": "l1", "to": "#non-existent", "rel": "cites"}]},
            "# My Heading\nSome text."
        )
        file_path = tmp_path / "test.ormd"
        file_path.write_text(content)
        assert validator.validate_file(str(file_path))
        assert any("points to an internal target '#non-existent' that was not found" in warning for warning in validator.warnings)

    def test_valid_internal_anchor_custom_id_heading(self, tmp_path):
        validator = ORMDValidator()
        content = self._create_test_file_content(
            {"title": "Test", "authors": ["Auth"], "links": [{"id": "l1", "to": "#custom", "rel": "cites"}]},
            "# My Heading {#custom}\nSome text."
        )
        file_path = tmp_path / "test.ormd"
        file_path.write_text(content)
        assert validator.validate_file(str(file_path))
        assert not validator.errors

    def test_valid_internal_anchor_html_id(self, tmp_path):
        validator = ORMDValidator()
        content = self._create_test_file_content(
            {"title": "Test", "authors": ["Auth"], "links": [{"id": "l1", "to": "#html-id", "rel": "cites"}]},
            '<div id="html-id">Content</div>'
        )
        file_path = tmp_path / "test.ormd"
        file_path.write_text(content)
        assert validator.validate_file(str(file_path))
        assert not validator.errors
        
    def test_valid_external_url(self, tmp_path):
        validator = ORMDValidator()
        content = self._create_test_file_content(
            {"title": "Test", "authors": ["Auth"], "links": [{"id": "l1", "to": "https://example.com/page?q=1", "rel": "references"}]},
            "Body text."
        )
        file_path = tmp_path / "test.ormd"
        file_path.write_text(content)
        assert validator.validate_file(str(file_path))
        assert not validator.errors

    def test_invalid_external_url_malformed(self, tmp_path):
        validator = ORMDValidator()
        content = self._create_test_file_content(
            {"title": "Test", "authors": ["Auth"], "links": [{"id": "l1", "to": "htp:/badurl", "rel": "references"}]},
            "Body text."
        )
        file_path = tmp_path / "test.ormd"
        file_path.write_text(content)
        assert not validator.validate_file(str(file_path))
        assert any("has a malformed external URL: 'htp:/badurl'" in err for err in validator.errors)

    # --- Test for Relationship Validation ---
    def test_link_rel_validation_valid_and_invalid(self, tmp_path):
        validator = ORMDValidator()
        content = self._create_test_file_content(
            {"title": "Test", "authors": ["Auth"], "links": [
                {"id": "l1", "to": "#h1", "rel": "supports"}, # Valid
                {"id": "l2", "to": "#h1", "rel": "invalid_rel_type"}  # Invalid
            ]},
            "# H1"
        )
        file_path = tmp_path / "test.ormd"
        file_path.write_text(content)
        assert not validator.validate_file(str(file_path))
        assert any("uses an unapproved relationship type: 'invalid_rel_type'" in err for err in validator.errors)
        assert not any("uses an unapproved relationship type: 'supports'" in err for err in validator.errors)

    # --- Tests for [[link-id]] Validation ---
    def test_defined_link_id_reference_manual_and_auto(self, tmp_path):
        """ Test [[id]] references to manual and (merged) auto-links. """
        validator = ORMDValidator()
        # Simulate that 'auto-link-1' was an inline link merged into front-matter by updater
        # Validator works on the front-matter's 'links' + auto_links from current parse for merged_links
        content = self._create_test_file_content(
            {"title": "Test", "authors": ["Auth"], "links": [
                {"id": "manual1", "to": "#h1", "rel": "cites", "source": "manual"},
            ]},
            "# H1\n[[manual1]]\n[auto link display text](https://example.com 'references')\n[[auto-link-1]]"
        )
        # For this test, validator runs on this content.
        # parse_document will produce auto_links = [{"id": "auto-link-1", ...}]
        # merged_links_for_validation will contain both manual1 and auto-link-1.
        file_path = tmp_path / "test.ormd"
        file_path.write_text(content)
        assert validator.validate_file(str(file_path), legacy_links_mode=False)
        print(validator.errors) # For debugging if it fails
        assert not validator.errors # Both [[manual1]] and [[auto-link-1]] should be resolved

    def test_undefined_link_id_reference(self, tmp_path):
        validator = ORMDValidator()
        content = self._create_test_file_content(
            {"title": "Test", "authors": ["Auth"], "links": []},
            "[[undefined]]"
        )
        file_path = tmp_path / "test.ormd"
        file_path.write_text(content)
        assert not validator.validate_file(str(file_path), legacy_links_mode=False)
        assert any("Body reference [[undefined]] does not correspond to any defined link" in err for err in validator.errors)

    def test_unused_link_definition_warning(self, tmp_path):
        validator = ORMDValidator()
        content = self._create_test_file_content(
            {"title": "Test", "authors": ["Auth"], "links": [
                {"id": "unused1", "to": "#h", "rel": "cites", "source": "manual"}
            ]},
            "# H\nBody text without reference to unused1.\n[another link](target 'rel')"
            # auto-link-1 will also be defined but unused by [[...]]
        )
        file_path = tmp_path / "test.ormd"
        file_path.write_text(content)
        assert validator.validate_file(str(file_path)) # Should be valid
        assert any("Link definition 'unused1' (source: manual) is not used" in w for w in validator.warnings)
        assert any("Link definition 'auto-link-1' (source: inline) is not used" in w for w in validator.warnings)

    # --- Tests for --legacy-links Mode ---
    def test_legacy_links_mode_undefined_link_id(self, tmp_path):
        validator = ORMDValidator()
        content = self._create_test_file_content(
            {"title": "Test", "authors": ["Auth"], "links": []}, # No manual links
            "[[ref-in-body]]\n[this is an inline link](target)." 
            # In legacy mode, [[ref-in-body]] is undefined because 'this is an inline link' is not considered for resolving it.
        )
        file_path = tmp_path / "test.ormd"
        file_path.write_text(content)
        # Validation should fail because [[ref-in-body]] is not defined in front-matter.
        # The inline link [this is an inline link](target) is ignored for [[...]] resolution in legacy.
        assert not validator.validate_file(str(file_path), legacy_links_mode=True)
        assert any("Body reference [[ref-in-body]] does not correspond to any defined link in front-matter (legacy mode)" in err for err in validator.errors)

    def test_legacy_links_mode_target_validation_on_manual_links(self, tmp_path):
        validator = ORMDValidator()
        content = self._create_test_file_content(
            {"title": "Test", "authors": ["Auth"], "links": [
                {"id": "m1", "to": "#non-existent-manual", "rel": "cites"}
            ]},
            "[[m1]]\n[inline link](target)."
        )
        file_path = tmp_path / "test.ormd"
        file_path.write_text(content)
        # Should fail because manual link m1 points to non-existent target.
        # In legacy_links_mode=True, the logic in validate_file for merging links
        # only adds manual links to merged_links_for_validation.
        # So, the inline link 'auto-link-1' is not in merged_links_for_validation and thus not validated.
        assert not validator.validate_file(str(file_path), legacy_links_mode=True)
        assert any("Link 'm1' (source: manual) points to an internal target '#non-existent-manual' that was not found" in err for err in validator.errors)
        # Ensure no errors about the inline link's target, as it shouldn't be in merged_links for validation in legacy.
        assert not any("auto-link-1" in err for err in validator.errors)

    def test_missing_required_fields_guidance(self):
        """Test clear guidance for missing required fields."""
        content = '''<!-- ormd:0.1 -->
---
description: "Missing required fields"
---

# Test

Content here.
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ormd', delete=False) as f:
            f.write(content)
            temp_path = f.name
        
        try:
            validator = ORMDValidator()
            result = validator.validate_file(temp_path)
            
            assert not result
            assert any("title: Your Document Title" in error for error in validator.errors)
            assert any("authors: [Author Name]" in error for error in validator.errors)
            assert any("links: []" in error for error in validator.errors)
            
        finally:
            os.unlink(temp_path)

    def test_no_front_matter_guidance(self):
        """Test guidance when front-matter is completely missing."""
        content = '''<!-- ormd:0.1 -->

# Test Document

No front-matter at all.
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ormd', delete=False) as f:
            f.write(content)
            temp_path = f.name
        
        try:
            validator = ORMDValidator()
            result = validator.validate_file(temp_path)
            
            assert not result
            assert any("No front-matter found" in error for error in validator.errors)
            assert any("title: Your Document Title" in error for error in validator.errors)
            
        finally:
            os.unlink(temp_path)

    def test_strict_schema_unknown_fields(self):
        """Test that unknown fields are rejected in Phase 1."""
        content = '''<!-- ormd:0.1 -->
---
title: "Test Document"
authors: ["Test Author"]
links: []
custom_field: "Not allowed"
another_unknown: 123
---

# Test

Content here.
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ormd', delete=False) as f:
            f.write(content)
            temp_path = f.name
        
        try:
            validator = ORMDValidator()
            result = validator.validate_file(temp_path)
            
            assert not result
            assert any("Unknown fields" in error for error in validator.errors)
            assert any("custom_field" in error for error in validator.errors)
            assert any("another_unknown" in error for error in validator.errors)
            assert any("Phase 1 only allows these fields" in error for error in validator.errors)
            
        finally:
            os.unlink(temp_path)

    def test_semantic_link_consistency_undefined_refs(self):
        """Test detection of undefined link references."""
        content = '''<!-- ormd:0.1 -->
---
title: "Test Document"
authors: ["Test Author"]
links:
  - id: "defined-link"
    rel: "supports"
    to: "#section"
---

# Test Document

This references [[defined-link]] which is good.
But this references [[undefined-link]] which is bad.
And this references [[another-undefined]] which is also bad.
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ormd', delete=False) as f:
            f.write(content)
            temp_path = f.name
        
        try:
            validator = ORMDValidator()
            result = validator.validate_file(temp_path)
            
            assert not result
            assert any("Undefined link reference [[undefined-link]]" in error for error in validator.errors)
            assert any("Undefined link reference [[another-undefined]]" in error for error in validator.errors)
            # Should not complain about defined-link
            assert not any("[[defined-link]]" in error for error in validator.errors)
            
        finally:
            os.unlink(temp_path)

    def test_semantic_link_consistency_unused_definitions(self):
        """Test warnings for unused link definitions."""
        content = '''<!-- ormd:0.1 -->
---
title: "Test Document"
authors: ["Test Author"]
links:
  - id: "used-link"
    rel: "supports"
    to: "#section"
  - id: "unused-link"
    rel: "supports"
    to: "#other"
---

# Test Document

This references [[used-link]] but not the other one.
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ormd', delete=False) as f:
            f.write(content)
            temp_path = f.name
        
        try:
            validator = ORMDValidator()
            result = validator.validate_file(temp_path)
            
            assert result  # Should pass validation
            assert any("unused-link" in warning for warning in validator.warnings)
            assert any("defined but not referenced" in warning for warning in validator.warnings)
            
        finally:
            os.unlink(temp_path)

    def test_link_ids_consistency_outdated(self):
        """Test detection of outdated link_ids field."""
        content = '''<!-- ormd:0.1 -->
---
title: "Test Document"
authors: ["Test Author"]
links:
  - id: "current-link"
    rel: "supports"
    to: "#section"
link_ids: ["old-link", "another-old"]
---

# Test Document

This references [[current-link]] which is different from link_ids.
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ormd', delete=False) as f:
            f.write(content)
            temp_path = f.name
        
        try:
            validator = ORMDValidator()
            result = validator.validate_file(temp_path)
            
            assert not result  # Should fail due to undefined current-link
            assert any("link_ids' is outdated" in error for error in validator.errors)
            assert any("ormd update" in error for error in validator.errors)
            
        finally:
            os.unlink(temp_path)

    def test_asset_existence_missing_files(self):
        """Test detection of missing asset files."""
        content = '''<!-- ormd:0.1 -->
---
title: "Test Document"
authors: ["Test Author"]
links: []
asset_ids:
  - "assets/existing.png"
  - "assets/missing.pdf"
  - "data/nonexistent.csv"
---

# Test Document

References to assets.
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ormd', delete=False) as f:
            f.write(content)
            temp_path = f.name
        
        try:
            # Create one of the asset files
            temp_dir = Path(temp_path).parent
            assets_dir = temp_dir / "assets"
            assets_dir.mkdir(exist_ok=True)
            (assets_dir / "existing.png").write_text("fake image")
            
            validator = ORMDValidator()
            result = validator.validate_file(temp_path)
            
            assert not result
            assert any("Asset not found: assets/missing.pdf" in error for error in validator.errors)
            assert any("Asset not found: data/nonexistent.csv" in error for error in validator.errors)
            # Should not complain about existing.png
            assert not any("existing.png" in error for error in validator.errors)
            assert any("Run 'ormd update' to resync" in error for error in validator.errors)
            
        finally:
            os.unlink(temp_path)
            # Clean up created directories
            if assets_dir.exists():
                (assets_dir / "existing.png").unlink()
                assets_dir.rmdir()

    def test_asset_existence_skips_urls(self):
        """Test that URL assets are skipped in existence checks."""
        content = '''<!-- ormd:0.1 -->
---
title: "Test Document"
authors: ["Test Author"]
links: []
asset_ids:
  - "https://example.com/remote.png"
  - "http://example.com/other.pdf"
  - "/absolute/path/file.txt"
---

# Test Document

References to remote and absolute assets.
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ormd', delete=False) as f:
            f.write(content)
            temp_path = f.name
        
        try:
            validator = ORMDValidator()
            result = validator.validate_file(temp_path)
            
            assert result  # Should pass - URLs and absolute paths are skipped
            assert not validator.errors
            
        finally:
            os.unlink(temp_path)

    def test_malformed_field_types_guidance(self):
        """Test helpful guidance for malformed field types."""
        content = '''<!-- ormd:0.1 -->
---
title: 123  # Should be string
authors: "Single Author"  # Should be list
links: "not a list"  # Should be list
---

# Test

Content here.
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ormd', delete=False) as f:
            f.write(content)
            temp_path = f.name
        
        try:
            validator = ORMDValidator()
            result = validator.validate_file(temp_path)
            
            assert not result
            assert any("title: My Document Title" in error for error in validator.errors)
            assert any("authors: [John Doe, jane@example.com]" in error for error in validator.errors)
            assert any("links: []" in error for error in validator.errors)
            
        finally:
            os.unlink(temp_path)

    def test_validation_summary_formatting(self):
        """Test the validation summary formatting."""
        content = '''<!-- ormd:0.1 -->
---
title: "Test Document"
authors: ["Test Author"]
links:
  - id: "unused-link"
    rel: "supports"
    to: "#section"
unknown_field: "not allowed"
---

# Test Document

No link references, so unused-link will be warned about.
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ormd', delete=False) as f:
            f.write(content)
            temp_path = f.name
        
        try:
            validator = ORMDValidator()
            result = validator.validate_file(temp_path)
            
            summary = validator.get_validation_summary()
            
            assert "❌ Validation failed" in summary
            assert "error(s):" in summary
            assert "Unknown fields" in summary
            
        finally:
            os.unlink(temp_path)

    def test_valid_document_with_warnings(self):
        """Test valid document that generates warnings."""
        content = '''<!-- ormd:0.1 -->
---
title: "Test Document"
authors: ["Test Author"]
links:
  - id: "unused-link"
    rel: "supports"
    to: "#section"
---

# Test Document

Valid document but with an unused link definition.
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ormd', delete=False) as f:
            f.write(content)
            temp_path = f.name
        
        try:
            validator = ORMDValidator()
            result = validator.validate_file(temp_path)
            
            assert result  # Should pass validation
            assert len(validator.warnings) > 0
            assert len(validator.errors) == 0
            
            summary = validator.get_validation_summary()
            assert "⚠️" in summary
            assert "warning(s):" in summary
            assert "unused-link" in summary
            
        finally:
            os.unlink(temp_path)

    def test_perfect_valid_document(self):
        """Test perfectly valid document with no warnings."""
        content = '''<!-- ormd:0.1 -->
---
title: "Perfect Document"
authors: ["Test Author"]
links:
  - id: "used-link"
    rel: "supports"
    to: "#section"
---

# Perfect Document

This references [[used-link]] properly.
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ormd', delete=False) as f:
            f.write(content)
            temp_path = f.name
        
        try:
            validator = ORMDValidator()
            result = validator.validate_file(temp_path)
            
            assert result
            assert len(validator.errors) == 0
            assert len(validator.warnings) == 0
            
            summary = validator.get_validation_summary()
            assert "✅ Document is valid ORMD 0.1" in summary
            
        finally:
            os.unlink(temp_path)

    def test_validate_invalid_legacy_meta_fixture(self):
        """Test validator fails document with legacy +++meta block."""
        # Create a temporary file with content from the fixture
        fixture_path = Path(__file__).parent / "fixtures" / "invalid_legacy_meta.ormd"
        content = fixture_path.read_text(encoding='utf-8')

        with tempfile.NamedTemporaryFile(mode='w', suffix='.ormd', delete=False) as f:
            f.write(content)
            temp_path = f.name

        try:
            validator = ORMDValidator()
            result = validator.validate_file(temp_path)

            assert not result
            assert any("`+++meta` or `+++end-meta` blocks are no longer supported" in error for error in validator.errors)
        finally:
            os.unlink(temp_path)

    def test_validate_invalid_multiple_yaml_fixture(self):
        """Test validator fails document with multiple YAML blocks."""
        fixture_path = Path(__file__).parent / "fixtures" / "invalid_multiple_yaml.ormd"
        content = fixture_path.read_text(encoding='utf-8')

        with tempfile.NamedTemporaryFile(mode='w', suffix='.ormd', delete=False) as f:
            f.write(content)
            temp_path = f.name

        try:
            validator = ORMDValidator()
            result = validator.validate_file(temp_path)

            assert not result
            assert any("Multiple YAML front-matter blocks found" in error for error in validator.errors)
        finally:
            os.unlink(temp_path)
