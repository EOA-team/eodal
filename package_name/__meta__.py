# `name` is the name of the package as used for `pip install package`
name = "package-name"
# `path` is the name of the package for `import package`
path = name.lower().replace("-", "_").replace(" ", "_")
# Your version number should follow https://python.org/dev/peps/pep-0440 and
# https://semver.org
version = "0.1.dev0"
author = "Author Name"
author_email = ""
description = ""  # One-liner
url = ""  # your project homepage
license = "MIT"  # See https://choosealicense.com
