
import cv2

from datetime import date
from eodal.operational.mapping import MapperConfigs, Sentinel2Mapper
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
date_end: date = date(2022,4,30)   		# year, month, day (incl.)

# ---------------------- Area of Interest ------------------------------
aoi: Path = Path('../data/sample_polygons/western_switzerland.gpkg')

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

# further program logic ...
