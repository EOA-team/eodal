#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Jul 27 10:52:22 2022

@author: orianif
"""
#%%
import geopandas as gpd
from pathlib import Path
from shapely.geometry import Polygon
from eodal.core.sensors import Sentinel2
from eodal.core.band import Band
import matplotlib.pyplot as plt
import numpy as np
from copy import deepcopy
from scipy.ndimage import rotate


#%% IMPORT DATA

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

#%% Q_RISC - quantile band rescaling
# useful to improve visibility of a single raster image.
original=deepcopy(s2_ds)
riscaled=Band.q_risc(original,'B02',qmin=0.01,qmax=0.99)

plt.figure()
plt.subplot(1,2,1)
plt.imshow(original['B02'].values.data)
plt.title('B02 band - original')
plt.subplot(1,2,2)
plt.imshow(riscaled)
plt.title('B02 band - quantile-riscaled')

#%% IM_RISC - quantile band rescaling to entire RasterCollection object
# Useful to improve the visualization of an entire Raster Collection.

original=deepcopy(s2_ds)
rescaled=Band.im_risc(original,qmin=0.01,qmax=0.99)

plt.figure()
ax1=plt.subplot(1,2,1)
original.plot_multiple_bands(band_selection=['B04','B03','B02'],ax=ax1)
plt.title('original colors')
ax2=plt.subplot(1,2,2)
rescaled.plot_multiple_bands(band_selection=['B04','B03','B02'],ax=ax2)
plt.title('rescaled colors')