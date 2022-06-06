# -*- coding: utf-8 -*-
#
# Configuration file for the Sphinx documentation builder.
#
# This file does only contain a selection of the most common options. For a
# full list see the documentation:
# http://www.sphinx-doc.org/en/master/config

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
import datetime
import os
import sys
import tempfile
from inspect import getsourcefile

DOCS_DIRECTORY = os.path.dirname(os.path.abspath(getsourcefile(lambda: 0)))
REPO_DIRECTORY = os.path.dirname(DOCS_DIRECTORY)

sys.path.insert(0, DOCS_DIRECTORY)
sys.path.insert(0, REPO_DIRECTORY)

from package_name import __meta__ as meta  # noqa: E402 isort:skip


# -- Project information -----------------------------------------------------

now = datetime.datetime.now()

project = meta.name
project_path = meta.path
author = meta.author
copyright = "{}, {}".format(now.year, author)


# The full version, including alpha/beta/rc tags
release = meta.version
# The short X.Y version
version = ".".join(release.split(".")[0:2])


# -- Automatically generate API documentation --------------------------------


def run_apidoc(_):
    """
    Call apidoc, with customised set up.
    """
    ignore_paths = [
        os.path.join("..", project_path, "tests"),
    ]

    argv = [
        "--force",  # Overwrite output files
        "--follow-links",  # Follow symbolic links
        "--separate",  # Put each module file in its own page
        "--module-first",  # Put module documentation before submodule
        "-o",
        "source/packages",  # Output path
        os.path.join("..", project_path),
    ] + ignore_paths

    try:
        # Sphinx 1.7+
        from sphinx.ext import apidoc

        apidoc.main(argv)
    except ImportError:
        # Sphinx 1.6 (and earlier)
        from sphinx import apidoc

        argv.insert(0, apidoc.__file__)
        apidoc.main(argv)


def retitle_modules(_):
    """
    Overwrite the title of the modules.rst file.
    """
    pth = "source/packages/modules.rst"
    lines = open(pth).read().splitlines()
    # Overwrite the junk in the first two lines with a better title
    lines[0] = "API Reference"
    lines[1] = "============="
    open(pth, "w").write("\n".join(lines))


def auto_convert_readme(_):
    """
    Handle README.rst or README.md as available.

    If it exists, makes a symbolic link to README.rst at docs/source/readme.rst.
    Otherwise, and if it exists, converts README.md to to rST format, the
    output of which is docs/source/readme.rst.
    """
    readme_path_md = os.path.join(REPO_DIRECTORY, "README.md")
    readme_path_rst = os.path.splitext(readme_path_md)[0] + ".rst"
    readme_path_output = os.path.join(DOCS_DIRECTORY, "source", "readme.rst")
    # Ensure output directory exists
    output_dir = os.path.dirname(readme_path_output)
    os.makedirs(output_dir, exist_ok=True)

    if os.path.isfile(readme_path_rst):
        # Make docs/source/readme.rst be a symbolic link to README.rst
        #
        # We can't overwrite an existing file when calling os.symlink, so
        # we write to a temporary file and copy that over instead.
        tmp_path = tempfile.mktemp(dir=output_dir)
        try:
            os.symlink(readme_path_rst, tmp_path)
            os.replace(tmp_path, readme_path_output)
        finally:
            if os.path.islink(tmp_path):
                os.remove(tmp_path)

    elif os.path.isfile(readme_path_md):
        # Otherwise, if README.md exists convert it to markdown using pandoc
        import pypandoc

        # Download pandoc if necessary. If pandoc is already installed and on
        # the PATH, the installed version will be used. Otherwise, we will
        # download a copy of pandoc into docs/bin/ and add that to our PATH.
        pandoc_dir = os.path.join(DOCS_DIRECTORY, "bin")
        os.environ["PATH"] += os.pathsep + pandoc_dir
        pypandoc.ensure_pandoc_installed(
            quiet=True,
            targetfolder=pandoc_dir,
            delete_installer=True,
        )
        # Call pandoc using the pypandoc wrapper
        tmp_path = tempfile.mktemp(dir=output_dir)
        try:
            pypandoc.convert_file(
                readme_path_md,  # Source file
                "rst",  # to rST
                format="gfm",  # from GitHub-Flavored Markdown
                outputfile=tmp_path,  # Output file
            )
            os.replace(tmp_path, readme_path_output)
        finally:
            if os.path.islink(tmp_path):
                os.remove(tmp_path)


def setup(app):
    """
    Set up our apidoc commands to run whenever sphinx is built.
    """
    app.connect("builder-inited", auto_convert_readme)
    app.connect("builder-inited", run_apidoc)
    app.connect("builder-inited", retitle_modules)


# -- General configuration ---------------------------------------------------

# If your documentation needs a minimal Sphinx version, state it here.
#
# needs_sphinx = "1.0"

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named "sphinx.ext.*") or your custom
# ones.
extensions = [
    "myst_parser",  # Support markdown
    "sphinx.ext.autodoc",
    "sphinx.ext.intersphinx",
    "sphinx.ext.todo",
    "sphinx.ext.coverage",
    "sphinx.ext.mathjax",
    "sphinx.ext.ifconfig",
    "sphinx.ext.viewcode",
    "sphinx.ext.napoleon",
]

# Some extension features only available on later Python versions
if sys.version_info >= (3, 6):
    # Enables search as you type with Elasticsearch on readthedocs.com
    # but only available on Python 3.6 and above.
    extensions.append("sphinx_search.extension")

# Napoleon settings
napoleon_google_docstring = True
napoleon_numpy_docstring = True
napoleon_include_init_with_doc = True
napoleon_include_private_with_doc = False
napoleon_include_special_with_doc = False
napoleon_use_admonition_for_examples = False
napoleon_use_admonition_for_notes = False
napoleon_use_admonition_for_references = False
napoleon_use_ivar = False
napoleon_use_rtype = True
napoleon_use_param = True
napoleon_type_aliases = {
    "array-like": ":term:`array-like <array_like>`",
    "array_like": ":term:`array_like`",
}

# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

# The suffix(es) of source filenames.
# You can specify multiple suffix as a list of string:
#
source_suffix = [".rst", ".md"]

# The master toctree document.
master_doc = "index"

# The language for content autogenerated by Sphinx. Refer to documentation
# for a list of supported languages.
#
# This is also used if you do content translation via gettext catalogs.
# Usually you set "language" from the command line for these cases.
language = None

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = None


# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = "sphinx_book_theme"

# Theme options are theme-specific and customize the look and feel of a theme
# further.  For a list of options available for each theme, see the
# documentation.
#
# html_theme_options = {}

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ["_static"]

# Custom sidebar templates, must be a dictionary that maps document names
# to template names.
#
# The default sidebars (for documents that don't match any pattern) are
# defined by theme itself.  Builtin themes are using these templates by
# default: ``["localtoc.html", "relations.html", "sourcelink.html",
# "searchbox.html"]``.
#
# html_sidebars = {}


# -- Options for HTMLHelp output ---------------------------------------------

# Output file base name for HTML help builder.
htmlhelp_basename = project + "doc"


# -- Options for LaTeX output ------------------------------------------------

latex_elements = {
    # The paper size ("letterpaper" or "a4paper").
    # "papersize": "letterpaper",
    #
    # The font size ("10pt", "11pt" or "12pt").
    # "pointsize": "10pt",
    #
    # Additional stuff for the LaTeX preamble.
    # "preamble": "",
    #
    # Latex figure (float) alignment
    # "figure_align": "htbp",
}

# Grouping the document tree into LaTeX files. List of tuples
# (source start file, target name, title,
#  author, documentclass [howto, manual, or own class]).
latex_documents = [
    (master_doc, project + ".tex", project + " Documentation", meta.author, "manual"),
]


# -- Options for manual page output ------------------------------------------

# One entry per manual page. List of tuples
# (source start file, name, description, authors, manual section).
man_pages = [(master_doc, project, project + " Documentation", [author], 1)]


# -- Options for Texinfo output ----------------------------------------------

# Grouping the document tree into Texinfo files. List of tuples
# (source start file, target name, title, author,
#  dir menu entry, description, category)
texinfo_documents = [
    (
        master_doc,
        project,
        project + " Documentation",
        author,
        project,
        meta.description,
        "Miscellaneous",
    ),
]


# -- Options for Epub output -------------------------------------------------

# Bibliographic Dublin Core info.
epub_title = project

# The unique identifier of the text. This can be a ISBN number
# or the project homepage.
#
# epub_identifier = ""

# A unique identification for the text.
#
# epub_uid = ""

# A list of files that should not be packed into the epub file.
epub_exclude_files = ["search.html"]


# -- Extension configuration -------------------------------------------------

# -- Options for intersphinx extension ---------------------------------------

# Example configuration for intersphinx
# Common intersphinx mappings can be found here:
# https://gist.github.com/bskinn/0e164963428d4b51017cebdb6cda5209
intersphinx_mapping = {
    "python": ("https://docs.python.org/{.major}".format(sys.version_info), None),
    "attrs": ("https://www.attrs.org/en/stable/", None),
    "numpy": ("https://numpy.org/doc/stable/", None),
    "scipy": ("https://docs.scipy.org/doc/scipy/reference/", None),
    "matplotlib": ("https://matplotlib.org/stable/", None),
    "pandas": ("https://pandas.pydata.org/pandas-docs/stable/", None),
    "Pillow": ("https://pillow.readthedocs.io/en/stable/", None),
    "skimage": ("https://scikit-image.org/docs/stable/", None),
    "sklearn": ("https://scikit-learn.org/stable/", None),
}

# -- Options for todo extension ----------------------------------------------

# If true, `todo` and `todoList` produce output, else they produce nothing.
todo_include_todos = True
