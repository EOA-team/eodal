# `name` is the name of the package as used for `pip install package`
name = "eodal"
# `path` is the name of the package for `import package`
path = name.lower().replace("-", "_").replace(" ", "_")
# Your version number should follow https://python.org/dev/peps/pep-0440 and
# https://semver.org
# version = "0.1.dev0"
author = (
    "Crop Science, Institute of Agricultural Sciences, D-USYS, ETH Zurich, Zurich, Switzerland;\n"
    "Earth Observation of Agroecosystems Team, Division Agroecology and Environment, Agroscope, Zurich, Switzerland"
)
author_email = ""
description = "Earth Observation Data Analysis Library"  # One-liner
url = "https://github.com/EOA-team/eodal"  # your project home-page
license = "GNU General Public License version 3"  # See https://choosealicense.com
version = "0.2.0"
