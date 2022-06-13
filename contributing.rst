Contributing
============

Contributions are welcome! If you can see a way to improve the development of E:earth_africa:dal :

- Do click the fork button
- Make your changes and make a pull request.

If you consider contributing as a **developer** please make sure to understand the follow the code style guidelines:

CODE STYLE
----------

Establishing some common code styling rules can help increasing the readability and maintability of the code and is vital for collaborative development.
We encourage the use of Black (https://black.readthedocs.io/en/stable/the_black_code_style/current_style.html) for code style formatting. Black_ is an uncompromising Python code formatter.
By using it, you cede control over minutiae of hand-formatting.
But in return, you no longer have to worry about formatting your code correctly, since black will handle it.
Blackened code looks the same for all authors, ensuring consistent code formatting within your project.

The format used by Black makes code review faster by producing the smaller diffs.

Black's output is always stable. For a given block of code, a fixed version of black will always produce the same output.
However, you should note that different versions of black will produce different outputs.

Besides these aspects, there are same `naming` rules to follow:

Variable Naming
---------------

Variable names shall be consice and verbose. Within the function bodies, there is no strict variable naming style, however,
we try to follow the PEP8 (https://realpython.com/python-pep8/) conventions whenever possible.

Therefore, for variable names (taken from PEP8):
Use a lowercase single letter, word, or words. Separate words with underscores to improve readability.

E.g.,

.. code:: python

    i = 0
    number = 1
    string_variable = 'This is a string'


Class Naming
------------

Following PEP8 (https://realpython.com/python-pep8/) conventions, class names should start with a captital lette.
Class names consisting of multiple words should not be separated by an underscore, but follow the *camel case* convention:

E.g.,

.. code:: python

    class Class(object):
        pass

    class MyClass(Class):
        pass


Function Headers
----------------

See below for an example how to style function headers. Please **always** use type declarations to indicate the datatypes required/returned.
Moreover, the in- and outputs of the function should be documented in the `reST` style.

.. code:: python

    def fun(
        a: int,
        b: Union[int, float],
        c: Optional[str]=''
    ) -> int:
    """
    function description goes here

    :param a:
        description of a
    :param b:
        description of b
    :param c:
        description of c
    :returns:
        description of return value(s)
    """
    pass # function code...

Comments
--------
Please make inline comments to explain the code or why you opted for certain implementations. Also mention code sources in case
you took some fixes from, e.g., stackoverflow or similar portals. Please provide the URL and the date you accessed the page.


Development features
====================

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

coming soon

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
