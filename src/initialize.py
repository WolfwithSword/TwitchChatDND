import os
import sys
import subprocess
import argparse
import static_ffmpeg


def parse_args():
    parser = argparse.ArgumentParser(description="Run the application.")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging level.")
    return parser.parse_args()

_args = parse_args()
os.environ["TCDND_DEBUG_MODE"] = "1" if _args.debug else "0"

from custom_logger.logger import logger # pylint: disable=wrong-import-position

logger.info("Setting up ffmpeg...")
static_ffmpeg.add_paths()
logger.info("Done setting up ffmpeg")

# Try to hide consoles from subproccesses
if sys.platform == "win32":
    _original_popen = subprocess.Popen

    def silent_popen(*args, **kwargs):
        kwargs.setdefault("creationflags", subprocess.CREATE_NO_WINDOW)
        return _original_popen(*args, **kwargs)

    subprocess.Popen = silent_popen
