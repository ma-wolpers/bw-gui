"""DataGrid — virtualised canvas table with frozen left/right regions and splitters.

Public API::

    from bw_gui.widgets.data_grid import DataGrid, GridColumn, GridRow, Region

See ``_grid.py`` for the behaviour contract and ``docs/DATA_GRID_CONTRACT.md``.
"""

from ._grid import DataGrid
from ._model import GridColumn, GridRow, Region

__all__ = ["DataGrid", "GridColumn", "GridRow", "Region"]
