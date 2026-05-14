import os
from pathlib import Path
import yaml # For loading FM if needed, though parser does it.
from click.testing import CliRunner
from datetime import datetime, timezone # For checking date string validity (approx)

from ormd_cli.main import cli
from ormd_cli.parser import parse_document

class TestConvertCommand:
    """Tests for the 'convert' CLI command."""

    def test_convert_txt_file_explicit_format(self, tmp_path):
        """Test converting a .txt file to .ormd with explicit format."""
        runner = CliRunner()
        input_filename = "test_input.txt"
        output_filename = "test_output.ormd"

        input_filepath = tmp_path / input_filename
        output_filepath = tmp_path / output_filename

        sample_txt_content = "This is line one.\nThis is line two.\n\nEnd of text."
        input_filepath.write_text(sample_txt_content, encoding='utf-8')

        result = runner.invoke(cli, [
            'convert',
            str(input_filepath),
            str(output_filepath),
            '--input-format', 'txt'
        ])

        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert output_filepath.exists(), "Output ORMD file was not created"

        # Read and verify the output ORMD file
        ormd_content_full = output_filepath.read_text(encoding='utf-8')
        assert ormd_content_full.startswith("<!-- ormd:0.1 -->\n"), "Missing or incorrect ORMD version comment"

        # parse_document expects the version tag to be part of the content passed to it.
        front_matter, body, _, _, parse_errors = parse_document(ormd_content_full)

        assert not parse_errors, f"Parsing errors in generated ORMD: {parse_errors}"
        assert front_matter is not None, "Front-matter is missing or invalid in generated ORMD"

        # Verify front-matter fields
        expected_title = "Test Input" # Derived from "test_input.txt"
        assert front_matter.get("title") == expected_title, f"Incorrect title: expected '{expected_title}', got '{front_matter.get('title')}'"
        assert front_matter.get("authors") == [], "Authors list should be empty by default"

        assert "dates" in front_matter, "Dates field missing"
        dates_data = front_matter.get("dates")
        assert isinstance(dates_data, dict), "Dates field is not a dictionary"
        assert "created" in dates_data, "created date missing"
        assert "modified" in dates_data, "modified date missing"
        # Basic check for ISO format (string ending with Z or +HH:MM offset)
        assert isinstance(dates_data["created"], str) and (dates_data["created"].endswith("Z") or "+" in dates_data["created"][-6:])
        assert isinstance(dates_data["modified"], str) and (dates_data["modified"].endswith("Z") or "+" in dates_data["modified"][-6:])

        assert "source_file" in front_matter, "source_file field missing"
        assert front_matter.get("source_file") == str(input_filepath.resolve()), "source_file path incorrect"

        assert "conversion_details" in front_matter, "conversion_details field missing"
        conv_details = front_matter.get("conversion_details")
        assert isinstance(conv_details, dict), "conversion_details is not a dictionary"
        assert conv_details.get("from_format") == "txt", "Incorrect from_format"
        assert "conversion_date" in conv_details, "conversion_date missing"
        assert isinstance(conv_details["conversion_date"], str) and (conv_details["conversion_date"].endswith("Z") or "+" in conv_details["conversion_date"][-6:])

        # Verify body content
        # .lstrip() because serialize_front_matter adds a newline, and we ensure one more after it.
        # The body itself starts after that.
        assert body.strip() == sample_txt_content.strip(), "Body content does not match input TXT content"

    def test_convert_txt_file_auto_detect_format(self, tmp_path):
        """Test converting a .txt file to .ormd with auto-detected format."""
        runner = CliRunner()
        input_filename = "another_test_input.txt" # Different name to ensure no test interference
        output_filename = "another_test_output.ormd"

        input_filepath = tmp_path / input_filename
        output_filepath = tmp_path / output_filename

        sample_txt_content = "Auto-detect: Line one.\nAuto-detect: Line two."
        input_filepath.write_text(sample_txt_content, encoding='utf-8')

        result = runner.invoke(cli, [
            'convert',
            str(input_filepath),
            str(output_filepath)
            # No --input-format provided
        ])

        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert output_filepath.exists(), "Output ORMD file was not created (auto-detect)"

        ormd_content_full = output_filepath.read_text(encoding='utf-8')
        assert ormd_content_full.startswith("<!-- ormd:0.1 -->\n")

        front_matter, body, _, _, parse_errors = parse_document(ormd_content_full)

        assert not parse_errors, f"Parsing errors in generated ORMD (auto-detect): {parse_errors}"
        assert front_matter is not None, "Front-matter is missing (auto-detect)"

        expected_title = "Another Test Input"
        assert front_matter.get("title") == expected_title
        assert front_matter.get("authors") == []
        assert "dates" in front_matter
        assert "source_file" in front_matter
        assert front_matter.get("source_file") == str(input_filepath.resolve())
        assert "conversion_details" in front_matter
        assert front_matter.get("conversion_details", {}).get("from_format") == "txt"

        assert body.strip() == sample_txt_content.strip(), "Body content mismatch (auto-detect)"

    # Placeholder for future MD tests - can be expanded in another subtask
    # def test_convert_md_file_placeholder(self):
    #     pass

    def test_convert_md_file_no_front_matter(self, tmp_path):
        """Test converting a .md file with no front-matter (auto-detect format)."""
        runner = CliRunner()
        input_filename = "plain_markdown.md"
        output_filename = "plain_markdown_converted.ormd"

        input_filepath = tmp_path / input_filename
        output_filepath = tmp_path / output_filename

        sample_md_content = "# Markdown Title\n\nThis is a paragraph."
        input_filepath.write_text(sample_md_content, encoding='utf-8')

        result = runner.invoke(cli, ['convert', str(input_filepath), str(output_filepath)])

        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert output_filepath.exists(), "Output ORMD file was not created (MD no FM)"

        ormd_content_full = output_filepath.read_text(encoding='utf-8')
        assert ormd_content_full.startswith("<!-- ormd:0.1 -->\n")

        front_matter, body, _, _, parse_errors = parse_document(ormd_content_full)

        assert not parse_errors, f"Parsing errors in generated ORMD (MD no FM): {parse_errors}"
        assert front_matter is not None, "Front-matter is missing (MD no FM)"

        expected_title = "Plain Markdown" # Derived from "plain_markdown.md"
        assert front_matter.get("title") == expected_title
        assert front_matter.get("authors") == []
        assert "dates" in front_matter
        assert isinstance(front_matter.get("dates", {}).get("created"), str)
        assert isinstance(front_matter.get("dates", {}).get("modified"), str)
        assert front_matter.get("source_file") == str(input_filepath.resolve())
        assert front_matter.get("conversion_details", {}).get("from_format") == "md"
        assert isinstance(front_matter.get("conversion_details", {}).get("conversion_date"), str)

        assert body.strip() == sample_md_content.strip(), "Body content mismatch (MD no FM)"

    def test_convert_md_file_with_yaml_fm(self, tmp_path):
        """Test converting a .md file with --- YAML front-matter (explicit format)."""
        runner = CliRunner()
        input_filename = "md_with_fm.md"
        output_filename = "md_with_fm_converted.ormd"

        input_filepath = tmp_path / input_filename
        output_filepath = tmp_path / output_filename

        original_created_date = "2023-03-15T14:30:00Z"
        sample_md_content = f"""---
title: My Original MD Title
authors:
  - Author One
  - id: author2
    display: Author Two
date: {original_created_date} # Root date field
custom_key: custom_value
---
# Markdown Body Header

This is the actual body content.
"""
        input_filepath.write_text(sample_md_content, encoding='utf-8')

        result = runner.invoke(cli, [
            'convert', str(input_filepath), str(output_filepath), '--input-format', 'md'
        ])

        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert output_filepath.exists(), "Output ORMD file was not created (MD with FM)"

        ormd_content_full = output_filepath.read_text(encoding='utf-8')
        assert ormd_content_full.startswith("<!-- ormd:0.1 -->\n")

        front_matter, body, _, _, parse_errors = parse_document(ormd_content_full)

        assert not parse_errors, f"Parsing errors in generated ORMD (MD with FM): {parse_errors}"
        assert front_matter is not None, "Front-matter is missing (MD with FM)"

        assert front_matter.get("title") == "My Original MD Title"
        assert len(front_matter.get("authors", [])) == 2
        assert front_matter.get("authors")[0] == "Author One"
        assert front_matter.get("custom_key") == "custom_value"

        dates_data = front_matter.get("dates")
        assert dates_data is not None
        # PyYAML loads ISO strings as datetime objects, convert back for comparison or compare objects
        assert isinstance(dates_data.get("created"), datetime)
        assert dates_data.get("created").isoformat().startswith(original_created_date.rstrip("Z"))
        assert dates_data.get("modified") != original_created_date # Should be new
        assert isinstance(dates_data.get("modified"), str)

        assert front_matter.get("source_file") == str(input_filepath.resolve())
        assert front_matter.get("conversion_details", {}).get("from_format") == "md"

        expected_body = "# Markdown Body Header\n\nThis is the actual body content."
        assert body.strip() == expected_body.strip(), "Body content mismatch (MD with FM)"

    def test_convert_md_file_with_plus_fm_and_dates_object(self, tmp_path):
        """Test .md file with +++ YAML front-matter and specific dates.created."""
        runner = CliRunner()
        input_filename = "md_plus_fm.md"
        output_filename = "md_plus_fm_converted.ormd"

        input_filepath = tmp_path / input_filename
        output_filepath = tmp_path / output_filename

        original_created_date = "2022-10-01T08:00:00Z"
        original_modified_date = "2022-10-02T09:00:00Z" # This should be overridden

        sample_md_content = f"""+++
title: Title From Pluses
authors: ["Plus Author"]
dates:
  created: {original_created_date}
  modified: {original_modified_date}
keywords: ["plus", "test"]
+++
## Body with Plus FM

Content after plus front-matter.
"""
        input_filepath.write_text(sample_md_content, encoding='utf-8')

        result = runner.invoke(cli, ['convert', str(input_filepath), str(output_filepath)]) # Auto-detect

        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert output_filepath.exists()

        ormd_content_full = output_filepath.read_text(encoding='utf-8')
        front_matter, body, _, _, parse_errors = parse_document(ormd_content_full)

        assert not parse_errors
        assert front_matter is not None
        assert front_matter.get("title") == "Title From Pluses"
        assert front_matter.get("authors") == ["Plus Author"]
        assert front_matter.get("keywords") == ["plus", "test"]

        dates_data = front_matter.get("dates")
        assert dates_data is not None
        assert isinstance(dates_data.get("created"), datetime)
        assert dates_data.get("created").isoformat().startswith(original_created_date.rstrip("Z"))
        assert dates_data.get("modified") != original_modified_date # Overridden
        assert isinstance(dates_data.get("modified"), str)
        # Check that modified is more recent than created
        assert datetime.fromisoformat(dates_data.get("modified")) > dates_data.get("created") # Compare datetime objects


        assert front_matter.get("conversion_details", {}).get("from_format") == "md"
        expected_body = "## Body with Plus FM\n\nContent after plus front-matter."
        assert body.strip() == expected_body.strip()

    def test_convert_md_file_already_ormd(self, tmp_path):
        """Test converting a file that is already ORMD (with .md extension)."""
        runner = CliRunner()
        input_filename = "already_an_ormd.md" # Note .md extension
        output_filename = "already_an_ormd_converted.ormd"

        input_filepath = tmp_path / input_filename
        output_filepath = tmp_path / output_filename

        original_created = "2020-01-01T00:00:00Z"
        original_modified = "2020-01-02T00:00:00Z"

        sample_ormd_content = f"""<!-- ormd:0.1 -->
---
title: Original ORMD Title
authors: ["Original Author"]
dates:
  created: {original_created}
  modified: {original_modified} # This will be updated
---
# Original ORMD Body

This is an ORMD document.
"""
        input_filepath.write_text(sample_ormd_content, encoding='utf-8')

        result = runner.invoke(cli, [
            'convert', str(input_filepath), str(output_filepath), '--input-format', 'md'
        ])

        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert output_filepath.exists()

        ormd_content_full = output_filepath.read_text(encoding='utf-8')
        front_matter, body, _, _, parse_errors = parse_document(ormd_content_full)

        assert not parse_errors, f"Parsing errors: {parse_errors}"
        assert front_matter is not None

        assert front_matter.get("title") == "Original ORMD Title"
        assert front_matter.get("authors") == ["Original Author"]

        dates_data = front_matter.get("dates")
        assert dates_data is not None
        assert isinstance(dates_data.get("created"), datetime)
        assert dates_data.get("created").isoformat().startswith(original_created.rstrip("Z"))
        assert dates_data.get("modified") != original_modified # Updated
        assert datetime.fromisoformat(dates_data.get("modified")) > dates_data.get("created") # Compare datetime objects


        assert front_matter.get("source_file") == str(input_filepath.resolve())
        assert front_matter.get("conversion_details", {}).get("from_format") == "md"

        expected_body = "# Original ORMD Body\n\nThis is an ORMD document."
        assert body.strip() == expected_body.strip()

    def test_parse_pdf_date_string(self):
        """Test the _parse_pdf_date_string helper function directly."""
        # Import here to avoid issues if main.py is not fully importable during collection
        from ormd_cli.main import _parse_pdf_date_string

        # Valid cases
        assert _parse_pdf_date_string("D:20230401123045Z") == "2023-04-01T12:30:45Z"
        assert _parse_pdf_date_string("D:20230401103045+02'00'") == "2023-04-01T08:30:45Z" # Converted to UTC
        assert _parse_pdf_date_string("D:20230401153045-02'00'") == "2023-04-01T17:30:45Z" # Converted to UTC
        assert _parse_pdf_date_string("D:202304011230Z") == "2023-04-01T12:30:00Z"
        assert _parse_pdf_date_string("D:2023040112Z") == "2023-04-01T12:00:00Z"
        assert _parse_pdf_date_string("D:20230401Z") == "2023-04-01T00:00:00Z"
        assert _parse_pdf_date_string("D:202304Z") == "2023-04-01T00:00:00Z" # Month only
        assert _parse_pdf_date_string("D:2023Z") == "2023-01-01T00:00:00Z" # Year only
        assert _parse_pdf_date_string("20230401123045+02'00'") == "2023-04-01T10:30:45Z" # No "D:" prefix - CORRECTED
        assert _parse_pdf_date_string("D:20230401") == "2023-04-01T00:00:00Z" # Date only
        assert _parse_pdf_date_string("D:20240130174918+00'00'") == "2024-01-30T17:49:18Z"

        # Invalid cases
        assert _parse_pdf_date_string(None) is None
        assert _parse_pdf_date_string("") is None
        assert _parse_pdf_date_string("invalid_date") is None
        assert _parse_pdf_date_string("D:invalid") is None
        assert _parse_pdf_date_string(b"D:20230401123045Z") == "2023-04-01T12:30:45Z" # Bytes input
        assert _parse_pdf_date_string(b"invalid bytes") is None

    def test_convert_pdf_invalid_file_causes_error(self, tmp_path):
        """Test PDF conversion with an invalid (non-PDF) file."""
        runner = CliRunner()
        input_filename = "invalid_is_actually_text.pdf"
        output_filename = "invalid_pdf_output.ormd"

        input_filepath = tmp_path / input_filename
        output_filepath = tmp_path / output_filename

        input_filepath.write_text("This is not a PDF content.", encoding='utf-8')

        result = runner.invoke(cli, ['convert', str(input_filepath), str(output_filepath)])

        assert result.exit_code != 0, "Command should fail for invalid PDF"
        assert "Failed to parse PDF for metadata (PDFSyntaxError)" in result.output or \
               "Failed to process PDF for text extraction (PDFSyntaxError)" in result.output or \
               "Failed to process PDF file" in result.output # More general error if it's not PDFSyntaxError

        assert not output_filepath.exists(), "Output file should not be created on PDF processing failure"

    def test_convert_pdf_empty_file_causes_error(self, tmp_path):
        """Test PDF conversion with an empty file named .pdf."""
        runner = CliRunner()
        input_filename = "empty.pdf"
        output_filename = "empty_pdf_output.ormd"

        input_filepath = tmp_path / input_filename
        output_filepath = tmp_path / output_filename

        input_filepath.touch() # Create empty file

        result = runner.invoke(cli, ['convert', str(input_filepath), str(output_filepath), '--input-format', 'pdf'])

        assert result.exit_code != 0, "Command should fail for empty PDF"
        assert "Failed to parse PDF for metadata (PDFSyntaxError)" in result.output or \
               "Failed to process PDF for text extraction (PDFSyntaxError)" in result.output or \
               "Failed to process PDF file" in result.output
        assert not output_filepath.exists(), "Output file should not be created for empty PDF"
