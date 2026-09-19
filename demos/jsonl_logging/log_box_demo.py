#! python 3
# To be run in rhino

import rhinoscriptsyntax as rs

from run_in_rhino.rhino_env.jsonl_logger import JsonlLogger

logger = JsonlLogger(globals().get("RUN_IN_RHINO_LOG"))

with logger:
    logger.log("adding a box")
    corners = [
        (-5, -5, 0), (5, -5, 0), (5, 5, 0), (-5, 5, 0),
        (-5, -5, 10), (5, -5, 10), (5, 5, 10), (-5, 5, 10),
    ]
    rs.AddBox(corners)
    logger.log({"object_count": len(rs.AllObjects())}, type="data")
    logger.log("box added")
