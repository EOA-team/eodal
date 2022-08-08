"""
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
"""
import cv2

from datetime import date
from eodal.operational.mapping import MapperConfigs, Sentinel2Mapper
from eodal.operational.mapping import plot_feature
from eodal.utils.sentinel2 import ProcessingLevels
from pathlib import Path

#%% user-inputs
# ---------------------- Spatial Resolution ----------------------------
spatial_resolution: int = 10 			# meters
resampling_method: int = cv2.INTER_NEAREST_EXACT

# ----------------------- Processing Level -----------------------------
processing_level: ProcessingLevels = ProcessingLevels.L2A 	# BOA

# ------------------------ Cloud Coverage ------------------------------
scene_cloud_cover_threshold: int = 50 	# percent

# ------------------------- Time Range ---------------------------------
date_start: date = date(2022,4,1)  		# year, month, day (incl.)
date_end: date = date(2022,5,1)   		# year, month, day (incl.)

# ---------------------- Area of Interest ------------------------------
aoi: Path = Path('../data/sample_polygons/lake_lucerne.gpkg')

#%% executable part
# Sentinel-2 mapper configuration
mapper_configs = MapperConfigs(
	spatial_resolution=spatial_resolution,
	resampling_method=resampling_method,
)

# get a new mapper instance
mapper = Sentinel2Mapper(
	date_start=date_start,
	date_end=date_end,
	processing_level=processing_level,
	cloud_cover_threshold=scene_cloud_cover_threshold,
	mapper_configs=mapper_configs,
	feature_collection=aoi
)

# retrieve metadata of scenes found (no reading)
mapper.get_scenes()
# read data into eodal's RasterCollection objects
s2_data = mapper.get_complete_timeseries()
features = mapper.get_feature_ids()

# loop features (in this case it's just a single one) and plot them
# TODO: Test this
for feature in features:
	fig_feature = plot_feature(
		feature_scenes=s2_data[feature],
		band_selection=['nir_1', 'red', 'green'],
		figsize=(15,7),
		max_scenes_in_row=3,
		sharex=True,
		sharey=True
	)

# further program logic ...
