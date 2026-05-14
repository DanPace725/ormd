import click
from pathlib import Path
from datetime import datetime, timezone, timedelta
import re
from typing import Optional

from pdfminer.high_level import extract_pages
from pdfminer.layout import LAParams, LTTextBoxHorizontal
from pdfminer.pdfparser import PDFParser, PDFSyntaxError
from pdfminer.pdfdocument import PDFDocument
from pdfminer.psparser import PSKeyword, PSLiteral
from pdfminer.utils import decode_text
import yaml # Though not directly used in convert, it's a common format, good to have.

from .utils import SYMBOLS
from .parser import parse_document, serialize_front_matter, _parse_front_matter_and_body
from .logger import logger # Added

# Helper function to parse PDF date strings
def _parse_pdf_date_string(pdf_date_str: str) -> Optional[str]:
    if not pdf_date_str or not isinstance(pdf_date_str, (str, bytes)):
        return None

    if isinstance(pdf_date_str, bytes):
        try:
            pdf_date_str = pdf_date_str.decode('utf-8', 'surrogateescape')
        except UnicodeDecodeError:
            return None # Cannot decode

    if pdf_date_str.startswith("D:"):
        pdf_date_str = pdf_date_str[2:]

    # Regex to capture YYYYMMDDHHMMSS and optional timezone offset
    # D:YYYYMMDDHHMMSSOHH'mm' (O is +, -, or Z)
    match = re.match(
        r"(\d{4})(\d{2})?(\d{2})?(\d{2})?(\d{2})?(\d{2})?" # Year, Month, Day, Hour, Minute, Second
        r"([Zz])?" # Z for UTC
        r"([+\-])?(\d{2})?'?(\d{2})?'?", # Timezone offset like +02'00' or -0500
        pdf_date_str
    )

    if not match:
        return None

    parts = match.groups()

    year = int(parts[0])
    month = int(parts[1] or 1)
    day = int(parts[2] or 1)
    hour = int(parts[3] or 0)
    minute = int(parts[4] or 0)
    second = int(parts[5] or 0)

    dt = datetime(year, month, day, hour, minute, second)

    utc_char = parts[6]
    offset_sign_char = parts[7]
    offset_hour_str = parts[8]
    offset_min_str = parts[9]

    if utc_char: # 'Z' means UTC
        dt = dt.replace(tzinfo=timezone.utc)
    elif offset_sign_char and offset_hour_str:
        offset_hours = int(offset_hour_str)
        offset_minutes = int(offset_min_str or 0)
        offset_delta = timedelta(hours=offset_hours, minutes=offset_minutes)
        if offset_sign_char == '-':
            offset_delta = -offset_delta

        dt = dt.replace(tzinfo=timezone(offset_delta))
        dt = dt.astimezone(timezone.utc) # Convert to UTC
    else:
        # No timezone info, assume UTC as a fallback, or local (pdfminer might imply local)
        # For consistency, let's assume UTC if no offset, though PDF spec implies local.
        # This might need refinement based on how source PDFs typically store dates.
        dt = dt.replace(tzinfo=timezone.utc)

    return dt.isoformat().replace("+00:00", "Z")

@click.command(name="convert") # Existing decorator
@click.pass_context # New decorator
@click.argument('input_file_path', type=click.Path(exists=True, dir_okay=False, resolve_path=True))
@click.argument('output_ormd_path', type=click.Path(dir_okay=False, resolve_path=True))
@click.option('--input-format', '-f', type=click.Choice(['txt', 'md', 'pdf'], case_sensitive=False), help='Specify the input file format.')
def convert_cmd(ctx, input_file_path: str, output_ormd_path: str, input_format: Optional[str]): # Added ctx
    """Convert a file (e.g. TXT, MD, PDF) to an ORMD file.

    Examples:
    
      ormd convert my_notes.txt my_notes.ormd
      ormd convert report.md report.ormd -f md
      ormd convert document.pdf document.ormd
    """
    try:
        input_p = Path(input_file_path)
        output_p = Path(output_ormd_path)

        # Determine format
        effective_input_format = input_format
        if not effective_input_format:
            effective_input_format = input_p.suffix.lower().lstrip('.')

        logger.debug(f"Starting conversion of {input_file_path} to {output_ormd_path} with format {effective_input_format if effective_input_format else 'auto'}")

        logger.info(f"{SYMBOLS['info']} Starting conversion...") # This is good for general info
        logger.debug(f"  Input file: {input_file_path}") # Debug for more detail
        logger.debug(f"  Output ORMD file: {output_ormd_path}") # Debug for more detail
        logger.info(f"  Detected input format: {effective_input_format if effective_input_format else 'unknown (will attempt .txt)'}") # Info is fine

        if effective_input_format == 'txt':
            logger.info(f"Converting from {effective_input_format.upper()} to ORMD...")

            # Read TXT content
            with click.open_file(input_p, 'r', encoding='utf-8') as f:
                txt_content = f.read()

            # Derive title
            title = input_p.stem.replace('-', ' ').replace('_', ' ').title()
            now_utc_iso = datetime.now(timezone.utc).isoformat()

            front_matter_data = {
                "title": title,
                "authors": [],
                "dates": {
                    "created": now_utc_iso,
                    "modified": now_utc_iso,
                },
                "source_file": str(input_p.resolve()), # Absolute path
                "conversion_details": {
                    "from_format": "txt",
                    "conversion_date": now_utc_iso
                }
            }

            front_matter_string = serialize_front_matter(front_matter_data)
            ormd_content = f"<!-- ormd:0.1 -->\n{front_matter_string}\n{txt_content}"

            with click.open_file(output_p, 'w', encoding='utf-8') as f:
                f.write(ormd_content)

            logger.info(f"{SYMBOLS['success']} Successfully converted '{input_p.name}' to '{output_p.name}'")

        elif effective_input_format == 'md':
            logger.info(f"Converting from {effective_input_format.upper()} to ORMD...")

            with click.open_file(input_p, 'r', encoding='utf-8') as f:
                md_content_full = f.read()

            body_content = "" # Initialize body_content
            existing_fm = {}  # Initialize existing_fm

            if md_content_full.strip().startswith("<!-- ormd:0.1 -->"):
                # File is likely already an ORMD file, parse it fully
                parsed_fm, parsed_body, _, _, parse_errors = parse_document(md_content_full)
                if parse_errors: # Still try to proceed if only minor errors
                    logger.warning(f"{SYMBOLS['warning']} Input ORMD-like file has parsing issues:")
                    for error in parse_errors: logger.warning(f"    {SYMBOLS['bullet']} {error}")
                if parsed_fm is not None: # if major parsing error, parsed_fm might be None
                    existing_fm = parsed_fm
                body_content = parsed_body # Use body from full parse
            else:
                # Plain MD file, try to get its front-matter and body
                raw_fm, plain_body = _parse_front_matter_and_body(md_content_full)
                existing_fm = raw_fm if raw_fm is not None else {}
                body_content = plain_body

            now_utc_iso = datetime.now(timezone.utc).isoformat()
            default_title = input_p.stem.replace('-', ' ').replace('_', ' ').title()

            # Initialize new front-matter with defaults
            new_fm = {
                "title": default_title,
                "authors": [],
                "dates": { # Default 'created' and 'modified' to now
                    "created": now_utc_iso,
                    "modified": now_utc_iso,
                },
                "source_file": str(input_p.resolve()),
                "conversion_details": {
                    "from_format": "md",
                    "conversion_date": now_utc_iso
                }
            }

            # Merge existing_fm into new_fm
            # Existing fields take precedence, except for special handling for 'dates'
            # and ensuring 'source_file' & 'conversion_details' are from the conversion process.
            if existing_fm:
                for key, value in existing_fm.items():
                    if key == "dates":
                        if isinstance(value, dict):
                            new_fm["dates"]["created"] = value.get("created", new_fm["dates"]["created"])
                            # new_fm["dates"]["modified"] is already set to now_utc_iso
                    elif key not in ["source_file", "conversion_details"]:
                        new_fm[key] = value

                # If 'dates' object was not in existing_fm, check for root 'date' or 'created'
                if "dates" not in existing_fm:
                    if "date" in existing_fm:
                        new_fm["dates"]["created"] = existing_fm["date"] # Override default 'created'
                    elif "created" in existing_fm: # A root 'created' field
                        new_fm["dates"]["created"] = existing_fm["created"] # Override default 'created'

            # Ensure 'authors' is a list. If overridden by a non-list, reset.
            if not isinstance(new_fm.get("authors"), list):
                logger.warning(f"{SYMBOLS['warning']} Existing 'authors' field was not a list. Resetting to empty list.")
                new_fm["authors"] = []

            # Ensure title is present, if existing_fm didn't have one, default_title is used.
            # If existing_fm had a title, it would have overwritten the default.
            if not new_fm.get("title"): # Should not happen if default_title is always set.
                 new_fm["title"] = default_title


            final_fm_string = serialize_front_matter(new_fm)
            # Ensure body_content doesn't start with newlines if it was empty after FM.
            ormd_content = f"<!-- ormd:0.1 -->\n{final_fm_string}\n{body_content.lstrip()}"


            with click.open_file(output_p, 'w', encoding='utf-8') as f:
                f.write(ormd_content)

            logger.info(f"{SYMBOLS['success']} Successfully converted '{input_p.name}' to '{output_p.name}'")

        elif effective_input_format == 'pdf':
            logger.info(f"Converting from {effective_input_format.upper()} to ORMD...") # Standardized this message
            logger.debug(f"  PDF conversion selected for '{input_p.name}'.") # More specific debug

            # --- Metadata Extraction ---
            pdf_meta = {}
            try:
                # Using click.open_file for consistency, as PDFParser needs a binary file object.
                with click.open_file(input_file_path, 'rb') as fp:
                    parser = PDFParser(fp)
                    doc = PDFDocument(parser)
                    if doc.info and isinstance(doc.info, list) and len(doc.info) > 0:
                        raw_info = doc.info[0]
                        for k, v_obj in raw_info.items():
                            key_str = decode_text(k) if isinstance(k, bytes) else str(k)
                            if isinstance(v_obj, (PSLiteral, PSKeyword)):
                                value_str = decode_text(v_obj.name)
                            elif isinstance(v_obj, bytes):
                                value_str = decode_text(v_obj)
                            else:
                                value_str = str(v_obj)
                            pdf_meta[key_str] = value_str
                        logger.debug(f"Extracted PDF metadata keys: {list(pdf_meta.keys())}") # Simpler debug
            except PDFSyntaxError as e:
                 logger.error(f"{SYMBOLS['error']} Failed to parse PDF for metadata (PDFSyntaxError): {e}. Ensure it's a valid PDF.")
                 exit(1)
            except Exception as e:
                logger.warning(f"{SYMBOLS['warning']} Could not extract metadata from PDF (general error): {e}")

            # --- Text Extraction (Layout Analysis) ---
            extracted_text_blocks = []
            pdf_body_content = ""
            try:
                laparams = LAParams()
                for page_layout in extract_pages(input_file_path, laparams=laparams):
                    for element in page_layout:
                        if isinstance(element, LTTextBoxHorizontal):
                            extracted_text_blocks.append(element.get_text())
                pdf_body_content = "\n\n".join(extracted_text_blocks).strip()
                logger.debug("Successfully processed PDF text using layout analysis.") # Debug for verbosity
            except PDFSyntaxError as e:
                logger.error(f"{SYMBOLS['error']} Failed to process PDF for text extraction (PDFSyntaxError): {e}. Ensure it's a valid PDF.")
                exit(1)
            except Exception as e:
                logger.error(f"{SYMBOLS['error']} Failed to process PDF file '{input_p.name}' for text extraction: {e}")
                exit(1)

            # --- Front-matter Population ---
            now_utc_iso = datetime.now(timezone.utc).isoformat()
            default_title = input_p.stem.replace('-', ' ').replace('_', ' ').title()

            title = pdf_meta.get('Title', default_title)
            if not title or not isinstance(title, str) or title.isspace():
                title = default_title

            authors = []
            pdf_author_str = pdf_meta.get('Author')
            if pdf_author_str and isinstance(pdf_author_str, str) and not pdf_author_str.isspace():
                if any(delim in pdf_author_str for delim in [',', ';', '&']):
                    authors = [a.strip() for a in re.split(r'[,;&]+', pdf_author_str) if a.strip()]
                else:
                    authors.append(pdf_author_str)

            keywords = []
            pdf_keywords_str = pdf_meta.get('Keywords')
            if pdf_keywords_str and isinstance(pdf_keywords_str, str) and not pdf_keywords_str.isspace():
                keywords = [kw.strip() for kw in re.split(r'[,;\s]+', pdf_keywords_str) if kw.strip()]

            created_date_iso = _parse_pdf_date_string(pdf_meta.get('CreationDate')) or now_utc_iso
            modified_date_iso = _parse_pdf_date_string(pdf_meta.get('ModDate')) or now_utc_iso

            front_matter_data = {
                "title": title,
                "authors": authors,
                "keywords": keywords if keywords else [],
                "dates": {
                    "created": created_date_iso,
                    "modified": modified_date_iso,
                },
                "source_file": str(input_p.resolve()),
                "conversion_details": {
                    "from_format": "pdf",
                    "conversion_date": now_utc_iso,
                    "extraction_method": "pdfminer.six layout analysis (paragraphs)",
                    "source_metadata_fields": list(pdf_meta.keys())
                }
            }
            if pdf_meta.get('ModDate') and modified_date_iso != now_utc_iso:
                 front_matter_data["conversion_details"]["source_modified_date"] = modified_date_iso

            front_matter_string = serialize_front_matter(front_matter_data)
            ormd_content = f"<!-- ormd:0.1 -->\n{front_matter_string}\n{pdf_body_content}"

            with click.open_file(output_p, 'w', encoding='utf-8') as f:
                f.write(ormd_content)

            logger.info(f"{SYMBOLS['success']} Successfully converted PDF '{input_p.name}' to ORMD file '{output_p.name}'")

        else:
            logger.error(f"{SYMBOLS['error']} Unsupported input format: '{effective_input_format}'. Only 'txt', 'md', and 'pdf' are supported.")
            logger.info(f"Please specify format with --input-format (e.g., txt, md, pdf).")
            exit(1)

    except Exception as e:
        logger.error(f"{SYMBOLS['error']} Failed during conversion: {str(e)}")
        exit(1)
