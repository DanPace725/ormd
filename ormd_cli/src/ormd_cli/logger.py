import logging
import click # Not strictly needed here but good for consistency if SYMBOLS were used
import sys

# Define custom log levels if needed, or use standard ones
# For simplicity, we'll map verbose to DEBUG and quiet to CRITICAL or suppress.

logger = logging.getLogger("ormd_cli")

def setup_logging(verbose: bool, quiet: bool):
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    handler = logging.StreamHandler(sys.stdout)
    # Basic formatter, can be enhanced
    formatter = logging.Formatter("%(message)s")
    # For verbose, a more detailed formatter might be:
    # formatter = logging.Formatter("%(levelname)s: %(asctime)s: %(name)s: %(message)s")

    if quiet:
        # logger.setLevel(logging.CRITICAL + 10) # Effectively suppress all but "really bad"
        # Or, set a NullHandler to suppress all messages through this logger
        # handler = logging.NullHandler()
        # For now, let's make it show only CRITICAL
        level = logging.CRITICAL
        formatter = logging.Formatter("CRITICAL: %(message)s")
    elif verbose:
        level = logging.DEBUG
        formatter = logging.Formatter("DEBUG: %(message)s") # Simple debug format
    else:
        level = logging.INFO
        # Default info messages don't need a level prefix typically

    handler.setFormatter(formatter)

    # Remove existing handlers to avoid duplicate messages if setup_logging is called multiple times
    if logger.hasHandlers():
        logger.handlers.clear()

    logger.addHandler(handler)
    logger.setLevel(level)

    # Propagate to root logger if needed, or keep it contained.
    # For a CLI tool, usually, we don't want to interfere too much with other library logs
    # unless verbose is explicitly on.
    logger.propagate = False # Keep ormd_cli logs separate unless verbose
    if verbose:
        # If verbose, configure the root logger to show all DEBUG messages from any library
        # This might be too noisy, consider adjusting if needed.
        logging.basicConfig(level=logging.DEBUG, format="%(levelname)s: %(name)s: %(message)s")
        logger.propagate = True # Propagate our own messages to the verbose root logger
    elif quiet:
        # For quiet, ensure other loggers are also quieted if desired.
        # This is a bit aggressive; typically, you only control your own app's logger.
        # For now, we only control our app's logger.
        pass
    else: # Default INFO level
        # Ensure basicConfig is called at least once if no other logging is set up by other libs
        # This sets up a default handler for the root logger if one isn't already configured.
        # We only want our specific handler for our logger by default, not affecting root.
        pass
