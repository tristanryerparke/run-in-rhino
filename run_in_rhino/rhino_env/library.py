#! python 3
# r: websocket-client
# To be run in rhino

import os
import sys


def install_library_path():
    """Make the directory containing ``run_in_rhino`` importable in Rhino."""
    package_root = os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    )

    if package_root in sys.path:
        sys.path.remove(package_root)

    sys.path.insert(0, package_root)
    return package_root


if __name__ == "__main__":
    install_library_path()
