# src/ormd_cli/validator.py
import re
import yaml
import markdown # Keep for potential future use with TOC extension for anchors
from pathlib import Path
from typing import List, Dict, Any, Set, Tuple, Optional
from .parser import parse_document, _body_has_additional_front_matter_block
from .schema import validate_front_matter_schema, APPROVED_LINK_RELATIONSHIPS
from .utils import SYMBOLS


class ORMDValidator:
    def __init__(self):
        self.errors = []
        self.warnings = []

    def _slugify(self, text: str) -> str:
        """Converts text to a slug format for anchor IDs."""
        if text is None: return ""
        text = str(text).lower()
        text = re.sub(r'\s+', '-', text)  # Replace spaces with hyphens
        text = re.sub(r'[^\w\-]', '', text)  # Remove non-alphanumeric characters except hyphens
        return text

    def validate_file(
        self,
        file_path: str,
        legacy_links_mode: bool = False,
        check_external_links: bool = False,
    ) -> bool:
        """Main validation entry point with comprehensive Phase 1 checks"""
        try:
            file_path_obj = self._resolve_file_path(file_path)
            if not file_path_obj.exists():
                self.errors.append(f"Failed to read file {file_path}: file not found")
                return False
            content = file_path_obj.read_text(encoding='utf-8')
            
            # Check version tag
            if not self._check_version_tag(content):
                # self.errors already populated
                pass # Continue to collect all errors
                
            # Parse document components using the shared parser
            # Now returns: front_matter, body, metadata, auto_links, parse_errors
            front_matter, body, metadata, auto_links, parse_errors = parse_document(content)
            if parse_errors: # Errors from initial parsing (e.g. bad YAML, missing version)
                self.errors.extend(parse_errors)
                # If basic parsing fails significantly, further validation might be unreliable
                if "Missing or invalid version tag" in str(parse_errors) or "Invalid YAML" in str(parse_errors):
                    return False 
            
            # Ensure front_matter is a dict for subsequent operations, even if it was None
            if front_matter is None:
                front_matter = {}

            # --- Link Merging for Validation ---
            merged_links_for_validation: List[Dict[str, Any]] = []
            manual_link_tuples: Set[Tuple[Optional[str], Optional[str]]] = set()
            manual_link_tos: Set[Optional[str]] = set()

            # Process manual links from front-matter
            fm_links = front_matter.get('links', [])
            if not isinstance(fm_links, list): # Handle malformed 'links' field
                self.errors.append(f"Front-matter 'links' field must be a list, but found type {type(fm_links)}. Skipping link validation for front-matter links.")
                fm_links = []

            for idx, m_link in enumerate(fm_links):
                if not isinstance(m_link, dict):
                    self.errors.append(f"Manual link at index {idx} is not a dictionary. Skipping this link.")
                    continue
                
                link_to_add = m_link.copy() # Avoid modifying original front_matter dicts
                link_to_add['source'] = 'manual'
                # Ensure 'id' exists for consistent access, even if it's from schema validation later
                if 'id' not in link_to_add:
                     # Schema should catch missing IDs for manual links, but provide a placeholder for merging if absent
                    link_to_add['id'] = f"manual-link-no-id-{idx}"
                    self.warnings.append(f"Manual link '{link_to_add.get('to', 'N/A')}' is missing an 'id'. Schema validation should catch this.")

                merged_links_for_validation.append(link_to_add)
                manual_link_tuples.add((link_to_add.get('to'), link_to_add.get('rel')))
                manual_link_tos.add(link_to_add.get('to'))
            
            # Process auto-generated inline links
            if not legacy_links_mode:
                processed_auto_targets_rels = set(manual_link_tuples) # Avoid re-adding if already covered by manual
                for auto_link in auto_links: # auto_links already have id, text, target, rel, source
                    auto_link_tuple = (auto_link.get('target'), auto_link.get('rel'))
                    
                    if auto_link_tuple in processed_auto_targets_rels:
                        # This auto-link is a duplicate of an existing manual link or already added auto-link
                        continue 
                    
                    # Remap auto_link keys to be consistent with 'to' for target
                    consistent_auto_link = auto_link.copy()
                    consistent_auto_link['to'] = consistent_auto_link.pop('target')


                    if consistent_auto_link['to'] in manual_link_tos:
                        # Conflict: same target, different relationship or manual has no rel
                        self.warnings.append(
                            f"Warning: Auto-generated link {consistent_auto_link['id']} for target "
                            f"'{consistent_auto_link['to']}' with relationship '{consistent_auto_link.get('rel')}' conflicts with an "
                            f"existing manual link with a different relationship. Both will be validated."
                        )
                    
                    merged_links_for_validation.append(consistent_auto_link)
                    processed_auto_targets_rels.add(auto_link_tuple) # Add to set to handle duplicate auto-links
            # --- End Link Merging ---

            # Phase 1: Required field enforcement with clear guidance
            self._validate_required_fields_with_guidance(front_matter)
                
            # Phase 1: YAML schema compliance with strict unknown key checking
            self._validate_schema_strict(front_matter)
                
            # Phase 1: Comprehensive Link Validation (New Method)
            self._validate_all_links(merged_links_for_validation, body, legacy_links_mode, front_matter)
                
            # Phase 1: Asset existence checks
            self._validate_asset_existence(front_matter, file_path_obj.parent)
            # This check already appends to self.errors, so continue collecting errors.

            # Add new checks for legacy meta blocks and multiple YAML blocks
            if front_matter is not None: # Only perform these if initial parsing was somewhat successful
                self._check_for_legacy_meta_blocks(body) # Already appends to self.errors
                # front_matter_exists for _check_for_multiple_yaml_blocks is true if a front-matter
                # delimiter appears near the top or the parsed front-matter has content.
                original_fm_existed = any(line.strip() in ["---", "+++"] for line in content.splitlines()[:5]) or bool(front_matter)
                self._check_for_multiple_yaml_blocks(body, original_fm_existed) # Already appends to self.errors

            if check_external_links:
                self.warnings.append("External link checking is not implemented yet.")
                
            return len(self.errors) == 0
            
        except Exception as e:
            self.errors.append(f"Critical validation error in file {file_path}: {e}")
            return False

    def _resolve_file_path(self, file_path: str) -> Path:
        """Resolve paths used from either repo root or the package test root."""
        path = Path(file_path)
        if path.exists() or path.is_absolute():
            return path

        package_root = Path(__file__).resolve().parents[2]
        repo_root = Path(__file__).resolve().parents[3]
        candidates = [
            Path.cwd() / path,
            package_root / path,
            repo_root / path,
        ]

        parts = path.parts
        if parts and parts[0] == "ormd_cli":
            candidates.append(package_root / Path(*parts[1:]))
        if len(parts) >= 3 and parts[:3] == ("ormd_cli", "tests", "fixtures"):
            candidates.append(repo_root / "tests" / "fixtures" / path.name)

        for candidate in candidates:
            if candidate.exists():
                return candidate
        return path
    
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
            if _body_has_additional_front_matter_block(body):
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
    
    
    def _validate_all_links(self, merged_links: List[Dict[str, Any]], body: str, legacy_links_mode: bool, front_matter: Dict[str, Any]) -> bool:
        """Validates all aspects of merged (manual + auto) links."""
        initial_error_count = len(self.errors)

        # --- Target Validation (Internal Anchors) ---
        heading_anchors: Set[str] = set()
        # Regex for Markdown headings: # Heading Title
        for match in re.finditer(r"^(#+)\s+(.*)", body, re.MULTILINE):
            heading_text = match.group(2).strip()
            # Remove any trailing {#custom-id} from heading text before slugifying
            heading_text = re.sub(r'\s*\{#([^\}]+)\}\s*$', '', heading_text)
            if heading_text:
                heading_anchors.add(self._slugify(heading_text))
            # Also capture explicit {#custom-id} if present
            custom_id_match = re.search(r'\{#([^\}]+)\}\s*$', match.group(2))
            if custom_id_match:
                heading_anchors.add(custom_id_match.group(1))


        # Regex for HTML anchors: <a name="foo">, <a id="foo">, <tag id="foo">
        # Simplified to catch common id attributes
        for match in re.finditer(r'<[^>\s]+\s(?:name|id)=["\']([^"\']+)["\']', body, re.IGNORECASE):
            heading_anchors.add(match.group(1))

        body_refs = set(re.findall(r'\[\[([^\]]+)\]\]', body))
        
        # --- Iterate Merged Links for Target, Rel, and other validations ---
        defined_link_ids_from_merged = set()
        for link in merged_links:
            link_id = link.get('id', f"unknown-link-to-{link.get('to','N/A')}") # Use 'to' if id is missing
            defined_link_ids_from_merged.add(link_id) # Collect all defined IDs

            link_target = link.get('to')
            link_rel = link.get('rel')

            if not link_target: # Target ('to') is essential
                self.errors.append(f"Link '{link_id}' (source: {link.get('source')}) is missing a 'to' target.")
                continue

            # Internal Target Validation
            if isinstance(link_target, str) and link_target.startswith('#'):
                target_anchor = link_target[1:]
                if not target_anchor: # Handles case like "links: [{to: "#"}]"
                     self.errors.append(f"Link '{link_id}' (source: {link.get('source')}) has an empty internal target '#'.")
                elif target_anchor not in heading_anchors:
                    message = f"Link '{link_id}' (source: {link.get('source')}) points to an internal target '{link_target}' that was not found in the document. Found anchors: {heading_anchors if heading_anchors else 'None'}"
                    if legacy_links_mode and link.get('source') == 'manual':
                        self.errors.append(message)
                    elif link_id not in body_refs:
                        self.warnings.append(message)
            # External Target Validation
            elif isinstance(link_target, str) and (link_target.startswith('http://') or link_target.startswith('https://')):
                if not re.match(r'^https?://[^\s/$.?#].[^\s]*$', link_target):
                    self.errors.append(f"Link '{link_id}' (source: {link.get('source')}) has a malformed external URL: '{link_target}'.")
            elif isinstance(link_target, str) and re.match(r'^[A-Za-z][A-Za-z0-9+.-]*:', link_target):
                self.errors.append(f"Link '{link_id}' (source: {link.get('source')}) has a malformed external URL: '{link_target}'.")
            # Other target types (e.g., file paths) are not explicitly validated here yet

            # Relationship Validation
            if link_rel is not None and link_rel not in APPROVED_LINK_RELATIONSHIPS:
                self.errors.append(f"Link '{link_id}' (source: {link.get('source')}) uses an unapproved relationship type: '{link_rel}'. Approved types: {APPROVED_LINK_RELATIONSHIPS}.")

        # --- [[link-id]] Body References Validation ---
        for ref_id in body_refs:
            if ref_id not in defined_link_ids_from_merged:
                if not legacy_links_mode:
                    self.errors.append(f"Undefined link reference [[{ref_id}]]. Body reference [[{ref_id}]] does not correspond to any defined link (manual from front-matter or auto-generated inline link); add definition to 'links' section.")
                else: # legacy_links_mode is True
                    # In legacy mode, auto-links are not considered for resolving [[id]] unless they were merged into front-matter (which they aren't, by definition of legacy mode)
                    # So, check only against manual links' IDs (which are already in defined_link_ids_from_merged if they had an ID)
                    manual_link_ids = {l.get('id') for l in merged_links if l.get('source') == 'manual' and l.get('id')}
                    if ref_id not in manual_link_ids:
                         self.errors.append(f"Undefined link reference [[{ref_id}]]. Body reference [[{ref_id}]] does not correspond to any defined link in front-matter (legacy mode); add definition to 'links' section.")


        # --- Unused Link Definitions Validation ---
        # Compare IDs from merged_links against body_refs
        for link in merged_links:
            defined_id = link.get('id')
            # Ensure we only warn for links that actually have an ID and are meant to be referenceable
            if defined_id and not defined_id.startswith("manual-link-no-id-") and defined_id not in body_refs:
                self.warnings.append(f"Link definition '{defined_id}' (source: {link.get('source', 'unknown')}) is not used; defined but not referenced in the document body via [[{defined_id}]] (to: {link.get('to', 'N/A')}).")

        # --- Consistency of 'link_ids' field in front-matter (if it exists) ---
        # This is more of a "linter" warning for the 'link_ids' field itself if present.
        if 'link_ids' in front_matter: # Check if the key exists
            front_matter_link_ids_field = front_matter.get('link_ids', [])
            if not isinstance(front_matter_link_ids_field, list):
                self.warnings.append(f"Front-matter field 'link_ids' should be a list, but found {type(front_matter_link_ids_field)}. Consider running 'ormd update'.")
            else:
                # In legacy_links_mode, body_refs might be considered against front_matter_link_ids only.
                # If not legacy_links_mode, body_refs includes [[id]] from inline links which are not in 'link_ids' field.
                # The 'link_ids' field is supposed to reflect [[references]] that *could* be defined in front-matter's 'links' section.
                # A simple check: if 'link_ids' exists, it should be a subset of body_refs if we are strict, or equal if perfectly synced.
                # For now, a softer warning: if link_ids exists and doesn't match body_refs, suggest update.
                # This mostly replicates part of the old _validate_semantic_link_consistency check for the 'link_ids' field.
                if set(front_matter_link_ids_field) != body_refs:
                     self.errors.append(f"Front-matter field 'link_ids' is outdated or inconsistent with [[references]] in the body. Consider running 'ormd update'.")

        return len(self.errors) == initial_error_count


    def _validate_asset_existence(self, front_matter: Dict[str, Any], base_dir: Path) -> bool:
        """Phase 1: Check that all assets in asset_ids actually exist on disk"""
        # This method remains largely the same, but ensure it's called correctly
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
            summary.append(f"{SYMBOLS['error']} Validation failed with {len(self.errors)} error(s):")
            for i, error in enumerate(self.errors, 1):
                summary.append(f"  {i}. {error}")
        
        if self.warnings:
            summary.append(f"{SYMBOLS['warning']}  {len(self.warnings)} warning(s):")
            for i, warning in enumerate(self.warnings, 1):
                summary.append(f"  {i}. {warning}")
        
        if not self.errors and not self.warnings:
            summary.append(f"{SYMBOLS['success']} Document is valid ORMD 0.1")
        
        return '\n'.join(summary)
