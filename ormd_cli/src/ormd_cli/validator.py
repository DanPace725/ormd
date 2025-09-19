# src/ormd_cli/validator.py
import re
import yaml
import markdown
from pathlib import Path
from typing import List, Dict, Any, Set
from .parser import parse_document
from .schema import validate_front_matter_schema

class ORMDValidator:
    def __init__(self):
        self.errors = []
        self.warnings = []
    
    def validate_file(self, file_path: str) -> bool:
        """Main validation entry point with comprehensive Phase 1 checks"""
        try:
            file_path_obj = Path(file_path)
            content = file_path_obj.read_text(encoding='utf-8')
            
            # Check version tag
            if not self._check_version_tag(content):
                return False
                
            # Parse document components using the shared parser
            front_matter, body, metadata, parse_errors = parse_document(content)
            self.errors.extend(parse_errors)
            
            # Phase 1: Required field enforcement with clear guidance
            if not self._validate_required_fields_with_guidance(front_matter):
                return False
                
            # Phase 1: YAML schema compliance with strict unknown key checking
            if not self._validate_schema_strict(front_matter):
                return False
                
            # Phase 1: Semantic link consistency checks
            if not self._validate_semantic_link_consistency(front_matter, body):
                return False
                
            # Phase 1: Asset existence checks
            if not self._validate_asset_existence(front_matter, file_path_obj.parent):
                # This check already appends to self.errors, so we just check its return
                pass # Collect all errors before returning

            # Add new checks for legacy meta blocks and multiple YAML blocks
            if front_matter is not None: # Only perform these if initial parsing was somewhat successful
                if not self._check_for_legacy_meta_blocks(body):
                    pass # Collect all errors
                if not self._check_for_multiple_yaml_blocks(body, front_matter is not None): # front_matter is not None implies it exists
                    pass # Collect all errors
                
            return len(self.errors) == 0
            
        except Exception as e:
            self.errors.append(f"Failed to read file: {e}")
            return False
    
    def _check_version_tag(self, content: str) -> bool:
        """Check for <!-- ormd:0.1 --> at start with guidance"""
        if not content.strip().startswith('<!-- ormd:0.1 -->'):
            self.errors.append("Missing or invalid version tag. Add '<!-- ormd:0.1 -->' at the top of your document.")
            return False
        return True

    def _check_for_legacy_meta_blocks(self, body: str) -> bool:
        """Checks for '+++meta' or '+++end-meta' blocks in the body."""
        if re.search(r'^[ ]*\+\+\+(meta|end-meta)\b', body, re.MULTILINE):
            self.errors.append("Error: `+++meta` or `+++end-meta` blocks are no longer supported. All metadata must be in the YAML front-matter.")
            return False
        return True

    def _check_for_multiple_yaml_blocks(self, body: str, front_matter_exists: bool) -> bool:
        """Checks for multiple YAML front-matter blocks if initial front-matter was found."""
        if front_matter_exists:
            # This regex looks for '---' or '+++' at the beginning of a line,
            # possibly with leading spaces, followed by an optional newline.
            if re.search(r'^\s*(?:---|\+\+\+)\s*$', body, re.MULTILINE):
                self.errors.append("Error: Multiple YAML front-matter blocks found. Only one is allowed at the beginning of the document.")
                return False
        return True
    
    def _validate_required_fields_with_guidance(self, front_matter: Dict[str, Any]) -> bool:
        """Phase 1: Enforce required fields with clear guidance"""
        if front_matter is None or not front_matter:
            self.errors.append("No front-matter found. Add YAML front-matter block with required fields:")
            self.errors.append("  title: Your Document Title")
            self.errors.append("  authors: [Author Name]")
            self.errors.append("  links: []")
            return False
        
        required_fields = {
            'title': "Add 'title: Your Document Title' to front-matter",
            'authors': "Add 'authors: [Author Name]' to front-matter", 
            'links': "Add 'links: []' to front-matter (empty list is acceptable)"
        }
        
        missing_fields = []
        for field, guidance in required_fields.items():
            if field not in front_matter:
                missing_fields.append(field)
                self.errors.append(f"Missing required field '{field}'. {guidance}")
        
        # Additional validation for field contents
        if 'title' in front_matter:
            title = front_matter['title']
            if not isinstance(title, str) or not title.strip():
                self.errors.append("Field 'title' must be a non-empty string. Example: title: My Document Title")
        
        if 'authors' in front_matter:
            authors = front_matter['authors']
            if not isinstance(authors, list):
                self.errors.append("Field 'authors' must be a list. Example: authors: [John Doe, jane@example.com]")
            elif len(authors) == 0:
                self.errors.append("Field 'authors' cannot be empty. Add at least one author.")
        
        if 'links' in front_matter:
            links = front_matter['links']
            if not isinstance(links, list):
                self.errors.append("Field 'links' must be a list. Example: links: [] or links: [{id: ref1, rel: supports, to: '#section'}]")
        
        return len(missing_fields) == 0
    
    def _validate_schema_strict(self, front_matter: Dict[str, Any]) -> bool:
        """Phase 1: Strict YAML schema compliance - fail fast on unknown keys"""
        if front_matter is None or not front_matter:
            return False
        
        # Define allowed keys for Phase 1 (strict mode)
        allowed_keys = {
            # Required fields
            'title', 'authors', 'links',
            # Optional organized metadata 
            'dates', 'metrics', 'permissions', 'context',
            # Optional simple fields
            'version', 'status', 'description', 'language', 'license', 'keywords',
            # Auto-populated fields (from update command)
            'link_ids', 'asset_ids'
        }
        
        # Check for unknown/extra keys
        unknown_keys = set(front_matter.keys()) - allowed_keys
        if unknown_keys:
            self.errors.append(f"Unknown fields in front-matter: {', '.join(sorted(unknown_keys))}")
            self.errors.append("Phase 1 only allows these fields: " + ', '.join(sorted(allowed_keys)))
            return False
        
        # Use existing schema validator for detailed validation
        is_valid, schema_errors = validate_front_matter_schema(front_matter)
        self.errors.extend(schema_errors)
        
        return is_valid
    
    def _validate_semantic_link_consistency(self, front_matter: Dict[str, Any], body: str) -> bool:
        """Phase 1: Validate semantic link consistency between front-matter and body"""
        if not front_matter:
            return False
        
        # Extract all [[id]] references from body
        body_link_refs = set(re.findall(r'\[\[([^\]]+)\]\]', body))
        
        # Get all defined link IDs from front-matter
        defined_link_ids = set()
        for link in front_matter.get('links', []):
            if isinstance(link, dict) and 'id' in link:
                defined_link_ids.add(link['id'])
        
        # Get link_ids if present (populated by update command)
        front_matter_link_ids = set(front_matter.get('link_ids', []))
        
        # Check 1: All [[id]] references must be defined in links
        undefined_refs = body_link_refs - defined_link_ids
        for ref in undefined_refs:
            self.errors.append(f"Undefined link reference [[{ref}]] - add definition to 'links' section or run 'ormd update' to sync")
        
        # Check 2: Warn about unused link definitions
        unused_links = defined_link_ids - body_link_refs
        for unused_id in unused_links:
            self.warnings.append(f"Link '{unused_id}' is defined but not referenced in document body")
        
        # Check 3: Validate link_ids consistency if present
        if front_matter_link_ids and body_link_refs != front_matter_link_ids:
            if body_link_refs:
                self.errors.append(f"Field 'link_ids' is outdated. Run 'ormd update' to sync with current [[id]] references")
            else:
                self.warnings.append(f"Field 'link_ids' contains references not found in body. Run 'ormd update' to sync")
        
        return len(undefined_refs) == 0
    
    def _validate_asset_existence(self, front_matter: Dict[str, Any], base_dir: Path) -> bool:
        """Phase 1: Check that all assets in asset_ids actually exist on disk"""
        if not front_matter:
            return True
        
        asset_ids = front_matter.get('asset_ids', [])
        if not asset_ids:
            return True
        
        missing_assets = []
        for asset_path in asset_ids:
            # Skip URLs and absolute paths
            if asset_path.startswith(('http://', 'https://', '/')):
                continue
            
            # Check if asset file exists relative to document directory
            full_path = base_dir / asset_path
            if not full_path.exists():
                missing_assets.append(asset_path)
                self.errors.append(f"Asset not found: {asset_path} (looked in {full_path})")
        
        if missing_assets:
            self.errors.append("Missing assets detected. Run 'ormd update' to resync asset_ids or fix asset paths.")
            return False
        
        return True
    
    def get_validation_summary(self) -> str:
        """Get a formatted summary of validation results"""
        summary = []
        
        if self.errors:
            summary.append(f"❌ Validation failed with {len(self.errors)} error(s):")
            for i, error in enumerate(self.errors, 1):
                summary.append(f"  {i}. {error}")
        
        if self.warnings:
            summary.append(f"⚠️  {len(self.warnings)} warning(s):")
            for i, warning in enumerate(self.warnings, 1):
                summary.append(f"  {i}. {warning}")
        
        if not self.errors and not self.warnings:
            summary.append("✅ Document is valid ORMD 0.1")
        
        return '\n'.join(summary)