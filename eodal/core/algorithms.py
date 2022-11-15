"""
EODAL-CORE ALGORITHMS MODULE

Collection of methods applicable to rastCollection object of the package Eodal.

Copyright (C) 2022 Fabio Oriani, Agroscope, fabio.oriani <at> agroscope.admin.ch

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
"""

import numpy as np
from copy import deepcopy
from eodal.core.raster import RasterCollection
from typing import List, Optional


def im_risc(rcoll: RasterCollection, bands: Optional[List[str]] = None, qmin: Optional[float] = 0.01, qmax: Optional[float] = 0.91, no_data: Optional[float] = 0.) -> RasterCollection:
    
    """
    Applies q_risc (Quantile-based min-max rescaling) to a selection of bands 
    of a RasterCollection object.
    
    :param rcoll:
        RasterCollection object, containing the band to rescale.
    :param bands:
        selection of band names to rescale. default = [] means all
        bands are taken.
    :param qmin:
        scalar in [0,1], minium quantile base for the rescale. 
        values <= qmin-quantile are set to zero. default = 0.99
    :param qmax:
        scalar in [0,1], maximum quantile base for the rescale. 
        values >= qmax-quantile are set to 1. default = 0.99
    """
    
    if bands == None:
        bands=rcoll.band_names
    #empty copy of input RC
    rcoll_out = deepcopy(rcoll)
    rcoll_out._collection = {}
    rcoll_out._band_aliases = []
    
    for b in bands:
        rcoll_out.add_band(rcoll[b])
        dt_tmp = rcoll[b].values.data.dtype
        band_out = np.copy(rcoll[b].values.data)
        band_tmp = band_out[np.logical_not(rcoll[b].values.mask)]
        vmin = np.quantile(band_tmp, qmin)
        vmax = np.quantile(band_tmp, qmax)
        band_out[band_out<vmin] = vmin
        band_out[band_out>vmax] = vmax
        band_out = (band_out-vmin)/(vmax-vmin)
        rcoll_out[b].values.data.setfield(band_out, dtype=dt_tmp)
    
    return rcoll_out