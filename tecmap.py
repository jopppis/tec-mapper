"""TEC map handling module."""

from pathlib import Path
import datetime
from dataclasses import dataclass

import numpy as np
from bokeh.models.widgets import Div
from bokeh.layouts import column
from bokeh.themes import Theme
from bokeh.plotting import curdoc

import holoviews as hv
import holoviews.plotting.bokeh
import geoviews as gw


@dataclass
class MapBounds:
    """Storage for IONEX TEC map data bounds."""
    min_lat: float = -87.5
    max_lat: float = 87.5
    dlat: float = 2.5

    min_lon: float = -180
    max_lon: float = 180
    dlon: float = 5

    @property
    def lat_span(self) -> float:
        """Get span of latitudes."""
        return self.max_lat - self.min_lat

    @property
    def lon_span(self) -> float:
        """Get span of longitudes."""
        return self.max_lon - self.min_lon

    @property
    def num_rows(self) -> int:
        """Get map array row count."""
        return int(self.lat_span / self.dlat + 1)

    @property
    def num_cols(self) -> int:
        """Get map array column count."""
        return int(self.lon_span / self.dlon + 1)

    @property
    def lats(self):
        """Get latitudes as a range."""
        return np.arange(self.min_lat, self.max_lat, self.dlat)

    @property
    def lons(self):
        """Get longitudes as a range."""
        return np.arange(self.min_lon, self.max_lon, self.dlon)


class TecMap:
    """TEC map class.

    Stores a map of TEC data.

    Provides also a functionality to generate a bokeh plot of the TEC map.
    """

    # plot dimensions
    PLOT_HEIGHT = 600
    PLOT_WIDTH = 1100

    # font sizes
    LABEL_FONT_SIZE = "20px"
    TITLE_FONT_SIZE = "30px"

    def __init__(self, epoch : datetime.datetime, map_arr: np.array, bounds: MapBounds):
        """Init the instance.

        Args:
            epoch([datetime.datetime]): Datetime of the map epoch
            map_arr([np.array]): Array representing the TEC map.
            bounds([MapBounds]): Bounds of the map array
        """
        self._map_arr = map_arr
        self._bounds = bounds
        self.epoch = epoch
        self.epoch_str = self.epoch.strftime("%m/%d/%Y %H:%M")

    def get_tec(self, lat, lon):
        """Get tec for coordiantes."""
        i = round((self._bounds.max_lat - lat) * (self._bounds.num_rows - 1) / self._bounds.lat_span)
        j = round((self._bounds.max_lon + lon) * (self._bounds.num_cols - 1) / self._bounds.lon_span)
        return self._map_arr[i, j]

    @property
    def map(self):
        """Get the TEC map as a numpy array.

        Array indices are lat, lon.
        """
        return self._map_arr

    def plot(self, max_tec=100):
        """Plot tec map."""
        renderer = hv.renderer('bokeh').instance(mode='server')
        dir_path = Path(__file__).parent.resolve()
        yaml_path = dir_path / "theme.yaml"
        renderer.theme = Theme(yaml_path)
        img = gw.Image(self.map, bounds=(self._bounds.min_lon, self._bounds.min_lat, self._bounds.max_lon, self._bounds.max_lat))
        img = img.redim.range(z=(0, max_tec))
        img.opts(width=self.PLOT_WIDTH, height=self.PLOT_HEIGHT, cmap="Viridis", colorbar=True)
        hvplot = renderer.get_plot(img * gw.feature.coastline())
        layout = hvplot.state
        title_div = Div(text=f"<h1>TEC Map for {self.epoch_str}</h1>", style={"text-align": "center"}, width=self.PLOT_WIDTH)
        return column(title_div, layout)
