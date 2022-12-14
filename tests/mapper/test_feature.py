'''
Tests for the Feature class (spatial filters for mapper)

.. versionadded:: 0.1.1

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

import pandas as pd
import pytest

from shapely.geometry import Point
from eodal.mapper.feature import Feature

def test_feature():

    # working constructor calls
    geom = Point([49,11])
    epsg = 4326
    name = 'Test Point'
    feature = Feature(name, geom, epsg)

    assert feature.geometry == geom, 'geometry differs'
    assert feature.epsg == epsg, 'EPSG code differs'
    assert feature.name == name, 'name differs'
    assert feature.attributes == {}, 'attributes must be empty'

    attributes = {'key': 'value'}
    feature = Feature(name, geom, epsg, attributes)
    assert feature.attributes == attributes, 'attributes differ'

    attributes = pd.Series({'key1': 'value1', 'key2': 'value2'})
    feature = Feature(name, geom, epsg, attributes)
    assert feature.attributes == attributes.to_dict(), 'attributes differ'

    gds = feature.to_geoseries()
    assert gds.name == feature.name, 'name differs'
    assert gds.crs.to_epsg() == feature.epsg, 'EPSG differs'
    assert gds.attrs == feature.attributes, 'attributes differ'

    # from_geoseries class method
    gds.attrs = {}
    feature = Feature.from_geoseries(gds)
    assert gds.name == feature.name, 'name differs'
    assert gds.crs.to_epsg() == feature.epsg, 'EPSG differs'
    assert gds.attrs == feature.attributes, 'attributes differ'

    # project into another spatial reference system
    feature_utm = feature.to_epsg(epsg=32632)
    assert feature_utm.epsg == 32632, 'projection had no effect'
    assert feature_utm.name == feature.name, 'name got lost'
    assert feature_utm.attributes == feature.attributes, 'attributes got lost'
