'''
Module defining geographic features for mapping.

Copyright (C) 2022 Lukas Valentin Graf

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
'''

class Feature:
    """
    Generic class for geographic features

    :attrib name:
        name of the feature (used for identification)
    :attrib geometry:
        `shapely` geometry of the feature in a spatial reference system
    :attrib crs:
        spatial coordinate reference system of the feature
    """
    def __init__(self, name: str, geometry, crs):
        """
        Class constructor
        """
        self._name = name
        self._geometry = geometry
        self._crs = crs

    def __repr__(self) -> str:
        return f'Feature name: {self.name}\nFeature Geometry: ' + \
            f'{self.geometry} (CRS: {self.crs})'

    @property
    def name(self) -> str:
        """the feature name"""
        return self._name

    @property
    def geometry(self):
        """the feature geometry"""
        return self._geometry

    @property
    def crs(self):
        """the feature coordinate reference system"""
        return self._crs