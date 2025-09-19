"""Parsing utilities for ORMD documents."""
import re
import yaml
from typing import Tuple, Dict, Optional, List


def parse_document(content: str) -> Tuple[Optional[Dict], str, Optional[Dict[str, str]], List[str]]:
    """Parse full ORMD document content.

    Returns a tuple ``(front_matter, body, metadata, errors)``.
    ``front_matter`` will be ``None`` if YAML parsing fails.
    ``metadata`` is always ``None`` in the new schema (no more +++meta blocks).
    ``errors`` contains any parsing related warnings or errors.
    
    Note: The metadata parameter is kept for backward compatibility but will always be None
    since all metadata now goes in the front-matter YAML block.
    """
    errors: List[str] = []
    
    # Check for version tag at the beginning
    if not content.strip().startswith('<!-- ormd:0.1 -->'):
        errors.append("Missing or invalid version tag (expected at the beginning of the document)")
        return None, "", None, errors
    
    # Remove the version tag
    content_without_version = re.sub(r'^<!-- ormd:0\.1 -->\s*\n?', '', content, flags=re.MULTILINE)
    
    # Parse front-matter and body
    front_matter, body = _parse_front_matter_and_body(content_without_version)
    
    # Validate YAML if present
    if front_matter is None and content_without_version.strip().startswith(('---', '+++')):
        errors.append("Invalid YAML in front-matter")
        return None, body, None, errors
    
    # Convert empty front-matter to empty dict
    if front_matter is None:
        front_matter = {}
    
    # Validate YAML if present, and ensure no multiple front-matter blocks
    if front_matter is None:
        if content_without_version.strip().startswith(('---', '+++')):
            errors.append("Error: Invalid YAML in front-matter.")
            # No further checks needed if the primary front-matter is invalid
            return None, body, None, errors
        # If no front-matter delimiters at all, it's a valid document with an empty front_matter
        front_matter = {}
    else: # Valid initial front-matter was found
        # Check for subsequent YAML block delimiters in the body
        # This regex looks for '---' or '+++' at the beginning of a line, possibly with spaces before it.
        if re.search(r'^\s*(---\s*$|\+\+\+\s*$)', body, re.MULTILINE):
            errors.append("Error: Multiple YAML front-matter blocks found. Only one is allowed at the beginning of the document.")

    # Error for legacy +++meta blocks
    if re.search(r'^[ ]*\+\+\+meta\b', body, re.MULTILINE):
        errors.append("Error: `+++meta` blocks are no longer supported. All metadata must be in the YAML front-matter.")
    if re.search(r'^[ ]*\+\+\+end-meta\b', body, re.MULTILINE): # Check for +++end-meta as well
        errors.append("Error: `+++end-meta` blocks are no longer supported.")
    
    return front_matter, body, None, errors


def _parse_front_matter_and_body(content: str) -> Tuple[Optional[Dict], str]:
    """Parse YAML front-matter and document body.
    
    Supports both --- and +++ delimiters for front-matter.
    Returns (front_matter_dict, body_content)
    """
    content = content.strip()
    
    # Check if content starts with front-matter delimiters
    if content.startswith('---\n'):
        return _extract_yaml_block(content, '---')
    elif content.startswith('+++\n'):
        return _extract_yaml_block(content, '+++')
    else:
        # No front-matter, entire content is body
        return None, content


def _extract_yaml_block(content: str, delimiter: str) -> Tuple[Optional[Dict], str]:
    """Extract YAML front-matter block with given delimiter."""
    lines = content.split('\n')
    
    if lines[0] != delimiter:
        return None, content
    
    # Find closing delimiter
    closing_line = None
    for i in range(1, len(lines)):
        if lines[i].strip() == delimiter:
            closing_line = i
            break
    
    if closing_line is None:
        # No closing delimiter found, treat as body content
        return None, content
    
    # Extract YAML content
    yaml_lines = lines[1:closing_line]
    yaml_content = '\n'.join(yaml_lines)
    
    # Extract body content (everything after closing delimiter)
    body_lines = lines[closing_line + 1:]
    body_content = '\n'.join(body_lines).strip()
    
    # Parse YAML
    try:
        if yaml_content.strip():
            front_matter = yaml.safe_load(yaml_content)
            if front_matter is None:
                front_matter = {}
        else:
            front_matter = {}
    except yaml.YAMLError:
        return None, body_content
    
    return front_matter, body_content

# Removed migrate_legacy_metadata and _migrate_metadata_fields functions

def serialize_front_matter(front_matter: Dict) -> str:
    """Serialize front-matter dictionary to YAML with stable ordering.
    
    Orders fields by logical grouping for better readability:
    1. Core required fields (title, authors, links)
    2. Organized metadata namespaces (dates, metrics, permissions)  
    3. Optional simple fields (version, status, etc.)
    """
    if not front_matter:
        return "---\n---\n"
    
    # Create ordered dictionary with stable field ordering
    ordered_fm = {}
    
    # 1. Required core fields first
    for field in ['title', 'authors', 'links']:
        if field in front_matter:
            ordered_fm[field] = front_matter[field]
    
    # 2. Organized metadata namespaces
    for namespace in ['dates', 'metrics', 'permissions', 'context']:
        if namespace in front_matter:
            ordered_fm[namespace] = front_matter[namespace]
    
    # 3. Optional simple fields in logical order
    optional_fields = ['version', 'status', 'description', 'language', 'license', 'keywords']
    for field in optional_fields:
        if field in front_matter:
            ordered_fm[field] = front_matter[field]
    
    # 4. Any remaining fields (to handle extensions)
    for field, value in front_matter.items():
        if field not in ordered_fm:
            ordered_fm[field] = value
    
    # Serialize to YAML with clean formatting
    yaml_content = yaml.dump(
        ordered_fm, 
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,  # Preserve our custom ordering
        indent=2
    )
    
    return f"---\n{yaml_content}---\n" 