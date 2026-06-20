"""ORMD Front-matter Updater

This module provides functionality to automatically update and sync
front-matter fields in ORMD documents.
"""

import re
import yaml
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Set, Any, Tuple, Optional
from .parser import parse_document, serialize_front_matter
from .logger import logger

class ORMDUpdater:
    """Updates and syncs front-matter metadata in ORMD documents."""
    
    def __init__(self):
        # self.changes = {} # Changes are now managed per-file update
        pass
    
    def update_file(self, file_path: str, dry_run: bool = False, 
                   force_update: bool = False, verbose: bool = False, # verbose is not used yet
                   legacy_links_mode: bool = False) -> Dict[str, Any]:
        """Update a single ORMD file's front-matter.
        
        Args:
            file_path: Path to the ORMD file
            dry_run: If True, show what would be updated without making changes
            force_update: If True, update even locked fields
            verbose: If True, provide detailed output (currently not used)
            legacy_links_mode: If True, skip merging auto-generated links
            
        Returns:
            Dict with keys: 'updated', 'changes', 'errors'
        """
        file_path = Path(file_path)
        made_changes = False
        changes: Dict[str, Any] = {}

        if not file_path.exists():
            # This should ideally be logged or returned as an error in the dict
            # For now, let it raise FileNotFoundError as per original behavior
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # Read and parse the document
        content = file_path.read_text(encoding='utf-8')
        # parse_document now returns: front_matter, body, metadata, auto_links, errors
        front_matter, body, metadata, auto_links, parse_errors = parse_document(content)
        
        if parse_errors:
            # This also might be better handled by returning an error in the dict
            raise ValueError(f"Parse errors in {file_path}: {'; '.join(parse_errors)}")
        
        if front_matter is None: # Should be an empty dict if no FM according to parser
            front_matter = {}

        original_front_matter = {k: v for k, v in front_matter.items()} # Deep enough copy for this use case

        # --- Link Merging Logic ---
        if not legacy_links_mode:
            logger.debug(f"Processing links for {file_path}. Auto-links found: {len(auto_links)}")
            manual_links = front_matter.get('links', [])
            if not isinstance(manual_links, list): # Ensure manual_links is a list
                logger.warning(f"Front-matter 'links' in {file_path} is not a list. Initializing as empty list.")
                manual_links = []
            
            final_links: List[Dict[str, Any]] = []
            
            # Use sets for efficient lookup
            manual_link_tuples = set()
            manual_link_tos = set()

            for link in manual_links:
                if isinstance(link, dict):
                    manual_link_tuples.add((link.get('to'), link.get('rel')))
                    manual_link_tos.add(link.get('to'))
            
            # Add all manual_links to final_links first to preserve their order and content.
            final_links.extend(manual_links)
            
            processed_auto_link_targets_rels = set(manual_link_tuples)
            next_auto_link_id = 1
            for link in final_links:
                link_id = link.get('id') if isinstance(link, dict) else None
                match = re.match(r'^auto-link-(\d+)$', link_id or '')
                if match:
                    next_auto_link_id = max(next_auto_link_id, int(match.group(1)) + 1)

            for auto_link in auto_links:
                auto_link_tuple = (auto_link['target'], auto_link['rel'])
                
                if auto_link_tuple in processed_auto_link_targets_rels:
                    logger.debug(f"Auto-link {auto_link['id']} for target '{auto_link['target']}' with rel '{auto_link['rel']}' is a duplicate of an existing link. Discarding.")
                    continue # Duplicate of an existing manual or already added auto-link
                
                if auto_link['target'] in manual_link_tos:
                    # Conflict: same target, different relationship or manual has no rel
                    warning_message = (
                        f"Conflict in {file_path}: Auto-generated link {auto_link['id']} for target "
                        f"'{auto_link['target']}' with relationship '{auto_link['rel']}' conflicts with an "
                        f"existing manual link with a different relationship. Adding auto-link for now."
                    )
                    logger.warning(warning_message)
                    logging.warning(warning_message)
                    # As per instructions, add the auto-link for now.
                    # Future enhancements could involve more sophisticated conflict resolution.
                
                auto_link_to_add = auto_link.copy()
                auto_link_to_add['id'] = f"auto-link-{next_auto_link_id}"
                next_auto_link_id += 1

                final_links.append(auto_link_to_add)
                processed_auto_link_targets_rels.add(auto_link_tuple)

            if original_front_matter.get('links', []) != final_links:
                if 'links' not in original_front_matter or original_front_matter.get('links') != final_links:
                    changes['links'] = {
                        'old': original_front_matter.get('links', 'Not present'),
                        'new': final_links
                    }
                    made_changes = True
                front_matter['links'] = final_links
        else:
            logger.info(f"Legacy links mode enabled for {file_path}. Skipping auto-link merging.")

        # --- End Link Merging Logic ---

        # Compute other updates (dates, metrics, etc.)
        # Pass the potentially modified front_matter (if links were merged)
        updated_fm_after_compute = self._compute_updates(front_matter, body, force_update)
        
        # Track changes from _compute_updates
        # Note: `front_matter` here is the one potentially modified by link merging.
        # `original_front_matter` is the state *before* link merging.
        # We need to compare `updated_fm_after_compute` with `front_matter` (state after link merge)
        # for fields managed by _compute_updates, but with `original_front_matter` for overall change detection.
        
        for field in ['dates', 'metrics', 'link_ids', 'asset_ids']:
            # Compare with the state of front_matter *before* _compute_updates but *after* link merging
            old_val_for_compute = self._get_nested_value(front_matter, field)
            new_val_from_compute = self._get_nested_value(updated_fm_after_compute, field)
            
            if old_val_for_compute != new_val_from_compute:
                # If 'links' also changed, this will overwrite. Need to be careful.
                # The changes dict should reflect the overall old vs new.
                changes[field] = {
                    'old': self._get_nested_value(original_front_matter, field, 'Not present' if field not in original_front_matter else None), 
                    'new': new_val_from_compute
                }
                made_changes = True
        
        # The final front_matter to be serialized is updated_fm_after_compute
        # Ensure 'links' from link merging is preserved if _compute_updates didn't touch it
        # or correctly reflects combined changes. _compute_updates currently doesn't modify 'links'.
        # So, updated_fm_after_compute will have the merged links if they were processed.

        if not made_changes:
            logger.debug(f"No changes detected for {file_path}.")
            return {'updated': False, 'changes': {}, 'errors': []}
        
        if dry_run:
            logger.info(f"Dry run: Changes for {file_path} would be: {changes}")
            return {'updated': False, 'changes': changes, 'errors': []}
        
        # Write updated file using the final state of the front-matter
        logger.info(f"Writing updates to {file_path}.")
        self._write_updated_file(file_path, content, updated_fm_after_compute)
        
        return {'updated': True, 'changes': changes, 'errors': []}
    
    def _compute_updates(self, current_front_matter: Dict[str, Any], body: str, 
                        force_update: bool = False) -> Dict[str, Any]:
        """Compute updated front-matter values (dates, metrics, etc.).
        This method operates on a copy and returns it.
        """
        updated_fm = {k: v for k, v in current_front_matter.items()} # Work on a copy
        
        # Ensure required fields exist (idempotently)
        if 'title' not in updated_fm:
            updated_fm['title'] = 'Untitled Document'
        if 'authors' not in updated_fm:
            updated_fm['authors'] = []
        # 'links' might have been populated by link merging, ensure it's a list if not.
        if 'links' not in updated_fm or not isinstance(updated_fm['links'], list):
            # If link merging happened, 'links' will exist.
            # If not, and it's missing, initialize.
            if 'links' not in updated_fm:
                 updated_fm['links'] = []

        # Update dates
        self._update_dates(updated_fm, force_update)
        
        # Update metrics
        self._update_metrics(updated_fm, body, force_update)
        
        # Update link and asset IDs
        self._update_ids(updated_fm, body, force_update)
        
        return updated_fm
    
    def _update_dates(self, front_matter: Dict[str, Any], force_update: bool = False):
        """Update date fields."""
        dates = front_matter.setdefault('dates', {})
        
        # Set created date if missing
        if 'created' not in dates:
            dates['created'] = self._current_timestamp()
        
        # Update modified date unless locked
        if force_update or not self._is_locked(dates, 'modified'):
            dates['modified'] = self._current_timestamp()
    
    def _update_metrics(self, front_matter: Dict[str, Any], body: str, force_update: bool = False):
        """Update metrics fields."""
        metrics = front_matter.setdefault('metrics', {})
        
        # Update word count unless locked
        if force_update or not self._is_locked(metrics, 'word_count'):
            metrics['word_count'] = self._count_words(body)
        
        # Update reading time estimate unless locked
        if force_update or not self._is_locked(metrics, 'reading_time'):
            word_count = metrics['word_count']
            # Assume 200 words per minute average reading speed
            minutes = max(1, round(word_count / 200))
            metrics['reading_time'] = f"{minutes} min"
    
    def _update_ids(self, front_matter: Dict[str, Any], body: str, force_update: bool = False):
        """Update link_ids and asset_ids fields."""
        # Update link_ids unless locked
        if force_update or not self._is_locked(front_matter, 'link_ids'):
            front_matter['link_ids'] = self._extract_link_ids(body)
        
        # Update asset_ids unless locked
        if force_update or not self._is_locked(front_matter, 'asset_ids'):
            front_matter['asset_ids'] = self._extract_asset_ids(body)
    
    def _extract_link_ids(self, body: str) -> List[str]:
        """Extract all [[id]] references from the document body."""
        # Find all [[...]] patterns
        link_pattern = r'\[\[([^\]]+)\]\]'
        matches = re.findall(link_pattern, body)
        
        # Return unique IDs, preserving order
        seen = set()
        unique_ids = []
        for link_id in matches:
            if link_id not in seen:
                seen.add(link_id)
                unique_ids.append(link_id)
        
        return unique_ids
    
    def _extract_asset_ids(self, body: str) -> List[str]:
        """Extract all asset references from the document body."""
        asset_ids = []
        
        # Markdown image syntax: ![alt](path)
        img_pattern = r'!\[[^\]]*\]\(([^)]+)\)'
        img_matches = re.findall(img_pattern, body)
        
        # HTML img tags: <img src="path">
        html_img_pattern = r'<img[^>]+src=["\']([^"\']+)["\'][^>]*>'
        html_img_matches = re.findall(html_img_pattern, body, re.IGNORECASE)
        
        # Markdown link syntax for assets: [text](path) where path looks like an asset
        asset_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.svg', '.pdf', '.doc', '.docx', 
                          '.mp4', '.mp3', '.wav', '.zip', '.tar', '.gz'}
        link_pattern = r'\[[^\]]*\]\(([^)]+)\)'
        link_matches = re.findall(link_pattern, body)
        asset_links = [path for path in link_matches 
                      if any(path.lower().endswith(ext) for ext in asset_extensions)]
        
        # Combine all asset references
        all_assets = img_matches + html_img_matches + asset_links
        
        # Filter for local assets (not URLs) and remove duplicates
        local_assets = []
        seen = set()
        for asset in all_assets:
            # Skip URLs
            if asset.startswith(('http://', 'https://', 'ftp://', '//')):
                continue
            
            # Skip absolute paths that look like system paths
            if asset.startswith('/') and not asset.startswith('./'):
                continue
            
            if asset not in seen:
                seen.add(asset)
                local_assets.append(asset)
        
        return local_assets
    
    def _count_words(self, text: str) -> int:
        """Count words in text, excluding code blocks and other non-prose elements."""
        # Remove code blocks (```...```)
        text = re.sub(r'```.*?```', '', text, flags=re.DOTALL)
        
        # Remove inline code (`...`)
        text = re.sub(r'`[^`]+`', '', text)
        
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        
        # Remove markdown links but keep the text: [text](url) -> text
        text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
        
        # Remove markdown image syntax
        text = re.sub(r'!\[[^\]]*\]\([^)]+\)', '', text)
        
        # Remove markdown headers (#)
        text = re.sub(r'^#+\s*', '', text, flags=re.MULTILINE)
        
        # Remove other markdown formatting
        text = re.sub(r'[*_`]', '', text)
        
        # Split into words and count
        words = text.split()
        return len([word for word in words if word.strip()])
    
    def _current_timestamp(self) -> str:
        """Get current timestamp in ISO 8601 format."""
        return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    
    def _is_locked(self, container: Dict[str, Any], field: str) -> bool:
        """Check if a field is marked as locked."""
        if isinstance(container, dict) and 'locked' in container:
            locked_fields = container['locked']
            if isinstance(locked_fields, bool):
                return locked_fields  # All fields locked
            if isinstance(locked_fields, list):
                return field in locked_fields  # Specific fields locked
            if isinstance(locked_fields, dict):
                return locked_fields.get(field, False)  # Field-specific lock status
        return False
    
    def _get_nested_value(self, data: Dict[str, Any], field: str, default_if_not_present: Any = None) -> Any:
        """Get a potentially nested field value for comparison.
        Allows specifying a default if the top-level field itself is not present.
        """
        if field == 'dates':
            return data.get('dates', {} if default_if_not_present is None else default_if_not_present)
        elif field == 'metrics':
            return data.get('metrics', {} if default_if_not_present is None else default_if_not_present)
        # For 'links', 'link_ids', 'asset_ids', if they are not present, returning [] or 'Not present' might be appropriate.
        # The original code returned data.get(field), which is None if not present.
        # The new change tracking needs 'Not present' for 'links'.
        if default_if_not_present is not None and field not in data:
            return default_if_not_present
        return data.get(field)
    
    def _write_updated_file(self, file_path: Path, original_content: str, 
                          updated_front_matter: Dict[str, Any]):
        """Write the updated file, preserving everything except front-matter."""
        # Split the content to preserve the structure
        lines = original_content.splitlines(keepends=True)
        
        # Find the version tag
        version_line = None
        fm_start = None
        fm_end = None
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith('<!-- ormd:0.1 -->'):
                version_line = i
            elif version_line is not None and fm_start is None:
                if stripped in ('---', '+++'):
                    fm_start = i
                    delimiter = stripped
            elif fm_start is not None and fm_end is None:
                if stripped == delimiter:
                    fm_end = i
                    break
        
        # Build the new content
        new_lines = []
        
        # Add everything before front-matter
        if version_line is not None:
            new_lines.extend(lines[:version_line + 1])
        
        # Add the updated front-matter
        if fm_start is not None:
            # Preserve any whitespace/comments between version and front-matter
            if version_line is not None:
                new_lines.extend(lines[version_line + 1:fm_start])
            
            # Add the new front-matter block
            serialized_fm = serialize_front_matter(updated_front_matter)
            # Use the same delimiter as the original
            if fm_start < len(lines):
                original_delimiter = lines[fm_start].strip()
                if original_delimiter == '+++':
                    # Replace only the YAML block delimiters, not any '---' that
                    # may appear inside the YAML content itself.
                    fm_lines = serialized_fm.rstrip('\n').split('\n')
                    if fm_lines and fm_lines[0] == '---':
                        fm_lines[0] = '+++'
                    if fm_lines and fm_lines[-1] == '---':
                        fm_lines[-1] = '+++'
                    serialized_fm = '\n'.join(fm_lines) + '\n'
            
            new_lines.append(serialized_fm)
            
            # Add everything after front-matter
            if fm_end is not None and fm_end + 1 < len(lines):
                new_lines.extend(lines[fm_end + 1:])
        else:
            # No front-matter found, add it after version tag
            new_lines.append('\n')
            new_lines.append(serialize_front_matter(updated_front_matter))
            new_lines.append('\n')
            # Add the rest of the content
            if version_line is not None:
                new_lines.extend(lines[version_line + 1:])
            else:
                new_lines.extend(lines)
        
        # Write the updated content
        file_path.write_text(''.join(new_lines), encoding='utf-8') 
