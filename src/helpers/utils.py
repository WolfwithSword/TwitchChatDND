import os, sys

def get_resource_path(relative_path, from_resources: bool = False):
    # Get absolute path to a resource, frozen or local (relative to helpers/utils.py)
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
        if from_resources:
            base_path = os.path.join(os.path.abspath("."), "resources")
        else:
            if not os.path.isfile(os.path.join(base_path, relative_path)):
                if not os.path.isdir(os.path.join(base_path, relative_path)):
                    base_path = os.path.dirname(os.path.abspath(__file__))
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)