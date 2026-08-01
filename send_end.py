import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rhino_watcher import send_end_sync


send_end_sync()
