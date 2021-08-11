#!/usr/bin/env python3
"""IONEX file handling."""

from collections import OrderedDict
import ftplib
import pycurl
from functools import partial
from pathlib import Path
import datetime
import unlzw3
import os
import tempfile

from bokeh.models.widgets import Div, DatePicker, Slider, Dropdown
from bokeh.layouts import column, row
from bokeh.plotting import curdoc

from ionex import IonexHandler


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

    def __init__(self, cache_dir=None, starting_date=None):
        """Init instance of application.

        Args:
            cache_dir ([str]): Path to use for caching the IONEX files
        """
        self._init = False

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
        self._selections = dict(analysis_center="c2p", date_str=starting_date, hour=12, max_tec=100)

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
        return datetime.datetime.strptime(self._selections["date_str"], self._BOKEH_DATE_FMT).date()

    @property
    def year(self):
        """Get selected year as string."""
        return self.date.strftime("%y")

    @property
    def year_centry(self):
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

        return self.cache_dir / "ionex" / self.year_centry / self.doy / self.filename

    @staticmethod
    def ionex_file_ok(file_path):
        """Check if IONEX file is ok."""
        return file_path.exists() and file_path.stat().st_size > 0

    def _read_ionex(self, file_path):
        """Read IONEX file and return it as string."""
        file_path = Path(file_path)
        if not self.ionex_file_ok(file_path):
            return None

        # uncompress the file
        return unlzw3.unlzw(file_path).decode("utf-8")

    def _get_ionex_str(self):
        """Get IONEX file from cache or download from online source."""
        # check if we have path for caching
        if self.cache_path is not None:
            # check if the file is not already cached and if cached, it should not be empty
            if not self.ionex_file_ok(self.cache_path):
                # create dir for the file
                os.makedirs(self.cache_path.parents[0], exist_ok=True)
                # download file to cache
                self._download_ionex(self.cache_path)
            if self.cache_path.exists() and not self.ionex_file_ok(self.cache_path):
                self.cache_path.unlink()
            # read cached file
            return self._read_ionex(self.cache_path)

        # open temp file for handling the IONEX
        with tempfile.NamedTemporaryFile() as fp:
            # download IONEX file to the temp
            self._download_ionex(fp.name)
            # read IONEX from the temp
            return self._read_ionex(fp.name)

    def _download_ionex(self, dest_path, remove_on_error=False):
        """Download IONEX file."""

        # ftplib does not play nicely with ufw firewall
        # ftp = ftplib.FTP("gssc.esa.int", timeout=10)
        # ftp.login()
        # try:
        #     print(f"igs/products/ionex/{self.year_centry}/{self.doy}/{self.filename}")
        #     ftp.cwd(f"igs/products/ionex/{self.year_centry}/{self.doy}")
        #     with open(dest_path, "wb") as fp:
        #         ftp.retrbinary(f"RETR {self.filename}", fp.write)
        # except ftplib.error_perm:
        #     # signal failure
        #     return False
        with open(dest_path, "wb") as fp:
            curl = pycurl.Curl()
            ftp_path = f"igs/products/ionex/{self.year_centry}/{self.doy}/{self.filename}"
            curl.setopt(pycurl.URL, f"ftp://gssc.esa.int/{ftp_path}")
            curl.setopt(pycurl.FTPPORT, ":54010-54020")
            curl.setopt(pycurl.WRITEDATA, fp)
            curl.perform()
            curl.close()

    def _update_tec_map(self):
        """Update tec map plot."""
        # get tec map
        tec_map = self._ionex_handler.get_tec_map(self._selections["hour"])

        # create IONEX handler
        if tec_map is None:
            self._ui_elements["plots"] = [Div(text="<h1>No IONEX data available for the given selection</h1>", width=800)]
        else:
            self._ui_elements["plots"] = [tec_map.plot(self._selections["max_tec"])]

        self._update_ui()

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
            title="Date", value=self._selections["date_str"], min_date="2000-01-01", max_date=self._yesterday
        )
        date_picker.on_change("value", self._update_date_selection)

        # add hour picker
        hour_slider = Slider(start=0, end=23, value=self._selections["hour"], step=1, title="Hour of day")
        hour_slider.on_change("value", partial(self._update_def_selection, key="hour"))

        # add pickers
        elements.append(Div(text="<h2>Pick date and hour of day:</h2>"))
        elements.append(row([date_picker, hour_slider]))

        # add analysis center selector
        menu = [(val, key) for key, val in self.ANALYSIS_CENTERS.items()]
        analysis_center = Dropdown(label="Analysis center", menu=menu, css_classes =['custom_button_bokeh'])
        analysis_center.on_click(partial(self._update_analysis_center_selection, analysis_center))
        self._set_analysis_center_selection_label(analysis_center, self._selections["analysis_center"])

        # add max tec slider
        max_tec = Slider(start=5, end=200, value=self._selections["max_tec"], step=5, title="Max TEC [TECU]")
        max_tec.on_change("value", partial(self._update_def_selection, key="max_tec"))

        elements.append(Div(text="<h2>Configure IONEX handling:</h2>"))
        elements.append(row(analysis_center, max_tec))

        self._ui_elements["pickers"] = [column(elements)]

    def _update_def_selection(self, attr, old, new, key):
        """Update user selections."""
        # convert string to date
        self._selections[key] = new

        self._update_tec_map()

    def _update_date_selection(self, attr, old, new):
        """Update user selections."""
        self._selections["date_str"] = new
        self._update_ionex()

    def _set_analysis_center_selection_label(self, dropdown, analysis_center_acro):
        """Set label for the analysis center selection."""
        dropdown.label = f"Analysis center - {self.ANALYSIS_CENTERS[analysis_center_acro]}"

    def _update_analysis_center_selection(self, dropdown, event):
        """Update user selection of the analysis center."""
        self._selections["analysis_center"] = event.item

        self._set_analysis_center_selection_label(dropdown, self._selections["analysis_center"])

        self._update_ionex()

    def _update_ionex(self):
        """Update used IONEX file."""
        self._ionex_handler = IonexHandler(self._get_ionex_str())

        self._update_tec_map()
