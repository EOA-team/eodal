#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EXAMPLE SCRIPT TO RESCALE COLORS IN ONE- OR MULTI-BAND IMAGES
FUNCTIONS USED: 
    eodal.core.algorithms.Band.im_risc()

Created on Wed Jul 27 10:52:22 2022
@author: Fabio Oriani, Agroscope
fabio.oriani <at> agroscope.admin.ch
"""
#%%
import geopandas as gpd
from pathlib import Path
from shapely.geometry import Polygon
from eodal.core.sensors import Sentinel2
from eodal.core.algorithms import im_risc
import matplotlib.pyplot as plt
#import numpy as np
from copy import deepcopy
#from scipy.ndimage import rotate
from eodal.config import get_settings

Settings = get_settings()
Settings.USE_STAC = False

#%% IMPORT DATA (a sentinel-2 image)

# file-path to the .SAFE dataset
dot_safe_dir = Path('../data/S2A_MSIL2A_20190524T101031_N0212_R022_T32UPU_20190524T130304.SAFE')

# construct a bounding box for reading a spatial subset of the scene (geographic coordinates)
ymin, ymax = 47.949, 48.027
xmin, xmax = 11.295, 11.385
bbox = Polygon([(xmin, ymin), (xmax, ymin), (xmax, ymax), (xmin, ymax)])

# eodal expects a vector file or a GeoDataFrame for spatial sub-setting
bbox_gdf = gpd.GeoDataFrame(geometry=[bbox], crs=4326)

# read data from .SAFE (all 10 and 20m bands + scene classification layer)
s2_ds = Sentinel2().from_safe(
    in_dir=dot_safe_dir,
    vector_features=bbox_gdf
)

# eodal support band aliasing. Thus, you can access the bands by their name ...
s2_ds.band_names

#%% IM_RISC - quantile band rescaling to bands in a RasterCollection object
# Useful to improve the visualization of a selection of bands. The outpèut is 
# a resterColelction of the original type with the selected bands rescaled. To
# rescale the entire collection omit the bands field.

original=deepcopy(s2_ds)
rescaled=im_risc(original,bands=['B02','B03','B04'],qmin=0.01,qmax=0.99)

plt.figure()
ax1=plt.subplot(1,2,1)
original.plot_multiple_bands(band_selection=['B04','B03','B02'],ax=ax1)
plt.title('original colors')
ax2=plt.subplot(1,2,2)
rescaled.plot_multiple_bands(band_selection=['B04','B03','B02'],ax=ax2)
plt.title('rescaled colors')