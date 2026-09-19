#! python 3
# To be run in rhino

import Rhino

from run_in_rhino.rhino_env.jsonl_logger import JsonlLogger

logger = JsonlLogger(globals().get("RUN_IN_RHINO_LOG"))


def log_on_idle(sender, event_args):
    logger.log("idle tick")


Rhino.RhinoApp.Idle += log_on_idle
logger.log("idle handler subscribed")
logger.send_done()

# Run this demo with --nostop: the done message above is ignored and the
# watcher keeps printing idle ticks until you stop it with Ctrl+C.
