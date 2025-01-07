import os, sys

def get_resource_path(relative_path):
    """Get absolute path to a resource, frozen or local (relative to helpers/utils.py)"""
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)