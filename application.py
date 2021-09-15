#!/usr/bin/env python3
"""IONEX file handling."""

import logging
import sys
from collections import OrderedDict
from functools import partial
from pathlib import Path
import datetime

from bokeh.models.widgets import Div, DatePicker, Slider, Dropdown
from bokeh.layouts import column, row
from bokeh.plotting import curdoc

from ionex import IonexHandler, IonexDownloader


class TecMapperApplication:
    """TEC mapper bokeh application."""

    _BOKEH_DATE_FMT = "%Y-%m-%d"

    ANALYSIS_CENTERS = {
        "cod": "CODE",
        "cor": "CODE Rapid",
        "c1p": "CODE 1d",
        "c2p": "CODE 2d",
        "emr": "NRCAN",
        "esa": "ESA",
        "esr": "ESA Rapid",
        "jpl": "JPL",
        "jpr": "JPL Rapid",
        "igs": "IGS",
        "igr": "IGS Rapid",
    }

    def __init__(self, cache_dir=None, starting_date=None, verbose=False):
        """Init instance of application.

        Args:
            cache_dir ([str]): Path to use for caching the IONEX files
        """
        self._init = False

        self.logger = logging.getLogger("TecMapper")
        formatter = logging.Formatter(fmt='[%(asctime)s]:%(levelname)s:%(name)s: %(message)s',
            datefmt='%H:%M:%S')
        self.logger.parent.handlers[0].setFormatter(formatter)

        if verbose:
            self.logger.setLevel(logging.INFO)

        self.logger.info("Initializing TEC Mapper")

        # store arguments
        self.cache_dir = Path(cache_dir)

        # UI element dict
        self._ui_elements = OrderedDict()
        self._ui_elements["pickers"] = []
        self._ui_elements["plots"] = []

        # get date for yesterday
        self._yesterday = datetime.date.today() - datetime.timedelta(days=1)

        # get starting date
        if starting_date is None:
            starting_date = self._yesterday.strftime(self._BOKEH_DATE_FMT)

        # user selection dict
        self._selections = dict(
            analysis_center="c2p", date_str=starting_date, hour=12, max_tec=100
        )

        # IONEX data handler
        self._ionex_handler = None

        # generate ui elements
        self._generate_ui()

        self._init = True

        # make initial plot
        self._update_ionex()

        # update ui
        self._update_ui()

    @property
    def date(self):
        """Get Date object of the selected date string."""
        return datetime.datetime.strptime(
            self._selections["date_str"], self._BOKEH_DATE_FMT
        ).date()

    @property
    def year(self):
        """Get selected year as string."""
        return self.date.strftime("%y")

    @property
    def year_century(self):
        """Get selected year as string."""
        return self.date.strftime("%Y")

    @property
    def doy(self):
        """Get selected day of year as string."""
        return self.date.strftime("%j")

    @property
    def analysis_center_fn(self):
        """Get analysis center part of the filename string."""
        return f"{self._selections['analysis_center']}g"

    @property
    def filename(self):
        """Get filename for the ionex file."""
        return f"{self.analysis_center_fn}{self.doy}0.{self.year}i.Z"

    @property
    def cache_path(self):
        """Get cached path for the IONEX file."""
        if self.cache_dir is None:
            return None

        return self.cache_dir / "ionex" / self.year_century / self.doy / self.filename

    def _update_tec_map(self):
        """Update tec map plot."""
        # get tec map
        self.logger.info("Getting TEC map")
        tec_map = self._ionex_handler.get_tec_map(self._selections["hour"])

        # create IONEX handler
        if tec_map is None:
            self._ui_elements["plots"] = [
                Div(
                    text="<h1>No IONEX data available for the given selection</h1>",
                    width=800,
                )
            ]
        else:
            self._ui_elements["plots"] = [tec_map.plot(self._selections["max_tec"])]

        self.logger.info("Updating UI")
        self._update_ui()

        self.logger.info("TEC map updated")

    def _get_ui_column(self):
        """Get column for the UI."""
        elements = []
        for element_list in self._ui_elements.values():
            elements.extend(element_list)
        return column(elements)

    def _update_ui(self):
        """Update application UI."""
        if not self._init:
            # not initialized yet, do nothing
            return

        if not curdoc().roots:
            curdoc().add_root(self._get_ui_column())
            curdoc().title = "TEC Map Generator"
        else:
            curdoc().roots[0].children = [self._get_ui_column()]

    def _generate_ui(self):
        """Generate static elements of application UI.

        Args:
            elements: List of UI elements
        """
        elements = []

        # add date picker
        date_picker = DatePicker(
            title="Date",
            value=self._selections["date_str"],
            min_date="2000-01-01",
            max_date=self._yesterday,
        )
        date_picker.on_change("value", self._update_date_selection)

        # add hour picker
        hour_slider = Slider(
            start=0, end=23, value=self._selections["hour"], step=1, title="Hour of day"
        )
        hour_slider.on_change("value", partial(self._update_def_selection, key="hour"))

        # add pickers
        elements.append(Div(text="<h2>Pick date and hour of day:</h2>"))
        elements.append(row([date_picker, hour_slider]))

        # add analysis center selector
        menu = [(val, key) for key, val in self.ANALYSIS_CENTERS.items()]
        analysis_center = Dropdown(
            label="Analysis center", menu=menu, css_classes=["custom_button_bokeh"]
        )
        analysis_center.on_click(
            partial(self._update_analysis_center_selection, analysis_center)
        )
        self._set_analysis_center_selection_label(
            analysis_center, self._selections["analysis_center"]
        )

        # add max tec slider
        max_tec = Slider(
            start=5,
            end=200,
            value=self._selections["max_tec"],
            step=5,
            title="Max TEC [TECU]",
        )
        max_tec.on_change("value", partial(self._update_def_selection, key="max_tec"))

        elements.append(Div(text="<h2>Configure IONEX handling:</h2>"))
        elements.append(row(analysis_center, max_tec))

        self._ui_elements["pickers"] = [column(elements)]

    def _update_def_selection(self, attr, old, new, key):
        """Update user selections."""
        # convert string to date
        self._selections[key] = new
        self.logger.info(f"Updating selection {key} to {new}")
        self._update_tec_map()

    def _update_date_selection(self, attr, old, new):
        """Update user selections."""
        self.logger.info(f"Updating date selection to {new}")
        self._selections["date_str"] = new
        self._update_ionex()

    def _set_analysis_center_selection_label(self, dropdown, analysis_center_acro):
        """Set label for the analysis center selection."""
        dropdown.label = (
            f"Analysis center - {self.ANALYSIS_CENTERS[analysis_center_acro]}"
        )

    def _update_analysis_center_selection(self, dropdown, event):
        """Update user selection of the analysis center."""
        self._selections["analysis_center"] = event.item

        self._set_analysis_center_selection_label(
            dropdown, self._selections["analysis_center"]
        )

        self._update_ionex()

    def _update_ionex(self):
        """Update used IONEX file."""
        self.logger.info("Downloading IONEX")
        ionex_downloader = IonexDownloader(
            self.filename, self.year_century, self.doy, self.cache_path
        )

        self.logger.info("Handling IONEX")
        self._ionex_handler = IonexHandler(ionex_downloader.str)

        self.logger.info("Updating TEC map")
        self._update_tec_map()
