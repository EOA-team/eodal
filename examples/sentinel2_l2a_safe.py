"""
Sample script showing how to load data from a Sentinel-2 scene
organized in .SAFE (Standard Archive Format for Europe) into a
`Sentinel-2` object.

The Sentinel-2 scene can be downloaded here:
https://data.mendeley.com/datasets/ckcxh6jskz/1
"""

import geopandas as gpd
from pathlib import Path
from shapely.geometry import Polygon
from eodal.core.sensors import Sentinel2

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
# >>> ['B02', 'B03', 'B04', 'B05', 'B06', 'B07', 'B08', 'B8A', 'B11', 'B12', 'SCL']
# ... or by their alias, i.e., their color name
s2_ds.band_aliases
# >>> ['blue', 'green', 'red', 'red_edge_1', 'red_edge_2', 'red_edge_3', 'nir_1', 'nir_2', 'swir_1', 'swir_2', 'scl']

# plot false-color infrared preview
fig_nir = s2_ds.plot_multiple_bands(band_selection=['nir_1','red','green'])
fig_nir.savefig('../img/AgriSatPy_Sentinel-2_NIR.png', dpi=150, bbox_inches='tight')

# plot scene classification layer
fig_scl = s2_ds.plot_scl()
fig_scl.savefig('../img/AgriSatPy_Sentinel-2_SCL.png', dpi=150, bbox_inches='tight')

# calculate the NDVI using 10m bands (no spatial resampling required)
s2_ds.calc_si('NDVI', inplace=True)
fig_ndvi = s2_ds.plot_band('NDVI', colormap='summer', vmin=-1, vmax=1)
fig_ndvi.savefig('../img/AgriSatPy_Sentinel-2_NDVI.png', dpi=150, bbox_inches='tight')

# mask the water (SCL class 6); requires resampling to 10m spatial resolution
s2_ds.resample(target_resolution=10, inplace=True)
s2_ds.mask(
    mask='SCL',
    mask_values=[6],
    bands_to_mask=['NDVI'],
    inplace=True
)
fig_ndvi = s2_ds.plot_band('NDVI', colormap='summer', vmin=-1, vmax=1)
fig_ndvi.savefig('../img/AgriSatPy_Sentinel-2_NDVI_masked.png', dpi=150, bbox_inches='tight')
