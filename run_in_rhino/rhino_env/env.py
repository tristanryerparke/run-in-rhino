#! python 3
# To be run in rhino

import os


STICKY_ENVIRONMENT_KEY = "run_in_rhino.env"


def install_sticky_environment(connection=None):
    """Store the server environment in Rhino's sticky state when connected."""
    if connection is None:
        return None
    environment = connection.get_env()

    import scriptcontext as sc

    sc.sticky[STICKY_ENVIRONMENT_KEY] = environment
    return environment


def install_os_environment(connection=None):
    """Add the server environment to ``os.environ`` when connected."""
    if connection is None:
        return None
    environment = connection.get_env()
    os.environ.update(environment)
    return environment
