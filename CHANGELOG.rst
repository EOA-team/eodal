Changelog
=========

All notable changes to package_name will be documented here.

The format is based on `Keep a Changelog`_, and this project adheres to `Semantic Versioning`_.

.. _Keep a Changelog: https://keepachangelog.com/en/1.0.0/
.. _Semantic Versioning: https://semver.org/spec/v2.0.0.html

Categories for changes are: Added, Changed, Deprecated, Removed, Fixed, Security.

Version `0.1.0 < https://github.com/EOA-team/eodal/releases/tag/v0.1.0>`__
--------------------------------------------------------------------------------

Release date: YYYY-MM-DD

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
