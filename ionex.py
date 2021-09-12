"""IONEX parser and handler."""


import datetime
import re

import numpy as np

from tecmap import TecMap


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

        self.bounds = dict(lat=[87.5, -87.5], dlat=2.5, lon=[-180, 180], dlon=5)

        self._get_bound("lat")
        self._get_bound("lon")

        self._tec_maps = []
        self._get_tec_maps()

    @property
    def map_shape(self):
        """Get shape of the map array."""
        num_rows = (self.bounds["lat"][0] - self.bounds["lat"][1]) / self.bounds["dlat"] + 1
        num_cols = (self.bounds["lon"][1] - self.bounds["lon"][0]) / self.bounds["dlon"] + 1
        return int(num_rows), int(num_cols)

    def _get_bound(self, bound_str):
        line_matcher = f"{bound_str.upper()}1 / {bound_str.upper()}2 / D{bound_str.upper()}"
        if line_matcher in self.ionex_str:
            # get everything before lat / lon marker
            bound_str = self.ionex_str.split(line_matcher)[0]
            # get the lat / lon marker line
            bound_str = bound_str.splitlines()[-1]
            # get a list of the lat / lon line items
            bound_list = list(map(float, bound_str.split()))
            if len(bound_list) != 3:
                raise ValueError(f"Too many elements in {line_matcher} definition {bound_str}")
            self.bounds[bound_str] = bound_list[0:2]
            self.bounds[f"d{bound_str}"] = bound_list[2]

    def _get_exponent(self):
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

        self._tec_maps.append(TecMap(map_array, epoch))
