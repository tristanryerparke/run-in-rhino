# r: pydantic

from typing import Literal
from pydantic import BaseModel


class ServerStopMessage():
    type: Literal["stop"] = "stop"

class ServerQuitMessage():
    type: Literal["quit"] = "quit"

class ServerDataMessage():
    type: Literal["data"] = "data"
    data: str

class ServerTerminalMessage():
    type: Literal["terminal"] = "terminal"
    terminal_text: str

