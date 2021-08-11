"""TEC map handling module."""

from pathlib import Path
from functools import partial

import numpy as np
from pyproj import CRS, Transformer
from bokeh.models.widgets import Div
from bokeh.layouts import column
from bokeh.themes import Theme
from bokeh.plotting import figure, curdoc
from bokeh.models import LinearColorMapper, ColorBar
from bokeh.palettes import Viridis

import holoviews as hv
import holoviews.plotting.bokeh
import geoviews as gw

class TecMap:
    """TEC map class.

    Stores a map of TEC data.

    Provides also a functionality to generate a bokeh plot of the TEC map.
    """

    # TODO: Do not hardcode the following
    DELTA_LAT = 2.5  # Delta of latitudes in the TEC map
    DELTA_LON = 5  # Delta of longitudes in the TEC map
    MINMAX_LAT = 87.5  # Absolute value of minimum and maximum latitudes
    MINMAX_LON = 180  # Absolute value of minimum and maximum longitudes
    LAT_SPAN = (
        MINMAX_LAT * 2
    )  # Maximum latitude difference in the opposite ends of the plot
    LON_SPAN = (
        MINMAX_LON * 2
    )  # Maximum longitude difference in the opposite ends of the plot

    # plot dimensions
    PLOT_HEIGHT = 800
    PLOT_WIDTH = 1100

    # font sizes
    LABEL_FONT_SIZE = "20px"
    TITLE_FONT_SIZE = "30px"

    def __init__(self, map_arr, epoch):
        """Init the instance.

        Args:
            map_arr([np.array]): Array representing the TEC map.
            epoch([datetime.datetime]): Datetime of the map epoch
        """
        self._map_arr = map_arr
        self.epoch = epoch
        self.epoch_str = self.epoch.strftime("%m/%d/%Y %H:%M")

    def get_tec(self, lat, lon):
        """Get tec for coordiantes."""
        i = round((87.5 - lat) * (self._map_arr.shape[0] - 1) / (2 * 87.5))
        j = round((180 + lon) * (self._map_arr.shape[1] - 1) / 360)
        return self._map_arr[i, j]

    @property
    def map(self):
        """Get the TEC map as a numpy array.

        Array indices are lat, lon.
        """
        return self._map_arr

    @property
    def lats(self):
        """Get latitudes of the TEC map."""
        return np.arange(-87.5, 87.5, self.DELTA_LAT)

    @property
    def lons(self):
        """Get longitudes of the TEC map."""
        return np.arange(-180, 180, self.DELTA_LON)

    def plot(self, max_tec=100):
        """Plot tec map."""
        color_mapper = LinearColorMapper(palette=Viridis[11], low=0, high=max_tec)
        color_bar = ColorBar(
            color_mapper=color_mapper,
            label_standoff=5,
        )
        color_bar.title = "Total Electron Content [TECU]"
        color_bar.title_text_font_size = self.LABEL_FONT_SIZE
        tools = "wheel_zoom,box_zoom,pan,reset"

        plot = figure(
            title=f"TEC Map for {self.epoch_str}",
            plot_height=self.PLOT_HEIGHT,
            plot_width=self.PLOT_WIDTH,
            toolbar_location="above",
            tools=tools,
        )
        plot.xgrid.visible = False
        plot.ygrid.visible = False

        # plot the map
        plot.image(
            image=[self.map],
            x=-self.MINMAX_LON,
            y=-self.MINMAX_LAT,
            dw=self.LON_SPAN,
            dh=self.LAT_SPAN,
            color_mapper=color_mapper,
            level="image",
        )

        plot.yaxis.axis_label = "Latitude [deg]"
        plot.xaxis.axis_label = "Longitude [deg]"

        # set styles
        plot.title.align = "center"
        plot.title.text_font_size = self.TITLE_FONT_SIZE
        plot.yaxis.axis_label_text_font_size = self.LABEL_FONT_SIZE
        plot.xaxis.axis_label_text_font_size = self.LABEL_FONT_SIZE

        # add marin to the plot
        plot.margin = [10, 0, 30, 20]


        # disable padding
        plot.x_range.range_padding = 0
        plot.y_range.range_padding = 0

        # Specify figure layout.
        plot.add_layout(color_bar, "right")

        renderer = hv.renderer('bokeh').instance(mode='server')
        dir_path = Path(__file__).parent.resolve()
        yaml_path = dir_path / "theme.yaml"
        renderer.theme = Theme(yaml_path)
        img = gw.Image(self.map, bounds=(-180, -87.5, 180, 87.5))
        img = img.redim.range(z=(0, max_tec))
        img.opts(width=self.PLOT_WIDTH, height=self.PLOT_HEIGHT, cmap="Viridis", colorbar=True)
        hvplot = renderer.get_plot(img * gw.feature.coastline(), curdoc())
        layout = hvplot.state
        title_div = Div(text=f"<h1>TEC Map for {self.epoch_str}</h1>", style={"text-align": "center"}, width=self.PLOT_WIDTH)
        return column(title_div, layout)
