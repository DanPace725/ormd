import markdown
import json
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from .utils import get_view_template, SYMBOLS
from .parser import _split_inline_link_inner

# Index for iterating through auto_links_from_parser in the replace_inline_link_match function
# This assumes that the regex finditer and the auto_links_from_parser list are in the same order.
_current_auto_id_index_for_inline_links = 0

def _replace_inline_link_match(match: re.Match, auto_links_from_parser: List[Dict[str, Any]]) -> str:
    """Replacement function for inline semantic links [text](target "rel")."""
    global _current_auto_id_index_for_inline_links
    
    text = match.group(1)
    target, rel = _split_inline_link_inner(match.group(2))

    if _current_auto_id_index_for_inline_links >= len(auto_links_from_parser):
        # This case should ideally not happen if parser and regex are in sync.
        # Fallback to creating a link without a pre-generated ID, or log an error.
        # For now, create a simple link, but this indicates a potential issue.
        rel_attr_fallback = f' data-rel="{rel}"' if rel else ''
        # No data-link-id because we don't have a pre-generated one.
        return f'<a href="{target}"{rel_attr_fallback}>{text}</a>'

    link_info = auto_links_from_parser[_current_auto_id_index_for_inline_links]
    
    # Basic sanity check (optional, but good for debugging)
    # if not (link_info.get('text') == text and link_info.get('target') == target and link_info.get('rel') == rel):
    #     # Log this mismatch, e.g., using a logger or print statement for debugging
    #     print(f"Warning: Link mismatch. Regex: ('{text}', '{target}', '{rel}'), Parser: ('{link_info.get('text')}', '{link_info.get('target')}', '{link_info.get('rel')}')")
        
    auto_id = link_info.get('id', f"generated-id-{_current_auto_id_index_for_inline_links}") # Fallback ID
    link_rel_from_parser = link_info.get('rel') # Use rel from parser for consistency
    
    _current_auto_id_index_for_inline_links += 1
    
    rel_attr = f' data-rel="{link_rel_from_parser}"' if link_rel_from_parser else ''
    return f'<a href="{target}" data-link-id="{auto_id}"{rel_attr}>{text}</a>'

def _replace_legacy_link_match(match: re.Match, merged_links_map: Dict[str, Dict[str, Any]]) -> str:
    """Replacement function for legacy [[link-id]] links."""
    link_id = match.group(1)
    link_definition = merged_links_map.get(link_id)
    if link_definition:
        to = link_definition.get('to', f'#{link_id}') # Default 'to' if missing
        rel = link_definition.get('rel')
        # Determine display text: Use 'text' (from auto-link if merged), then 'title' (manual), else 'id'
        display_text = link_definition.get('text', link_definition.get('title', link_id))
        
        rel_attr = f' data-rel="{rel}"' if rel else ''
        return f'<a href="{to}" data-link-id="{link_id}"{rel_attr}>{display_text}</a>'
    else:
        return f'<span class="ormd-link ormd-link-undefined" data-link-id="{link_id}">{link_id}</span>'

def _preprocess_body_links(
    body: str, 
    auto_links_from_parser: List[Dict[str, Any]], 
    merged_fm_links: List[Dict[str, Any]]
) -> str:
    """Processes both inline semantic links and legacy [[link-id]] links in the body."""
    global _current_auto_id_index_for_inline_links
    _current_auto_id_index_for_inline_links = 0 # Reset for each call

    # Stage 1: Replace Inline Semantic Links [text](target "rel")
    inline_link_regex = re.compile(r'\[([^\]]+?)\]\(([^)]*?)\)')
    
    # Curry auto_links_from_parser into the replacement function
    def stage1_repl_func(match):
        return _replace_inline_link_match(match, auto_links_from_parser)
        
    processed_body_stage1 = inline_link_regex.sub(stage1_repl_func, body)

    # Stage 2: Replace Legacy [[link-id]] Links
    merged_links_map = {
        link['id']: link for link in merged_fm_links if isinstance(link, dict) and 'id' in link
    }
    
    # Curry merged_links_map into the replacement function
    def stage2_repl_func(match):
        return _replace_legacy_link_match(match, merged_links_map)

    processed_body_final = re.sub(r'\[\[([^\]]+?)\]\]', stage2_repl_func, processed_body_stage1)
    
    return processed_body_final

def get_edit_template() -> str:
    """Reads and returns the content of the edit_template.html file."""
    template_path = Path(__file__).parent / "templates" / "edit_template.html"
    try:
        return template_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return "<html><body><h1>Error: Edit template not found.</h1><p>Searched at: {}</p></body></html>".format(template_path.resolve())
    except Exception as e:
        return f"<html><body><h1>Error loading edit template: {e}</h1></body></html>"

def _generate_viewable_html(
    file_path, 
    raw_ormd, 
    front_matter: Dict[str, Any], 
    body: str, 
    links: List[Dict[str, Any]], # This is front_matter.get('links', [])
    meta, 
    auto_links_from_parser: List[Dict[str, Any]]
):
    """Generate HTML for viewing ORMD document"""

    title = front_matter.get('title', 'ORMD Document') if front_matter else 'ORMD Document'
    permissions = front_matter.get('permissions', {}) if front_matter else {}

    processed_body = _preprocess_body_links(body, auto_links_from_parser, links)

    # Render Markdown to HTML with syntax highlighting
    main_html = markdown.markdown(
        processed_body,
        extensions=['extra', 'toc', 'sane_lists', 'codehilite'],
        extension_configs={
            'codehilite': {
                'css_class': 'codehilite',
                'guess_lang': True,
                'use_pygments': True
            },
            'toc': {
                'permalink': True
            }
        }
    )

    # Prepare history info from meta.json if available
    history = ''
    if meta:
        created = meta.get('created', '')
        modified = meta.get('modified', '')
        provenance = meta.get('provenance', {})
        history = f"<b>Created:</b> {created}<br><b>Modified:</b> {modified}<br>"
        if provenance:
            history += f"<b>Hash:</b> {provenance.get('hash', '')}<br>"
            history += f"<b>Signature Ref:</b> {provenance.get('sigRef', '')}<br>"
            history += f"<b>Timestamp:</b> {provenance.get('timestamp', '')}<br>"

    # Add permissions info to history
    if permissions:
        history += "<br><b>Permissions:</b><br>"
        history += f"Mode: {permissions.get('mode', 'draft')}<br>"
        history += f"Editable: {permissions.get('editable', True)}<br>"
        history += f"Signed: {permissions.get('signed', False)}<br>"

    # Fill the HTML template (reuse existing template)
    html_template_content = get_view_template() # Call the function from utils
    html = html_template_content.format(
        title=f"{title} - ORMD Viewer",
        raw_ormd=raw_ormd.replace('<', '&lt;').replace('>', '&gt;'),
        main_html=main_html,
        history=history
    )

    # Insert links data for D3.js graph
    # 'links' here refers to the merged front-matter links, which is appropriate for the graph
    links_json = json.dumps(links) 
    new_html, n = re.subn(r'// renderGraph\(.*\);', f'renderGraph({links_json});', html)
    if n == 0:
        new_html = html.replace('</script>', f'renderGraph({links_json});\n</script>')

    return new_html

def _generate_editable_html(
    file_path, 
    raw_ormd, 
    front_matter: Dict[str, Any], 
    body: str, 
    links: List[Dict[str, Any]], # This is front_matter.get('links', [])
    meta,
    auto_links_from_parser: List[Dict[str, Any]]
):
    """Generate HTML for editing ORMD document"""

    title = front_matter.get('title', 'ORMD Document') if front_matter else 'ORMD Document'
    permissions = front_matter.get('permissions', {}) if front_matter else {}

    processed_body = _preprocess_body_links(body, auto_links_from_parser, links)
    
    # Render Markdown to HTML with syntax highlighting
    main_html = markdown.markdown(
        processed_body,
        extensions=['extra', 'toc', 'sane_lists', 'codehilite'],
        extension_configs={
            'codehilite': {
                'css_class': 'codehilite',
                'guess_lang': True,
                'use_pygments': True
            },
            'toc': {
                'permalink': True
            }
        }
    )

    # Prepare history info from meta.json if available
    history = ''
    if meta:
        created = meta.get('created', '')
        modified = meta.get('modified', '')
        provenance = meta.get('provenance', {})
        history = f"<b>Created:</b> {created}<br><b>Modified:</b> {modified}<br>"
        if provenance:
            history += f"<b>Hash:</b> {provenance.get('hash', '')}<br>"
            history += f"<b>Signature Ref:</b> {provenance.get('sigRef', '')}<br>"
            history += f"<b>Timestamp:</b> {provenance.get('timestamp', '')}<br>"

    # Add permissions info to history
    if permissions:
        history += "<br><b>Permissions:</b><br>"
        history += f"Mode: {permissions.get('mode', 'draft')}<br>"
        history += f"Editable: {permissions.get('editable', True)}<br>"
        history += f"Signed: {permissions.get('signed', False)}<br>"

    # Create the editable HTML template with main area editing
    editable_template_str = get_edit_template() # Call the function now in this module

    # Prepare template variables
    file_name = Path(file_path).name
    file_path_safe = file_path.replace('\\', '/').replace(' ', '_')  # Safe for localStorage key
    raw_ormd_escaped = raw_ormd.replace('<', '&lt;').replace('>', '&gt;')

    return editable_template_str.format(
        title=f"{title}",
        raw_ormd_escaped=raw_ormd_escaped,
        main_html=main_html, # This is already processed by markdown
        history=history,
        file_name=file_name,
        file_path_safe=file_path_safe
    )

def generate_render_html(
    raw_ormd: str, 
    front_matter: dict, 
    body: str, 
    links: list, # This is front_matter.get('links', [])
    meta: dict,
    auto_links_from_parser: List[Dict[str, Any]]
) -> str:
    """Generates HTML for the 'render' command."""
    title = front_matter.get('title', 'ORMD Document') if front_matter else 'ORMD Document'

    processed_body = _preprocess_body_links(body, auto_links_from_parser, links)

    # Render Markdown to HTML with syntax highlighting
    main_html_content = markdown.markdown(
        processed_body,  # Use the link-processed body
        extensions=['extra', 'toc', 'sane_lists', 'codehilite'],
        extension_configs={
            'codehilite': {
                'css_class': 'codehilite',
                'guess_lang': True,
                'use_pygments': True
            },
            'toc': {
                'permalink': True
            }
        }
    )

    # Prepare history info from meta.json if available
    history_content = ''
    if meta:
        created = meta.get('created', '')
        modified = meta.get('modified', '')
        provenance = meta.get('provenance', {})
        history_content = f"<b>Created:</b> {created}<br><b>Modified:</b> {modified}<br>"
        if provenance:
            history_content += f"<b>Hash:</b> {provenance.get('hash', '')}<br>"
            history_content += f"<b>Signature Ref:</b> {provenance.get('sigRef', '')}<br>"
            history_content += f"<b>Timestamp:</b> {provenance.get('timestamp', '')}<br>"

    # Fill the HTML template
    template_str = get_view_template()
    html_output = template_str.format(
        title=title,
        raw_ormd=raw_ormd.replace('<', '&lt;').replace('>', '&gt;'),
        main_html=main_html_content,
        history=history_content
    )

    # Insert links data for D3.js graph (as a JS variable)
    # 'links' here refers to the merged front-matter links
    links_json_str = json.dumps(links) 
    # Replace any '// renderGraph(...);' line with the actual call
    final_html, n = re.subn(r'// renderGraph\(.*\);', f'renderGraph({links_json_str});', html_output)
    if n == 0:
        # If no placeholder was found, append the call at the end of the script
        final_html = html_output.replace('</script>', f'renderGraph({links_json_str});\n</script>')

    return final_html
