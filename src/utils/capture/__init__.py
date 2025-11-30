from .stream import CaptureStream
from .target import (
    MonitorIdentifier,
    WindowHandle,
    get_nime_window_text,
    enumerate_windows,
)

__all__ = [
    "CaptureStream",
    "MonitorIdentifier",
    "WindowHandle",
    "get_nime_window_text",
    "enumerate_windows",
]
