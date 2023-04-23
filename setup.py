#!/usr/bin/env python

import glob
import os
import sys
from shutil import rmtree

from setuptools import Command, find_packages, setup
from setuptools.command.test import test as TestCommand


def read(fname):
    """
    Read the contents of a file.

    Parameters
    ----------
    fname : str
        Path to file.

    Returns
    -------
    str
        File contents.
    """
    with open(os.path.join(os.path.dirname(__file__), fname)) as f:
        return f.read()


install_requires = read("requirements.txt").splitlines()

# Dynamically determine extra dependencies
extras_require = {}
extra_req_files = glob.glob("requirements-*.txt")
for extra_req_file in extra_req_files:
    name = os.path.splitext(extra_req_file)[0].replace("requirements-", "", 1)
    extras_require[name] = read(extra_req_file).splitlines()

# If there are any extras, add a catch-all case that includes everything.
# This assumes that entries in extras_require are lists (not single strings),
# and that there are no duplicated packages across the extras.
if extras_require:
    extras_require["all"] = sorted({x for v in extras_require.values() for x in v})


# Import meta data from __meta__.py
#
# We use exec for this because __meta__.py runs its __init__.py first,
# __init__.py may assume the requirements are already present, but this code
# is being run during the `python setup.py install` step, before requirements
# are installed.
# https://packaging.python.org/guides/single-sourcing-package-version/
meta = {}
exec(read("eodal/__meta__.py"), meta)


# Import the README and use it as the long-description.
# If your readme path is different, add it here.
possible_readme_names = ["README.rst", "README.md", "README.txt", "README"]

# Handle turning a README file into long_description
long_description = meta["description"]
readme_fname = ""
for fname in possible_readme_names:
    try:
        long_description = read(fname)
    except IOError:
        # doesn't exist
        continue
    else:
        # exists
        readme_fname = fname
        break

# Infer the content type of the README file from its extension.
# If the contents of your README do not match its extension, manually assign
# long_description_content_type to the appropriate value.
readme_ext = os.path.splitext(readme_fname)[1]
if readme_ext.lower() == ".rst":
    long_description_content_type = "text/x-rst"
elif readme_ext.lower() == ".md":
    long_description_content_type = "text/markdown"
else:
    long_description_content_type = "text/plain"


class PyTest(TestCommand):
    """Support setup.py test."""

    def finalize_options(self):
        TestCommand.finalize_options(self)
        self.test_args = []
        self.test_suite = True

    def run_tests(self):
        import pytest

        pytest.main(self.test_args)


class UploadCommand(Command):
    """Support setup.py upload."""

    description = "Build and publish the package."
    user_options = []

    @staticmethod
    def status(s):
        """Print things in bold."""
        print("\033[1m{0}\033[0m".format(s))

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        try:
            self.status("Removing previous builds...")
            here = os.path.abspath(os.path.dirname(__file__))
            rmtree(os.path.join(here, "dist"))
        except OSError:
            pass

        self.status("Building Source and Wheel (universal) distribution...")
        os.system("{0} setup.py sdist bdist_wheel --universal".format(sys.executable))

        self.status("Uploading the package to PyPI via Twine...")
        os.system("twine upload dist/*")

        self.status("Pushing git tags...")
        os.system("git tag v{0}".format(meta["version"]))
        os.system("git push --tags")

        sys.exit()

setup(
    name='eodal',
    # setup_requires=['setuptools_scm'],
    # use_scm_version={'version_scheme': 'python-simplified-semver'},
    version='0.2.0',
    description='The Earth Observation Data Analysis Library EOdal',
    long_description=long_description,
    # long_description='*A truely open-source package for unified analysis of Earth Observation (EO) data\nCloud-native by design providing access to Petabytes of EO data',
    long_description_content_type='text/markdown',
    author='Group of Crop Science, ETH Zurich & EOA-Team Agroscope Reckenholz, Zurich, Switzerland',
    author_email='',
    install_requires=install_requires,
    url='https://github.com/EOA-team/eodal',
    python_requires=">=3.8",
    packages=find_packages(exclude=["tests", "*.tests", "*.tests.*", "tests.*"]),
    include_package_data=True,
    license='GNU General Public License v3',
    package_data={'': []},
    classifiers = [
     "Natural Language :: English",
     "Programming Language :: Python :: 3",
     "Operating System :: OS Independent",
     "Programming Language :: Python :: 3.8",
     "Programming Language :: Python :: 3.9",
     "Programming Language :: Python :: 3.10"
    ],
    # Could also include keywords, download_url, project_urls, etc.
    # Custom commands
    cmdclass={
        "test": PyTest,
        "upload": UploadCommand,
    },
)
