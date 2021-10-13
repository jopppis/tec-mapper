"""IONEX parser and handler."""


import datetime
import re
from dataclasses import dataclass
# import ftplib
import os
import tempfile
from pathlib import Path

import pycurl
import unlzw3
import numpy as np

from tecmap import MapBounds, TecMap


class IonexDownloader:
    """Class to handle downloading of IONEX files."""

    def __init__(self, filename, year_century, doy, cache_path=None):
        """Init the instance."""
        self.cache_path = cache_path
        self.year_century = year_century
        self.doy = doy
        self.filename = filename

        self._ionex_str = self._get_ionex_str()

    @property
    def str(self):
        """Get downloaded IONEX as string."""
        return self._ionex_str

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
        #     print(f"igs/products/ionex/{self.year_century}/{self.doy}/{self.filename}")
        #     ftp.cwd(f"igs/products/ionex/{self.year_century}/{self.doy}")
        #     with open(dest_path, "wb") as fp:
        #         ftp.retrbinary(f"RETR {self.filename}", fp.write)
        # except ftplib.error_perm:
        #     # signal failure
        #     return False
        with open(dest_path, "wb") as fp:
            try:
                curl = pycurl.Curl()
                ftp_path = f"gnss/products/ionex/{self.year_century}/{self.doy}/{self.filename}"
                curl.setopt(pycurl.URL, f"ftp://gssc.esa.int/{ftp_path}")
                curl.setopt(pycurl.FTPPORT, ":54010-54020")
                curl.setopt(pycurl.WRITEDATA, fp)
                curl.perform()
                curl.close()
            except pycurl.error:
                # failed to download the file
                pass

class IonexHandler:
    """Class to read IONEX file and store TEC maps extracted from the IONEX data.

    The IONEX parsing is heavily affected by:
    https://github.com/daniestevez/jupyter_notebooks/blob/master/IONEX.ipynb
    """

    def __init__(self, ionex_str: str):
        """Init the instance.

        IONEX file can be simply input as:
            with open(file_path) as f:
                ionex_handler = IonexHandler(f.read())

        Args:
            ionex_str ([str]): IONEX file stored as a string.
        """
        self.ionex_str = ionex_str

        self.exponent = self._get_exponent()

        self.bounds = MapBounds()

        self._get_bound("lat")
        self._get_bound("lon")

        self._tec_maps = []
        self._get_tec_maps()

    @property
    def map_shape(self):
        """Get shape of the map array."""
        return self.bounds.num_rows, self.bounds.num_cols

    def _get_bound(self, bound_type_str):
        if self.ionex_str is None:
            return None

        line_matcher = f"{bound_type_str.upper()}1 / {bound_type_str.upper()}2 / D{bound_type_str.upper()}"
        if line_matcher in self.ionex_str:
            # get everything before lat / lon marker
            bound_str = self.ionex_str.split(line_matcher)[0]
            # get the lat / lon marker line
            bound_str = bound_str.splitlines()[-1]
            # get a list of the lat / lon line items
            bound_list = list(map(float, bound_str.split()))
            if len(bound_list) != 3:
                raise ValueError(f"Too many elements in {line_matcher} definition {bound_str}")
            if bound_type_str == "lat":
                self.bounds.min_lat = bound_list[0]
                self.bounds.max_lat = bound_list[1]
                self.bounds.dlat = bound_list[2]
            elif bound_type_str == "lon":
                self.bounds.min_lon = bound_list[0]
                self.bounds.max_lon = bound_list[1]
                self.bounds.dlon = bound_list[2]
            else:
                raise ValueError(f"Invalid bound_type_str {bound_type_str}")

    def _get_exponent(self):
        if self.ionex_str is None:
            return None

        line_matcher = "EXPONENT"
        if line_matcher in self.ionex_str:
            # get everything before EXPONENT marker
            exponent_str = self.ionex_str.split(line_matcher)[0]
            # get the exponent marker line
            exponent_str = exponent_str.splitlines()[-1]
            # store the exponent
            return int(exponent_str)

        # no exponent, set to 0 to disable scaling
        return 0

    @property
    def tec_maps(self):
        """Get all TEC maps from the file."""
        return self._tec_maps

    def get_tec_map(self, hour):
        """Get TEC map for a UTC hour."""
        if self.tec_maps is None:
            return None

        for tec_map in self.tec_maps:
            if tec_map.epoch.hour == hour:
                return tec_map
        return None

    def _get_tec_maps(self):
        """Get all tec maps from IONEX file."""
        if self.ionex_str is None:
            return None

        # each TEC map ends with END OF TEC MAP
        # the first map will include header and the last item in the list
        # will include everything after last map so skip it
        map_strs = re.split(".*END OF TEC MAP", self.ionex_str)[:-1]

        for map_str in map_strs:
            # discard everything before start of map
            map_str = map_str.split("START OF TEC MAP")[1]
            self._process_tec_map_str(map_str)

    def _process_tec_map_str(self, map_str):
        """Process single TEC map from a string containing a single TEC map."""
        def get_epoch():
            """Get epoch of the map."""
            # get the line with
            epoch_str = map_str.split("EPOCH OF CURRENT MAP")[0]
            epoch_str = epoch_str.splitlines()[-1]
            epoch_list = epoch_str.split()
            epoch_list = [int(epoch) for epoch in epoch_list]
            return datetime.datetime(*epoch_list)


        # get map epoch
        epoch = get_epoch()

        # get values for each latitude from the map by splitting the map from latitude definitions
        # skip the first one since there is other data before first latitude definition
        map_array = np.zeros(self.map_shape)
        for ix, lat_vals_str in enumerate(re.split(".*LAT/LON1/LON2/DLON/H", map_str)[1:]):
            lat_vals_list = lat_vals_str.split()
            map_array[ix,:] = lat_vals_list
        map_array = map_array * (10 ** self.exponent)

        self._tec_maps.append(TecMap(epoch, map_array, self.bounds))
