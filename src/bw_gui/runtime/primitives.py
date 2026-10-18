from __future__ import annotations

import tkinter as _tk
from tkinter import font as _tkfont

from . import _ttk_facade

# App code imports these aliases from bw_gui.runtime instead of importing tkinter directly.
# ``widgets`` is the ttk namespace with bw-gui primitives in place of ttk ones (``Scrollbar``).
ui = _tk
widgets = _ttk_facade
fonts = _tkfont
