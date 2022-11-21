Changelog
=========

All notable changes to package_name will be documented here.

The format is based on `Keep a Changelog`_, and this project adheres to `Semantic Versioning`_.

.. _Keep a Changelog: https://keepachangelog.com/en/1.0.0/
.. _Semantic Versioning: https://semver.org/spec/v2.0.0.html

Categories for changes are: Added, Changed, Deprecated, Removed, Fixed, Security.

Version `0.0.2 < https://github.com/EOA-team/eodal/releases/tag/v0.0.2>`__
--------------------------------------------------------------------------------

Release date: YYYY-MM-DD

- Added: RasterCollection objects are now iterable (iterate over bands in collection)
- Added: RasterCollection now have a "apply" method allowing to pass custom functions to RasterCollection objects


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
