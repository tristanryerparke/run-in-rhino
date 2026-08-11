#! python 3
# To be run in rhino

class NotInRhinoEnvException(RuntimeError):
    pass

def check_rhino_env():
    """checks to see if we are in the rhino python 3 environment or not"""
    try:
        import Rhino
    except ImportError as exc:
        raise NotInRhinoEnvException("Rhino environment is unavailable") from exc