# src/ormd_cli/main.py
import click
from .validator import ORMDValidator
from .packager import ORMDPackager
from .updater import ORMDUpdater
from typing import Optional
import io # Changed from 'from io import StringIO' to just 'import io'
from pdfminer.high_level import extract_pages
from pdfminer.layout import LAParams, LTTextBoxHorizontal
from pdfminer.pdfparser import PDFParser, PDFSyntaxError # Added PDFParser
from pdfminer.pdfdocument import PDFDocument # Added PDFDocument
from pdfminer.psparser import PSKeyword, PSLiteral # Added for decoding
from pdfminer.utils import decode_text # Added for decoding
import yaml
from pathlib import Path
from datetime import datetime, timezone, timedelta # Added timedelta
from .utils import get_view_template, SYMBOLS
from .parser import parse_document, serialize_front_matter, _parse_front_matter_and_body
import zipfile
import json # Used by render, open, edit
# re is no longer used directly in main.py
# webbrowser, threading, http.server, socketserver, tempfile, socket, os were moved
from .server import _serve_and_open
from .html_generator import _generate_viewable_html, _generate_editable_html, generate_render_html
from .logger import setup_logging, logger # Added
from .converter import _parse_pdf_date_string
# get_edit_template, _generate_viewable_html, _generate_editable_html, markdown and re imports removed as logic moved.

@click.group(context_settings=dict(help_option_names=['-h', '--help']))
@click.option('-v', '--verbose', is_flag=True, help='Enable verbose output (DEBUG level).')
@click.option('-q', '--quiet', is_flag=True, help='Suppress most output (show CRITICAL errors).')
@click.pass_context
def cli(ctx, verbose, quiet):
    """ORMD CLI - Tools for Open Relational Markdown.

    Use -v/--verbose for detailed debug output, or -q/--quiet to suppress all non-critical messages.
    """
    ctx.ensure_object(dict)
    # Store flags for potential direct use, though logger config is primary
    ctx.obj['VERBOSE'] = verbose
    ctx.obj['QUIET'] = quiet
    if quiet and verbose:
        # Let quiet take precedence as per user requirement, though Click might handle this too
        # For setup_logging, quiet=True will override verbose=True
        pass # setup_logging will handle precedence
    setup_logging(verbose, quiet)

@cli.command()     # Existing decorator
@click.pass_context # New decorator
@click.argument('file_path')
def create(ctx, file_path: str): # Added ctx
    """Create a new ORMD file with minimal front-matter.

    Examples:
    
      ormd create my_document.ormd
      ormd create path/to/my_new_report.ormd
    """
    logger.debug(f"Attempting to create ORMD file at: {file_path}")
    try:
        p = Path(file_path)
        filename = p.stem

        # Convert filename to title (e.g., "my-doc-name" -> "My Doc Name")
        title = filename.replace('-', ' ').replace('_', ' ').title()

        now_utc_iso = datetime.now(timezone.utc).isoformat()

        front_matter_data = {
            "title": title,
            "authors": [],
            "dates": { # Using 'dates' namespace as per serialize_front_matter logic
                "created": now_utc_iso,
                "modified": now_utc_iso,
            },
            # Consider adding other useful defaults if any, e.g.
            # "version": "1.0.0",
            # "status": "draft",
            # "permissions": {"editable": True, "mode": "private"}
        }

        front_matter_string = serialize_front_matter(front_matter_data)

        # Ensure there's a blank line after front-matter for the body
        # serialize_front_matter already adds a newline at the end of the block.
        # We add one more for an empty body.
        content = f"<!-- ormd:0.1 -->\n{front_matter_string}\n"

        with click.open_file(file_path, 'w', encoding='utf-8') as f:
            f.write(content)

        logger.info(f"{SYMBOLS['success']} Created ORMD file: {file_path}")

    except Exception as e:
        logger.error(f"{SYMBOLS['error']} Failed to create file: {str(e)}")
        # exit(1) removed for click consistency, though it was present in the original create
@cli.command()
@click.pass_context # New decorator
@click.argument('file_path')
# verbose option is now global, remove from here if not specifically overriding global
# For now, keeping it to see if click handles local vs global context options gracefully
@click.option('--verbose', '-v', is_flag=True, help='Show detailed validation info (overrides global -v).')
@click.option('--legacy-links', is_flag=True, help='Enable legacy link handling (skip inline link processing and strict validation).')
@click.option('--check-external-links', is_flag=True, help='Enable checking of external link targets (requires network access).')
def validate(ctx, file_path, verbose, legacy_links, check_external_links): # Added ctx, verbose might be from global ctx.obj['VERBOSE']
    """Validate an ORMD file against the 0.1 specification.

    The -v/--verbose flag (global or command-specific) shows detailed validation info.
    -q/--quiet will suppress typical success/warning messages if validation passes.

    Examples:
    
      ormd validate my_document.ormd
      ormd -v validate my_document.ormd
    """
    logger.debug(f"Validating file: {file_path} with legacy_links={legacy_links}, check_external_links={check_external_links}")
    validator = ORMDValidator()
    
    is_valid = validator.validate_file(
        file_path, 
        legacy_links_mode=legacy_links, 
        check_external_links=check_external_links
    )
    
    # Determine if local verbose was explicitly set, otherwise use global
    # This assumes the local verbose flag is meant to override the global for this command.
    # If not, then `verbose_flag = ctx.obj.get('VERBOSE', False)` would be sufficient.
    verbose_flag = verbose if ctx.get_parameter_source('verbose') == click.core.ParameterSource.COMMANDLINE else ctx.obj.get('VERBOSE', False)

    if verbose_flag or not is_valid:
        # Show detailed validation summary
        logger.info(validator.get_validation_summary())
    else:
        # Show simple success message
        if is_valid and not validator.warnings:
            logger.info(f"{SYMBOLS['success']} {file_path} is valid ORMD 0.1")
        elif is_valid and validator.warnings:
            logger.info(f"{SYMBOLS['success']} {file_path} is valid ORMD 0.1 (with {len(validator.warnings)} warning(s))")
            if not verbose_flag: # Use the determined verbose_flag
                logger.info("Use --verbose to see warnings")
    
    # Always show warnings even in non-verbose mode if validation passes
    if is_valid and validator.warnings and not verbose_flag: # Use the determined verbose_flag
        logger.warning(f"{SYMBOLS['warning']}  {len(validator.warnings)} warning(s) - use --verbose for details")
    
    if not is_valid:
        exit(1)

@cli.command()
@click.pass_context # New decorator
@click.argument('content_file')
@click.argument('meta_file')
@click.option('--out', '-o', default='package.ormd', help='Output package file')
@click.option('--validate/--no-validate', default=True, help='Validate content before packing')
@click.option('--overwrite', is_flag=True, help='Overwrite the output package if it already exists.') # New
def pack(ctx, content_file, meta_file, out, validate, overwrite): # Added overwrite
    """Pack content.ormd and meta.json into a single .ormd package.

    Examples:
    
      ormd pack content.ormd meta.json
      ormd pack chapter1.ormd chapter1_meta.json --out my_book.ormd
      ormd pack document.ormd metadata.json --no-validate
    """
    
    # Optional validation step
    if validate:
        validator = ORMDValidator()
        if not validator.validate_file(content_file):
            logger.error(f"{SYMBOLS['error']} Content file failed validation:")
            for error in validator.errors:
                logger.error(f"  {SYMBOLS['bullet']} {error}")
            logger.info("Use --no-validate to skip validation")
            exit(1)
    else:
        logger.debug("Skipping validation for pack operation.")

    output_package_path_str = out
    if output_package_path_str == 'package.ormd' and not Path(content_file).name.startswith('package'):
        output_package_path_str = Path(content_file).stem + ".ormd"

    logger.debug(f"Packing {content_file} and {meta_file} into {output_package_path_str}")
    output_package_path = Path(output_package_path_str)

    if output_package_path.exists() and not overwrite:
        logger.error(f"Error: Output package '{output_package_path}' already exists. Use --overwrite to replace it.")
        return
    
    packager = ORMDPackager()
    if packager.pack(content_file, meta_file, str(output_package_path)): # Use potentially modified path
        logger.info(f"{SYMBOLS['success']} Created package: {output_package_path}")
    else:
        logger.error(f"{SYMBOLS['error']} Failed to create package")
        exit(1)

@cli.command()
@click.pass_context # New decorator
@click.argument('package_file')
@click.option('--out-dir', '-d', default='./unpacked', help='Output directory')
@click.option('--overwrite', is_flag=True, help='Overwrite existing files') # Overwrite option is already here
def unpack(ctx, package_file, out_dir, overwrite): # Added ctx
    """Unpack a .ormd package for editing.

    Examples:
    
      ormd unpack my_package.ormd
      ormd unpack my_book.ormd --out-dir ./book_files
      ormd unpack archive.ormd --overwrite
    """
    from pathlib import Path

    output_dir_str = out_dir
    if output_dir_str == './unpacked' and Path(package_file).stem != 'unpacked':
        output_dir_str = Path(package_file).stem
    
    logger.debug(f"Unpacking {package_file} to {output_dir_str}")
    out_path = Path(output_dir_str)

    if out_path.is_file():
        logger.error(f"Error: Output directory target '{out_path}' exists and is a file.")
        return

    # Existing check for non-empty directory with --overwrite is good:
    if out_path.exists() and any(out_path.iterdir()) and not overwrite:
        logger.error(f"Error: Directory '{out_path}' is not empty. Use --overwrite to force.")
        # exit(1) # Changed to return for consistency
        return
    
    packager = ORMDPackager()
    if packager.unpack(package_file, output_dir_str): # Use potentially modified output_dir_str
        logger.info(f"{SYMBOLS['success']} Unpacked to: {output_dir_str}")
        
        # Show what was extracted
        if out_path.exists():
            files = list(out_path.iterdir())
            logger.info("Files extracted:")
            for file in sorted(files):
                logger.info(f"  {SYMBOLS['bullet']} {file.name}")
    else:
        logger.error(f"{SYMBOLS['error']} Failed to unpack {package_file}")
        exit(1)

@cli.command()
@click.pass_context # New decorator
@click.argument('file_path')
@click.option('--dry-run', '-n', is_flag=True, help='Show what would be updated without making changes')
@click.option('--force-update', '-f', is_flag=True, help='Update locked fields (ignore locked: true)')
@click.option('--verbose', '-v', is_flag=True, help='Show detailed update information (overrides global -v).')
@click.option('--legacy-links', is_flag=True, help='Enable legacy link handling (skip auto-generation of links in front-matter).')
def update(ctx, file_path, dry_run, force_update, verbose, legacy_links): # Added ctx, verbose might be from global
    # If local verbose is removed, use: verbose = ctx.obj.get('VERBOSE', False)
    """Update and sync front-matter fields (date_modified, word_count, etc.).

    The -v/--verbose flag (global or command-specific) shows detailed update information.

    Examples:
    
      ormd update my_document.ormd
      ormd -v update my_document.ormd
      ormd update my_document.ormd --dry-run
      ormd update my_document.ormd --force-update
    """
    logger.debug(f"Updating file: {file_path}")
    updater = ORMDUpdater()
    
    # Determine if local verbose was explicitly set for update, otherwise use global
    # This assumes the local verbose flag is meant to override the global for this command.
    # If not, then `verbose_flag = ctx.obj.get('VERBOSE', False)` would be sufficient.
    verbose_flag = verbose if ctx.get_parameter_source('verbose') == click.core.ParameterSource.COMMANDLINE else ctx.obj.get('VERBOSE', False)

    try:
        result = updater.update_file(
            file_path,
            dry_run=dry_run,
            force_update=force_update,
            verbose=verbose_flag, # Pass the determined verbosity
            legacy_links_mode=legacy_links
        )

        if dry_run:
            if result['changes']:
                logger.debug("Dry run: Showing potential changes.")
                logger.info(f"{SYMBOLS['info']} Would update {file_path}:")
                for field, change in result['changes'].items():
                    old_val = change.get('old', 'None') # Ensure old_val is defined if using it here
                    new_val = change.get('new')
                    logger.info(f"  {SYMBOLS['bullet']} {field}: {old_val} → {new_val}")
            else:
                logger.info(f"{SYMBOLS['success']} {file_path} is already up to date (dry run)")
        else:
            if result['updated']:
                logger.info(f"{SYMBOLS['success']} Updated {file_path}")
                if verbose_flag and result['changes']: # Use determined verbosity
                    logger.debug("Changes made:") # Detailed changes to debug
                    for field, change in result['changes'].items():
                        old_val = change.get('old', 'None')
                        new_val = change.get('new')
                        logger.debug(f"  {SYMBOLS['bullet']} {field}: {old_val} → {new_val}")
            else:
                logger.info(f"{SYMBOLS['success']} {file_path} is already up to date")
                
    except Exception as e:
        logger.error(f"{SYMBOLS['error']} Failed to update {file_path}: {str(e)}")
        exit(1)

@cli.command()
@click.pass_context # New decorator
@click.argument('input_file')
@click.option('--out', '-o', default=None, help='Output HTML file')
@click.option('--overwrite', is_flag=True, help='Overwrite the output file if it already exists.') # New
def render(ctx, input_file, out, overwrite: bool): # Added overwrite
    """Render an ORMD file or package to HTML.

    Examples:
    
      ormd render my_document.ormd
      ormd render my_package.ormd -o custom_name.html
    """
    logger.debug(f"Rendering {input_file} to {out if out else 'default HTML output'}")
    input_path = Path(input_file)
    is_zip = input_path.suffix == '.ormd' and zipfile.is_zipfile(input_file)
    raw_ormd = ''
    meta = {}
    title = 'ORMD Document'
    history = ''
    main_html = ''
    links = []
    front_matter = {}
    body = ''
    metadata = None # This is the old +++meta block, should be None.
    auto_links = [] # Initialize auto_links

    if is_zip:
        logger.debug(f"Input is a zip package. Reading content.ormd and meta.json.")
        with zipfile.ZipFile(input_file, 'r') as zf:
            if 'content.ormd' in zf.namelist():
                raw_ormd = zf.read('content.ormd').decode('utf-8')
            if 'meta.json' in zf.namelist():
                meta = json.loads(zf.read('meta.json').decode('utf-8')) # meta here is from meta.json
    else:
        logger.debug(f"Input is a plain ORMD file. Reading directly.")
        raw_ormd = Path(input_file).read_text(encoding='utf-8')

    # Unified parsing for both file and package using the shared parser
    # parse_document now returns: front_matter, body, metadata (old style, should be None), auto_links, parse_errors
    front_matter, body, metadata, auto_links, parse_errors = parse_document(raw_ormd)
    
    if parse_errors: # Log errors from parser
        logger.warning(f"{SYMBOLS['warning']} Document has parsing errors:")
        for error in parse_errors:
            logger.warning(f"  {SYMBOLS['bullet']} {error}")

    logger.debug(f"Document parsed. Auto-links found: {len(auto_links)}. Generating HTML content.")
    title = front_matter.get('title', title) if front_matter else title
    # 'links' for generate_render_html should be front_matter.get('links', [])
    fm_links = front_matter.get('links', []) if front_matter else []


    # The 'meta' passed to generate_render_html is from the meta.json in package, not the metadata from parse_document
    html_content = generate_render_html(
        raw_ormd, 
        front_matter, 
        body, 
        fm_links,  # This is front_matter.get('links', [])
        meta,      # This is from meta.json (for packages)
        auto_links_from_parser=auto_links
    )

    # Determine output path
    output_path_str = out
    if output_path_str is None:
        output_path_str = str(input_path.with_suffix('.html'))

    out_path = Path(output_path_str)
    if out_path.exists() and not overwrite:
        logger.error(f"Error: Output file '{out_path}' already exists. Use --overwrite to replace it.")
        return

    out_path.write_text(html_content, encoding='utf-8')
    logger.info(f"{SYMBOLS['success']} Rendered HTML written to: {out_path}") # Use out_path here

@cli.command()
@click.pass_context # New decorator
@click.argument('file_path')
@click.option('--port', '-p', default=0, help='Local server port (0 for random)')
@click.option('--no-browser', is_flag=True, help='Don\'t automatically open browser')
@click.option('--show-url', is_flag=True, help='Just show URL that would be opened (for testing)')
def open(ctx, file_path, port, no_browser, show_url): # Added ctx
    """Open ORMD document in browser for viewing (read-only).

    Examples:
    
      ormd open my_document.ormd
      ormd open my_package.ormd -p 8080
      ormd open my_document.ormd --no-browser
    """
    logger.debug(f"Preparing to open {file_path} for viewing.")
    # Validate file exists
    if not Path(file_path).exists():
        logger.error(f"{SYMBOLS['error']} File not found: {file_path}")
        exit(1)
    
    try:
        # Parse the document (similar to render command)
        input_path = Path(file_path)
        is_zip = input_path.suffix == '.ormd' and zipfile.is_zipfile(file_path)
        raw_ormd = ''
        meta = {} # From meta.json for packages
        auto_links = []
        
        if is_zip:
            with zipfile.ZipFile(file_path, 'r') as zf:
                if 'content.ormd' in zf.namelist():
                    raw_ormd = zf.read('content.ormd').decode('utf-8')
                if 'meta.json' in zf.namelist():
                    meta = json.loads(zf.read('meta.json').decode('utf-8'))
        else:
            raw_ormd = Path(file_path).read_text(encoding='utf-8')

        # Parse document
        front_matter, body, metadata, auto_links, parse_errors = parse_document(raw_ormd)
        logger.debug(f"Document parsed for viewing mode. Auto-links found: {len(auto_links)}.")
        
        if parse_errors:
            logger.warning(f"{SYMBOLS['warning']} Document has parsing errors:")
            for error in parse_errors:
                logger.warning(f"  {SYMBOLS['bullet']} {error}")
        
        title = front_matter.get('title', 'ORMD Document') if front_matter else 'ORMD Document'
        # 'links' for HTML generation should be front_matter.get('links', [])
        fm_links = front_matter.get('links', []) if front_matter else []
        permissions = front_matter.get('permissions', {}) if front_matter else {} # Not used by _generate_viewable_html directly but kept for context
        
        # Generate HTML for viewing
        html_content = _generate_viewable_html(
            file_path, 
            raw_ormd, 
            front_matter, 
            body, 
            fm_links, # This is front_matter.get('links', []) 
            meta,     # This is from meta.json (for packages)
            auto_links_from_parser=auto_links
        )
        
        if show_url:
            # Just show what would happen without starting server
            if port == 0:
                port = 8000  # Default for display
            logger.info(f"{SYMBOLS['success']} Would open '{title}' at http://localhost:{port}/")
            logger.debug(f"{SYMBOLS['info']} HTML generated successfully ({len(html_content)} characters)")
            return
        
        # Start server and open browser
        _serve_and_open(html_content, port, no_browser, file_path, title)
        
    except Exception as e:
        logger.error(f"{SYMBOLS['error']} Failed to open {file_path}: {str(e)}")
        exit(1)

@cli.command()
@click.pass_context # New decorator
@click.argument('file_path')
@click.option('--port', '-p', default=0, help='Local server port (0 for random)')
@click.option('--no-browser', is_flag=True, help='Don\'t automatically open browser')
@click.option('--force', '-f', is_flag=True, help='Force edit even if permissions deny it')
@click.option('--show-url', is_flag=True, help='Just show URL that would be opened (for testing)')
def edit(ctx, file_path, port, no_browser, force, show_url): # Added ctx
    """Open ORMD document in browser for editing.

    Examples:
    
      ormd edit my_document.ormd
      ormd edit my_package.ormd -p 8081 --force
      ormd edit my_document.ormd --no-browser
    """
    logger.debug(f"Preparing to open {file_path} for editing.")
    # Validate file exists
    if not Path(file_path).exists():
        logger.error(f"{SYMBOLS['error']} File not found: {file_path}")
        exit(1)
    
    try:
        # Parse the document
        input_path = Path(file_path)
        is_zip = input_path.suffix == '.ormd' and zipfile.is_zipfile(file_path)
        raw_ormd = ''
        meta = {} # From meta.json for packages
        auto_links = []
        
        if is_zip:
            with zipfile.ZipFile(file_path, 'r') as zf:
                if 'content.ormd' in zf.namelist():
                    raw_ormd = zf.read('content.ormd').decode('utf-8')
                if 'meta.json' in zf.namelist():
                    meta = json.loads(zf.read('meta.json').decode('utf-8'))
        else:
            raw_ormd = Path(file_path).read_text(encoding='utf-8')

        # Parse document
        front_matter, body, metadata, auto_links, parse_errors = parse_document(raw_ormd)
        logger.debug(f"Document parsed for editing mode. Auto-links found: {len(auto_links)}.")
        
        if parse_errors:
            logger.warning(f"{SYMBOLS['warning']} Document has parsing errors:")
            for error in parse_errors:
                logger.warning(f"  {SYMBOLS['bullet']} {error}")
        
        title = front_matter.get('title', 'ORMD Document') if front_matter else 'ORMD Document'
        # 'links' for HTML generation should be front_matter.get('links', [])
        fm_links = front_matter.get('links', []) if front_matter else []
        permissions = front_matter.get('permissions', {}) if front_matter else {}
        
        # Check permissions before proceeding
        can_edit = permissions.get('editable', True)  # Default to editable
        is_signed = permissions.get('signed', False)
        perm_mode = permissions.get('mode', 'draft')
        logger.debug(f"Checking permissions: editable={can_edit}, signed={is_signed}, mode={perm_mode}")
        
        if is_signed and not force:
            logger.error(f"{SYMBOLS['error']} Document is cryptographically signed and cannot be edited")
            logger.info("Use --force to edit anyway (will break signature)")
            exit(1)
        
        if not can_edit and not force:
            logger.error(f"{SYMBOLS['error']} Document permissions deny editing (editable: false)")
            logger.info("Use --force to edit anyway")
            exit(1)
        
        if perm_mode == 'private' and not force:
            logger.warning(f"{SYMBOLS['warning']} Document is marked as private")
            logger.info("Continuing with edit (use --force to suppress this warning)")
        
        # Show warnings for forced edits
        if force:
            logger.warning("Forced edit mode activated.")
            if is_signed:
                logger.warning(f"{SYMBOLS['warning']} Editing signed document - signature will be invalidated")
            if not can_edit:
                logger.warning(f"{SYMBOLS['warning']} Editing document marked as non-editable")
        
        # Generate HTML for editing
        html_content = _generate_editable_html(
            file_path, 
            raw_ormd, 
            front_matter, 
            body, 
            fm_links, # This is front_matter.get('links', [])
            meta,     # This is from meta.json (for packages)
            auto_links_from_parser=auto_links
        )
        
        if show_url:
            # Just show what would happen without starting server
            if port == 0:
                port = 8000  # Default for display
            logger.info(f"{SYMBOLS['success']} Would edit '{title}' at http://localhost:{port}/")
            logger.debug(f"{SYMBOLS['info']} Editable HTML generated successfully ({len(html_content)} characters)")
            return
        
        # Start server and open browser
        _serve_and_open(html_content, port, no_browser, file_path, f"{title} [EDIT]")
        
    except Exception as e:
        logger.error(f"{SYMBOLS['error']} Failed to edit {file_path}: {str(e)}")
        exit(1)

# _generate_viewable_html, _generate_editable_html, and the old get_edit_template (if it was here) are removed.
# _serve_and_open was already moved to server.py.

from .converter import convert_cmd
cli.add_command(convert_cmd)

if __name__ == '__main__':
    cli()
