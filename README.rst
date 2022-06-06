|GHA tests| |Codecov report| |pre-commit| |black|

Python Template Repository
==========================

This repository gives a fully-featured template or skeleton for new Python repositories.


Quick start
-----------

.. highlight:: bash

When creating a new repository from this template, these are the steps to follow:

#. *Don't click the fork button.*
   The fork button is for making a new template based in this one, not for using the template to make a new repository.

#.
    #.  **New GitHub repository**.

        You can create a new repository on GitHub from this template by clicking the `Use this template <https://github.com/scottclowe/python-template-repo/generate>`_ button.

        *Need to support Python 2.7?*
        Make sure to check the "Include all branches" option while creating the new repository.

        Then clone your new repository to your local system [pseudocode]::

          git clone git@github.com:your-org/your-repo.git
          cd your-repo

        *If you need to support Python 2.7*, now move the reference for your default branch (master/main) to point to the python2.7 branch head::

          git reset --hard origin/python2.7
          git push -f

        You can now delete the python2.7 branch from your remote.

    #.  **New repository not on GitHub**.

        Alternatively, if your new repository is not going to be on GitHub, you can download `this repo as a zip <https://github.com/scottclowe/python-template-repo/archive/master.zip>`_ and work from there.

        *Need to support Python 2.7?*
        Download the `python2.7 branch as a zip <https://github.com/scottclowe/python-template-repo/archive/refs/heads/python2.7.zip>`_ instead.

        Either way, you should note that this zip does not include the .gitignore and .gitattributes files (because GitHub automatically omits them, which is usually helpful but is not for our purposes).
        Thus you will also need to download the `.gitignore <https://raw.githubusercontent.com/scottclowe/python-template-repo/master/.gitignore>`__ and `.gitattributes <https://raw.githubusercontent.com/scottclowe/python-template-repo/master/.gitattributes>`__ files.

        The following shell commands can be used for this purpose on \*nix systems::

          git init your_repo_name
          cd your_repo_name
          wget https://github.com/scottclowe/python-template-repo/archive/master.zip
          unzip master.zip
          mv -n python-template-repo-master/* python-template-repo-master/.[!.]* .
          rm -r python-template-repo-master/
          rm master.zip
          wget https://raw.githubusercontent.com/scottclowe/python-template-repo/master/.gitignore
          wget https://raw.githubusercontent.com/scottclowe/python-template-repo/master/.gitattributes
          git add .
          git commit -m "Initial commit"
          git rm LICENSE

        Note that we are doing the move with ``mv -n``, which will prevent the template repository from clobbering your own files (in case you already made a README.rst file, for instance).

        You'll need to instruct your new local repository to synchronise with the remote ``your_repo_url``::

          git remote set-url origin your_repo_url
          git push -u origin master

#.  Remove the dummy files ``package_name/module.py`` and ``package_name/tests/test_module.py``::

        rm package_name/module.py
        rm package_name/tests/test_module.py

    If you prefer, you can keep them around as samples, but should note that they require numpy.

#.  Depending on your needs, some of the files may be superfluous to you.
    You can remove any superfluous files, as follows.

    - *No GitHub Actions!*
      Delete the .github directory::

        rm -r .github/

    - *No unit testing!*
      Run the following commands to delete unit testing files::

        rm -rf package_name/tests/
        rm -f .github/workflows/test*.yaml
        rm -f .codecov.yml
        rm -f .coveragerc
        rm -f requirements-test.txt

#.  Delete the LICENSE file and replace it with a LICENSE file of your own choosing.
    If the code is intended to be freely available for anyone to use, use an `open source license <https://choosealicense.com/>`_, such as `MIT License <https://choosealicense.com/licenses/mit/>`__ or `GPLv3 <https://choosealicense.com/licenses/gpl-3.0/>`__.
    If you don't want your code to be used by anyone else, add a LICENSE file which just says:

    .. code-block:: none

        Copyright (c) YEAR, YOUR NAME

        All right reserved.

    Note that if you don't include a LICENSE file, you will still have copyright over your own code (this copyright is automatically granted), and your code will be private source (technically nobody else will be permitted to use it, even if you make your code publicly available).

#.  Edit the file ``package_name/__meta__.py`` to contain your author and repo details.

    name
        The name as it will/would be on PyPI (users will do ``pip install new_name_here``).
        It is `recommended <PEP-8_>`__ to use a name all lowercase, runtogetherwords but if separators are needed hyphens are preferred over underscores.

    path
        The path to the package. What you will rename the directory ``package_name``.
        `Should be <PEP-8_>`__ the same as ``name``, but now hyphens are disallowed and should be swapped for underscores.
        By default, this is automatically inferred from ``name``.

    license
        Should be the name of the license you just picked and put in the LICENSE file (e.g. ``MIT`` or ``GPLv3``).

    Other fields to enter should be self-explanatory.

#. Rename the directory ``package_name`` to be the ``path`` variable you just added to ``__meta__.py``.::

      PACKAGE_NAME=your_actual_package_name
      mv package_name "$PACKAGE_NAME"

#.  Change references to ``package_name`` to your path variable:

    This can be done with the sed command::

        PACKAGE_NAME=your_actual_package_name
        sed -i "s/package_name/$PACKAGE_NAME/" setup.py \
            docs/conf.py \
            docs/index.rst \
            CHANGELOG.rst \
            .github/workflows/test*.yaml

    Which will make changes in the following places.

    .. highlight:: python

    - In ``setup.py``, `L69 <https://github.com/scottclowe/python-template-repo/blob/master/setup.py#L69>`__::

        exec(read('package_name/__meta__.py'), meta)

    - In ``docs/conf.py``, `L23 <https://github.com/scottclowe/python-template-repo/blob/master/docs/conf.py#L23>`__::

        from package_name import __meta__ as meta  # noqa: E402

    - In ``docs/index.rst``, `L1 <https://github.com/scottclowe/python-template-repo/blob/master/docs/index.rst#L1>`__::

        package_name documentation

    - In ``.github/workflows/test.yaml``, `L78 <https://github.com/scottclowe/python-template-repo/blob/master/.github/workflows/test.yaml#L78>`__, and ``.github/workflows/test-release-candidate.yaml``, `L90 <https://github.com/scottclowe/python-template-repo/blob/master/.github/workflows/test-release-candidate.yaml#L90>`__::

        python -m pytest --cov=package_name --cov-report term --cov-report xml --cov-config .coveragerc --junitxml=testresults.xml

    .. highlight:: bash

#.  Swap out the contents of ``requirements.txt`` for your project's current requirements.
    If you don't have any requirements yet, delete the contents of ``requirements.txt``.

#.  Swap out the contents of ``README.rst`` with an inital description of your project.
    If you are keeping all the badges, make sure to change the URLs from ``scottclowe/python-template-repo`` to ``your_username/your_repo``.
    If you prefer, you can use markdown instead of rST.

#.  Commit and push your changes::

      git commit -am "Initialise project from template repository"
      git push

When it comes time to make your first release, make sure you update the placeholder entry in CHANGELOG.rst to contain the correct details.
You'll need to change ``YYYY-MM-DD`` to the actual release date, and change the URL to point to your release.


Features
--------

.gitignore
~~~~~~~~~~

A `.gitignore`_ file is used specify untracked files which Git should ignore and not try to commit.

Our template's .gitignore file is based on the `GitHub defaults <default-gitignores_>`_.
We use the default `Python .gitignore`_, `Windows .gitignore`_, `Linux .gitignore`_, and `Mac OSX .gitignore`_ concatenated together.
(Released under `CC0-1.0 <https://github.com/github/gitignore/blob/master/LICENSE>`__.)

The Python .gitignore specifications prevent compiled files, packaging and sphinx artifacts, test outputs, etc, from being accidentally committed.
Even though you may develop on one OS, you might find a helpful contributor working on a different OS suddenly issues you a new PR, hence we include the gitignore for all OSes.
This makes both their life and yours easier by ignoring their temporary files before they even start working on the project.

.. _.gitignore: https://git-scm.com/docs/gitignore
.. _default-gitignores: https://github.com/github/gitignore
.. _Python .gitignore: https://github.com/github/gitignore/blob/master/Python.gitignore
.. _Windows .gitignore: https://github.com/github/gitignore/blob/master/Global/Windows.gitignore
.. _Linux .gitignore: https://github.com/github/gitignore/blob/master/Global/Linux.gitignore
.. _Mac OSX .gitignore: https://github.com/github/gitignore/blob/master/Global/macOS.gitignore


.gitattributes
~~~~~~~~~~~~~~

The most important reason to include a `.gitattributes`_ file is to ensure that line endings are normalised, no matter which OS the developer is using.
This is largely achieved by the line::

    * text=auto

which `ensures <gitattributes-text_>`__ that all files Git decides contain text have their line endings normalized to LF on checkin.
This can cause problems if Git misdiagnoses a file as text when it is not, so we overwrite automatic detection based on file endings for some several common file endings.

Aside from this, we also gitattributes to tell git what kind of diff to generate.

Our template .gitattributes file is based on the `defaults from Alexander Karatarakis <alexkaratarakis/gitattributes_>`__.
We use the `Common .gitattributes`_ and `Python .gitattributes`_ concatenated together.
(Released under `MIT License <https://github.com/alexkaratarakis/gitattributes/blob/master/LICENSE.md>`__.)

.. _.gitattributes: https://git-scm.com/docs/gitattributes
.. _gitattributes-text: https://git-scm.com/docs/gitattributes#_text
.. _alexkaratarakis/gitattributes: https://github.com/alexkaratarakis/gitattributes
.. _Common .gitattributes: https://github.com/alexkaratarakis/gitattributes/blob/master/Common.gitattributes
.. _Python .gitattributes: https://github.com/alexkaratarakis/gitattributes/blob/master/Python.gitattributes


Black
~~~~~

Black_ is an uncompromising Python code formatter.
By using it, you cede control over minutiae of hand-formatting.
But in return, you no longer have to worry about formatting your code correctly, since black will handle it.
Blackened code looks the same for all authors, ensuring consistent code formatting within your project.

The format used by Black makes code review faster by producing the smaller diffs.

Black's output is always stable.
For a given block of code, a fixed version of black will always produce the same output.
However, you should note that different versions of black will produce different outputs.
If you want to upgrade to a newer version of black, you must change the version everywhere it is specified:

- requirements-dev.txt, `L1 <https://github.com/scottclowe/python-template-repo/blob/master/requirements-dev.txt#L1>`__
- .pre-commit-config.yaml, `L14 <https://github.com/scottclowe/python-template-repo/blob/master/.pre-commit-config.yaml#L14>`__,
  `L28 <https://github.com/scottclowe/python-template-repo/blob/master/.pre-commit-config.yaml#L28>`__, and
  `L47 <https://github.com/scottclowe/python-template-repo/blob/master/.pre-commit-config.yaml#L47>`__

.. _black: https://github.com/psf/black


pre-commit
~~~~~~~~~~

The template repository comes with a pre-commit_ stack.
This is a set of git hooks which are executed every time you make a commit.
The hooks catch errors as they occur, and will automatically fix some of these errors.

To set up the pre-commit hooks, run the following code from within the repo directory::

    pip install -r requirements-dev.txt
    pre-commit install

Whenever you try to commit code which is flagged by the pre-commit hooks, the commit will not go through.
Some of the pre-commit hooks (such as black_, isort_) will automatically modify your code to fix the issues.
When this happens, you'll have to stage the changes made by the commit hooks and then try your commit again.
Other pre-commit hooks will not modify your code and will just tell you about issues which you'll then have to manually fix.

You can also manually run the pre-commit stack on all the files at any time::

    pre-commit run --all-files

To force a commit to go through without passing the pre-commit hooks use the ``--no-verify`` flag::

    git commit --no-verify

The pre-commit stack which comes with the template is highly opinionated, and includes the following operations:

- Code is reformatted to use the black_ style.
  Any code inside docstrings will be formatted to black using blackendocs_.
  All code cells in Jupyter notebooks are also formatted to black using black_nbconvert_.

- All Jupyter notebooks are cleared using nbstripout_.

- Imports are automatically sorted using isort_.

- flake8_ is run to check for conformity to the python style guide PEP-8_, along with several other formatting issues.

- setup-cfg-fmt_ is used to format any setup.cfg files.

- Several `hooks from pre-commit <pre-commit-hooks_>`_ are used to screen for non-language specific git issues, such as incomplete git merges, overly large files being commited to the repo, bugged JSON and YAML files.
  JSON files are also prettified automatically to have standardised indentation.
  Entries in requirements.txt files are automatically sorted alphabetically.

- Several `hooks from pre-commit specific to python <pre-commit-py-hooks_>`_ are used to screen for rST formatting issues, and ensure noqa flags always specify an error code to ignore.

Once it is set up, the pre-commit stack will run locally on every commit.
The pre-commit stack will also run on github with one of the action workflows, which ensures PRs are checked without having to rely on contributors to enable the pre-commit locally.

.. _black_nbconvert: https://github.com/dfm/black_nbconvert
.. _blackendocs: https://github.com/asottile/blacken-docs
.. _flake8: https://gitlab.com/pycqa/flake8
.. _isort: https://github.com/timothycrosley/isort
.. _nbstripout: https://github.com/kynan/nbstripout
.. _PEP-8: https://www.python.org/dev/peps/pep-0008/
.. _pre-commit: https://pre-commit.com/
.. _pre-commit-hooks: https://github.com/pre-commit/pre-commit-hooks
.. _pre-commit-py-hooks: https://github.com/pre-commit/pygrep-hooks
.. _setup-cfg-fmt: https://github.com/asottile/setup-cfg-fmt


Automated documentation
~~~~~~~~~~~~~~~~~~~~~~~

The script ``docs/conf.py`` is based on the Sphinx_ default configuration.
It is set up to work well out of the box, with several features added in.

GitHub Pages
^^^^^^^^^^^^

If your repository is publicly available, the docs workflow will automatically deploy your documentation to `GitHub Pages`_.
To enable the documentation, go to the ``Settings > Pages`` pane for your repository and set Source to be the ``gh-pages`` branch (root directory).
Your automatically compiled documentation will then be publicly available at https://USER.github.io/PACKAGE/.

Since GitHub pages are always publicly available, the workflow will check whether your repository is public or private, and will not deploy the documentation to gh-pages if your repository is private.

The gh-pages documentation is refreshed every time there is a push to your default branch.

Note that only one copy of the documentation is served (the latest version).
For more mature projects, you may wish to host the documentation readthedocs_ instead, which supports hosting documentation for multiple package versions simultaneously.

.. _GitHub Pages: https://pages.github.com/
.. _readthedocs: https://readthedocs.org/

Building locally
^^^^^^^^^^^^^^^^

You can build the web documentation locally with::

   make -C docs html

And view the documentation like so::

   sensible-browser docs/_build/html/index.html

Or you can build pdf documentation::

   make -C docs latexpdf

On Windows, this becomes::

    cd docs
    make html
    make latexpdf
    cd ..

Other documentation features
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

- Your README.rst will become part of the generated documentation (via a link file ``docs/source/readme.rst``).
  Note that the first line of README.rst is not included in the documentation, since this is expected to contain badges which you want to render on GitHub, but not include in your documentation pages.

- If you prefer, you can use a README.md file written in GitHub-Flavored Markdown instead of README.rst.
  This will automatically be handled and incorporate into the generated documentation (via a generated file ``docs/source/readme.rst``).
  As with a README.rst file, the first line of README.md is not included in the documentation, since this is expected to contain badges which you want to render on GitHub, but not include in your documentation pages.

- Your docstrings to your modules, functions, classes and methods will be used to build a set of API documentation using autodoc_.
  Our ``docs/conf.py`` is also set up to automatically call autodoc whenever it is run, and the output files which it generates are on the gitignore list.
  This means you will automatically generate a fresh API description which exactly matches your current docstrings every time you generate the documentation.

- Docstrings can be formatted in plain reST_, or using the `numpy format`_ (recommended), or `Google format`_.
  Support for numpy and Google formats is through the napoleon_ extension (which we have enabled by default).

- You can reference functions in the python core and common packages and they will automatically be hyperlinked to the appropriate documentation in your own documentation.
  This is done using intersphinx_ mappings, which you can see (and can add to) at the bottom of the ``docs/conf.py`` file.

- The documentation theme is sphinx-book-theme_.
  Alternative themes can be found at sphinx-themes.org_, sphinxthemes.com_, and writethedocs_.

.. _autodoc: http://www.sphinx-doc.org/en/master/usage/extensions/autodoc.html
.. _Google format: https://sphinxcontrib-napoleon.readthedocs.io/en/latest/example_google.html#example-google
.. _intersphinx: http://www.sphinx-doc.org/en/master/usage/extensions/intersphinx.html
.. _napoleon: https://www.sphinx-doc.org/en/master/usage/extensions/napoleon.html
.. _numpy format: https://sphinxcontrib-napoleon.readthedocs.io/en/latest/example_numpy.html#example-numpy-style-python-docstrings
.. _Sphinx: https://www.sphinx-doc.org/
.. _sphinx-book-theme: https://sphinx-book-theme.readthedocs.io/
.. _sphinx-themes.org: https://sphinx-themes.org
.. _sphinxthemes.com: https://sphinxthemes.com/
.. _reST: http://docutils.sourceforge.net/rst.html
.. _writethedocs: https://www.writethedocs.org/guide/tools/sphinx-themes/


Consolidated metadata
~~~~~~~~~~~~~~~~~~~~~

Package metadata is consolidated into one place, the file ``package_name/__meta__.py``.
You only have to write the metadata once in this centralised location, and everything else (packaging, documentation, etc) picks it up from there.
This is similar to `single-sourcing the package version`_, but for all metadata.

This information is available to end-users with ``import package_name; print(package_name.__meta__)``.
The version information is also accessible at ``package_name.__version__``, as per PEP-396_.

.. _PEP-396: https://www.python.org/dev/peps/pep-0396/#specification
.. _single-sourcing the package version: https://packaging.python.org/guides/single-sourcing-package-version/


setup.py
~~~~~~~~

The ``setup.py`` script is used to build and install your package.

Your package can be installed from source with::

    pip install .

or alternatively with::

    python setup.py install

But do remember that as a developer, you should install your package in editable mode, using either::

    pip install --editable .

or::

    python setup.py develop

which will mean changes to the source will affect your installed package immediately without you having to reinstall it.

By default, when the package is installed only the main requirements, listed in ``requirements.txt`` will be installed with it.
Requirements listed in ``requirements-dev.txt``, ``requirements-docs.txt``, and ``requirements-test.txt`` are optional extras.
The ``setup.py`` script is configured to include these as extras named ``dev``, ``docs``, and ``test``.
They can be installed along with::

    pip install .[dev]

etc.
Any additional files named ``requirements-EXTRANAME.txt`` will also be collected automatically and made available with the corresponding name ``EXTRANAME``.
Another extra named ``all`` captures all of these optional dependencies.

Your README file is automatically included in the metadata when you use setup.py build wheels for PyPI.
The rest of the metadata comes from ``package_name/__meta__.py``.

Our template setup.py file is based on the `example from setuptools documentation <setuptools-setup.py_>`_, and the comprehensive example from `Kenneth Reitz <kennethreitz/setup.py_>`_ (released under `MIT License <https://github.com/kennethreitz/setup.py/blob/master/LICENSE>`__), with further features added.

.. _kennethreitz/setup.py: https://github.com/kennethreitz/setup.py
.. _setuptools-setup.py: https://setuptools.readthedocs.io/en/latest/setuptools.html#basic-use


Unit tests
~~~~~~~~~~

The file ``package_name/tests/base_test.py`` provides a class for unit testing which provides easy access to all the numpy testing in one place (so you don't need to import a stack of testing functions in every test file, just import the ``BaseTestClass`` instead).

If you aren't using doing numeric tests, you can delete this from the ``package_name/tests/base_test.py`` file.


GitHub Actions Workflows
~~~~~~~~~~~~~~~~~~~~~~~~

GitHub features the ability to run various workflows whenever code is pushed to the repo or a pull request is opened.
This is one service of several services that can be used to continually run the unit tests and ensure changes can be integrated together without issue.
It is also useful to ensure that style guides are adhered to

Five workflows are included:

docs
    The docs workflow ensures the documentation builds correctly, and presents any errors and warnings nicely as annotations.
    If your repository is public, publicly available html documentation is automatically deployed to the gh-pages branch and https://USER.github.io/PACKAGE/.

pre-commit
    Runs the pre-commit stack.
    Ensures all contributions are compliant, even if a contributor has not set up pre-commit on their local machine.

lint
    Checks the code uses the black_ style and tests for flake8_ errors.
    If you are using the pre-commit hooks, the lint workflow is superfluous and can be deleted.

test
    Runs the unit tests, and pushes coverage reports to Codecov_.
    You'll need to sign up at Codecov_ with your GitHub account in order for this integration to work.

release candidate tests
    The release candidate tests workflow runs the unit tests on more Python versions and operating systems than the regular test workflow.
    This runs on all tags, plus pushes and PRs to branches named like "v1.2.x", etc.
    Wheels are built for all the tested systems, and stored as artifacts for your convenience when shipping a new distribution.

If you enable the ``publish`` job on the release candidate tests workflow, you can also push built release candidates to the `Test PyPI <testpypi_>`_ server.
For this to work, you'll also need to add your Test `PyPI API token <pypi-api-token_>`_ to your `GitHub secrets <github-secrets_>`_.
Checkout the `pypa/gh-action-pypi-publish <pypi-publish_>`_ GitHub action, and `PyPI's guide on distributing from CI <ci-packaging_>`_ for more information on this.
With minimal tweaks, this job can be changed to push to PyPI for real, but be careful with this since releases on PyPI can not easily be yanked.

.. _Codecov: https://codecov.io/
.. _ci-packaging: https://packaging.python.org/guides/publishing-package-distribution-releases-using-github-actions-ci-cd-workflows/
.. _github-secrets: https://docs.github.com/en/actions/reference/encrypted-secrets
.. _pypi-api-token: https://pypi.org/help/#apitoken
.. _pypi-publish: https://github.com/pypa/gh-action-pypi-publish
.. _testpypi: https://test.pypi.org/


Other CI/CD options
~~~~~~~~~~~~~~~~~~~

Alternative CI/CD services are also available for running tests.

- `Travis CI <https://travis-ci.org/>`_ offers a free trial service.

- `Circle CI <https://circleci.com>`_ is another option with a limited `free option <https://circleci.com/pricing/#build-linux>`_.

- `Appveyor <https://www.appveyor.com>`_ useful for testing on Windows.
  This offers an alternative to GitHub Actions if you need to `build Windows wheel files to submit to PyPI <https://github.com/ogrisel/python-appveyor-demo>`_.

- `Jenkins <https://jenkins.io/>`_ is useful if you want to run your CI test suite locally or on your own private server instead of in the cloud.


Contributing
------------

Contributions are welcome! If you can see a way to improve this template:

- Do click the fork button
- Make your changes and make a pull request.

Or to report a bug or request something new, make an issue.


.. highlight:: python


.. |GHA tests| image:: https://github.com/scottclowe/python-template-repo/workflows/tests/badge.svg
   :target: https://github.com/scottclowe/python-template-repo/actions?query=workflow%3Atests
   :alt: GHA Status
.. |Codecov report| image:: https://codecov.io/github/scottclowe/python-template-repo/coverage.svg?branch=master
   :target: https://codecov.io/github/scottclowe/python-template-repo?branch=master
   :alt: Coverage
.. |pre-commit| image:: https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white
   :target: https://github.com/pre-commit/pre-commit
   :alt: pre-commit
.. |black| image:: https://img.shields.io/badge/code%20style-black-000000.svg
   :target: https://github.com/psf/black
   :alt: black
