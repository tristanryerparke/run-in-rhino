from pathlib import Path

import pytest

from run_in_rhino.app_control.instance import launch_rhino


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BLANK_FILE = PROJECT_ROOT / "blank_file.3dm"


@pytest.fixture(scope="session")
def rhino_instance():
    with launch_rhino(BLANK_FILE) as instance:
        yield instance
