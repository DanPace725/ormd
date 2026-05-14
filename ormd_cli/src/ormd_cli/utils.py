import sys
import locale
from pathlib import Path

def get_view_template() -> str:
    """Reads and returns the content of the view_template.html file."""
    template_path = Path(__file__).parent / "templates" / "view_template.html"
    try:
        return template_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        # Fallback or error handling if template is missing
        # This could return a minimal default HTML or raise an error
        return "<html><body><h1>Error: View template not found.</h1></body></html>"
    except Exception as e:
        # Log error or handle other exceptions
        return f"<html><body><h1>Error loading view template: {e}</h1></body></html>"


def get_symbols():
    """
    Get appropriate symbols for the current terminal/platform.
    Returns Unicode symbols if supported, ASCII fallbacks otherwise.
    """
    # Check if we can safely use Unicode symbols
    can_use_unicode = True
    
    try:
        # Test if we can encode Unicode symbols with current stdout encoding
        test_symbols = "✅❌⚠️"
        if hasattr(sys.stdout, 'encoding') and sys.stdout.encoding:
            test_symbols.encode(sys.stdout.encoding)
        else:
            # Fallback to locale encoding
            test_symbols.encode(locale.getpreferredencoding())
    except (UnicodeEncodeError, LookupError):
        can_use_unicode = False
    
    # Also check for known problematic encodings
    encoding = getattr(sys.stdout, 'encoding', '').lower()
    if encoding in ('cp1252', 'ascii', 'latin-1'):
        can_use_unicode = False
    
    if can_use_unicode:
        return {
            'success': '✅',
            'error': '❌', 
            'warning': '⚠️',
            'info': '🔍',
            'bullet': '•'
        }
    else:
        return {
            'success': '[OK]',
            'error': '[ERROR]',
            'warning': '[WARN]',
            'info': '[INFO]',
            'bullet': '*'
        }

# Global symbols instance
SYMBOLS = get_symbols()
