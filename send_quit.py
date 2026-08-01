import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rhino_watcher import send_quit_sync


send_quit_sync()
