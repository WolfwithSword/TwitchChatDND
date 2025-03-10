import os
from helpers.utils import parse_args

args = parse_args()
os.environ['TCDND_DEBUG_MODE'] = '1' if args.debug else '0'
