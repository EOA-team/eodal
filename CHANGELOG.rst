Changelog
=========

All notable changes to package_name will be documented here.

The format is based on `Keep a Changelog`_, and this project adheres to `Semantic Versioning`_.

.. _Keep a Changelog: https://keepachangelog.com/en/1.0.0/
.. _Semantic Versioning: https://semver.org/spec/v2.0.0.html

Categories for changes are: Added, Changed, Deprecated, Removed, Fixed, Security.

Version `0.2.0 < https://github.com/EOA-team/eodal/releases/tag/v0.2.0>`__
--------------------------------------------------------------------------------

Release date: 2023-04-03

- Added: the new EOdal Mapper class has been fully implemented and replaces the old mapper version. Scripts calling the Mapper must be updated.
- Removed: the previous EOdal Mapper class. The enitre eodal.operational sub-package has been deprecated.
- Removed: the sub-package called eodal.operational.cli has been deprecated. Some useful scripts have been ported to the `scripts` folder in the main directory of the EOdal git repository.
- Changed: The EOdal pystac client has been re-designed to provide a higher level of generalization. Still, future changes might apply.
- Fixed: SceneCollection.get_feature_timeseries() had several bugs. Thanks to @atoparseks the code has been cleaned up, made simpler and works now with custom functions for computing user-defined zonal statistical metrics.
- Fixed: Several small bugs in the core module with varying levels of severity.
- Fixed: The map algebra operators for Band and RasterCollection objects lacked support of right-handed sided expression (e.g., `2 + Band` instead of `Band +2`). This issue has been fixed by overwriting also the [r]ight-handed built-in operators such `radd` as the right-handed equivalent of `add`.
- Changed: The README has been updated and now also includes information about the data model in EOdal.

Version `0.1.1 < https://github.com/EOA-team/eodal/releases/tag/v0.1.1>`__
--------------------------------------------------------------------------------

Release date: 2022-12-13

- Fixed: Band.clip() now has a optional keyword "full_bounding_box_only" (default: False) allowing to mask pixels outside the feature geometry.
- Fixed: Calculation of bounding box in image coordinates was partly incorrect, we now use the same approach as rasterstats and rasterio do.
- Fixed: Sentinel.mask_clouds_and_shadows() default SCL classes were updated so that everything but SCL classes 4 and 5 are masked by default.
- Added: SceneCollection now also allows clipping to a feature geometry (SceneCollection.clip_scenes())

Version `0.1.0 < https://github.com/EOA-team/eodal/releases/tag/v0.1.0>`__
--------------------------------------------------------------------------------

Release date: 2022-12-08

- Added: RasterCollection objects are now iterable (iterate over bands in collection)
- Added: RasterCollection now have a "apply" method allowing to pass custom functions to RasterCollection objects
- Added: RasterCollection now supports numpy-array like slicing using band names or band aliases
- Added: Band and RasterCollection objects now support clipping to rectangular bounds (i.e., spatial sub-setting)
- Changed: Band.reduce() and RasterCollection.band_summaries() now support creating statistics per Polygon features
- Added: SceneCollections are collections of 0 to N Scenes (RasterCollection + timestamp) and allow to store multiple Scenes over time
- Fixed: Map algebra now also works on RasterCollection supporting multiple cases (i.e., RasterCollection with other RasterCollection, scaler, etc.)
- Added: SceneCollection objects can be saved as pickled objects and loaded from pickled binary objects to make SceneCollections persistent


Version `0.0.1 < https://github.com/EOA-team/eodal/releases/tag/v0.0.1>`__
--------------------------------------------------------------------------------

Release date: 2022-10-31.

- Added: Support for Microsoft Planetary Computer (using its STAC)
- Added: Guidelines for Contribution to E:earth_africa:dal
- Added: Sensor core class to work with Planet Scope Super Dove sensors including download capacities
- Added: Sensor core class to work with Sentinel-1 data (Ground Range Detected and Radiometrically Terrain Corrected)
- Added: Metadata and archive handling for Sentinel-1 products (GRD, SLC)
- Fixed: Various issues and bugs in the operational.mapper class (made more generic to allow easy integration of further sensors)
- Added: Fast visualization of time series data (imagery) as part of the mapping module in the operational sub-package
