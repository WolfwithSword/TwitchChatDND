import os
import argparse


def parse_args():
    parser = argparse.ArgumentParser(description="Run the application.")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging level.")
    return parser.parse_args()


args = parse_args()
os.environ["TCDND_DEBUG_MODE"] = "1" if args.debug else "0"
