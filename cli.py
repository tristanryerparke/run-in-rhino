import argparse
import asyncio
import json
import sys

from orchestration import run_rhino_python_til_done
from pipe import run_script
from server_2 import RunContext


def rhino_watch(argv=None):
    parser = argparse.ArgumentParser(
        description="Run a script inside Rhino and watch its WebSocket output"
    )
    parser.add_argument("script", help="Rhino Python script path")
    parser.add_argument(
        "--nostop",
        action="store_true",
        help="Keep watching after a done message; quit still stops the server.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Make debug=true available to the Rhino script environment.",
    )
    parser.add_argument(
        "--noquit",
        action="store_true",
        help="Keep watching after both done and quit messages.",
    )
    args = parser.parse_args(argv)
    context = RunContext(
        stop=not (args.nostop or args.noquit),
        quit=not args.noquit,
        env={"debug": "true" if args.debug else "false"},
    )

    try:
        asyncio.run(
            run_rhino_python_til_done(
                args.script,
                context=context,
            )
        )
    except Exception as error:
        print("rhino-watch failed: {}".format(error), file=sys.stderr)
        return 1
    return 0


def in_rhino(argv=None):
    parser = argparse.ArgumentParser(
        description="Run a Python script in Rhino without starting a watcher"
    )
    parser.add_argument("script", help="Rhino Python script path")
    parser.add_argument(
        "--pipe-path",
        help="path to the RhinoCode pipe; uses the first available pipe by default",
    )
    args = parser.parse_args(argv)

    try:
        result = run_script(args.script, pipe_path=args.pipe_path)
    except Exception as error:
        print("in-rhino failed: {}".format(error), file=sys.stderr)
        return 1

    if result is not None:
        print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(rhino_watch())
