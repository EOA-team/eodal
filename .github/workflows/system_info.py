"""
Print out some handy system info.
"""

import os
import platform
import sys

print("Build system information")
print()

print("sys.version\t\t", sys.version.split("\n"))
print("os.name\t\t\t", os.name)
print("sys.platform\t\t", sys.platform)
print("platform.system()\t", platform.system())
print("platform.machine()\t", platform.machine())
print("platform.platform()\t", platform.platform())
print("platform.version()\t", platform.version())
print("platform.uname()\t", platform.uname())
if sys.platform == "darwin":
    print("platform.mac_ver()\t", platform.mac_ver())
