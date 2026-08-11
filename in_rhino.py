import argparse
import json
import sys

from pipe import run_script


def main(argv=None):
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
    raise SystemExit(main())
