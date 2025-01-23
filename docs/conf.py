#!/usr/bin/env python
#
# cubids documentation build configuration file, created by
# sphinx-quickstart on Fri Jun  9 13:47:02 2017.
#
# This file is execfile()d with the current directory set to its
# containing dir.
#
# Note that not all possible configuration values are present in this
# autogenerated file.
#
# All configuration values have a default; values that are commented out
# serve to show the default.

# If extensions (or modules to document with autodoc) are in another
# directory, add these directories to sys.path here. If the directory is
# relative to the documentation root, use os.path.abspath to make it
# absolute, like shown here.
import os
import sys

sys.path.insert(0, os.path.abspath(".."))

import cubids

sys.path.insert(0, os.path.abspath("sphinxext"))

from github_link import make_linkcode_resolve

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
sys.path.append(os.path.abspath("sphinxext"))
sys.path.insert(0, os.path.abspath("../wrapper"))

# -- General configuration ---------------------------------------------

# If your documentation needs a minimal Sphinx version, state it here.
#
needs_sphinx = "1.5.3"

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    "hoverxref.extension",
    "nbsphinx",
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",  # standard
    "sphinx.ext.doctest",
    "sphinx.ext.intersphinx",  # links code to other packages
    "sphinx.ext.linkcode",  # links to code from api
    "sphinx.ext.mathjax",  # include formulae in html
    "sphinx.ext.napoleon",  # alternative to numpydoc
    "sphinx_copybutton",  # for copying code snippets
    "sphinx_gallery.load_style",
    "sphinxarg.ext",  # argparse extension
    "sphinxcontrib.bibtex",  # bibtex-based bibliographies
    "sphinx_design",  # for adding in-line badges etc
]

# Mock modules in autodoc:
autodoc_mock_imports = [
    "numpy",
    "nitime",
    "matplotlib",
]

# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

# The suffix(es) of source filenames.
# You can specify multiple suffix as a list of string:
#
# source_suffix = ['.rst', '.md']
source_suffix = ".rst"

# The master toctree document.
master_doc = "index"

# General information about the project.
project = "CuBIDS"
copyright = "2020, PennLINC"
author = "PennLINC"

# The version info for the project you're documenting, acts as replacement
# for |version| and |release|, also used in various other places throughout
# the built documents.
#
# The short X.Y version.
version = cubids.__version__
# The full version, including alpha/beta/rc tags.
release = cubids.__version__

# The language for content autogenerated by Sphinx. Refer to documentation
# for a list of supported languages.
#
# This is also used if you do content translation via gettext catalogs.
# Usually you set "language" from the command line for these cases.
language = "en"

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This patterns also effect to html_static_path and html_extra_path
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = "default"

# If true, `todo` and `todoList` produce output, else they produce nothing.
todo_include_todos = False

# -----------------------------------------------------------------------------
# Napoleon settings
# -----------------------------------------------------------------------------
napoleon_google_docstring = False
napoleon_numpy_docstring = True
napoleon_custom_sections = ["License"]
napoleon_include_init_with_doc = True
napoleon_include_private_with_doc = False
napoleon_include_special_with_doc = False
napoleon_use_admonition_for_examples = True
napoleon_use_admonition_for_notes = True
napoleon_use_admonition_for_references = True
napoleon_use_ivar = True
napoleon_use_param = True
napoleon_use_keyword = True
napoleon_use_rtype = True
napoleon_preprocess_types = False
napoleon_type_aliases = None
napoleon_attr_annotations = True

# -----------------------------------------------------------------------------
# HTML output
# -----------------------------------------------------------------------------
# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = "sphinx_rtd_theme"
html_theme_path = [
    "_themes",
]

# Theme options are theme-specific and customize the look and feel of a
# theme further.  For a list of options available for each theme, see the
# documentation.
#
# html_theme_options = {}

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ["_static"]

# -----------------------------------------------------------------------------
# HTMLHelp output
# -----------------------------------------------------------------------------
# Output file base name for HTML help builder.
htmlhelp_basename = "cubidsdoc"

# The following is used by sphinx.ext.linkcode to provide links to github
linkcode_resolve = make_linkcode_resolve(
    "cubids",
    "https://github.com/PennLINC/cubids/blob/{revision}/{package}/{path}#L{lineno}",
)

# -----------------------------------------------------------------------------
# intersphinx
# -----------------------------------------------------------------------------
_python_version_str = f"{sys.version_info.major}.{sys.version_info.minor}"
_python_doc_base = "https://docs.python.org/" + _python_version_str
intersphinx_mapping = {
    "python": (_python_doc_base, None),
    "numpy": ("https://numpy.org/doc/stable/", (None, "./_intersphinx/numpy-objects.inv")),
    "scipy": (
        "https://docs.scipy.org/doc/scipy/reference",
        (None, "./_intersphinx/scipy-objects.inv"),
    ),
    "sklearn": ("https://scikit-learn.org/stable", (None, "./_intersphinx/sklearn-objects.inv")),
    "matplotlib": ("https://matplotlib.org/", (None, "https://matplotlib.org/objects.inv")),
    "pandas": ("https://pandas.pydata.org/pandas-docs/stable/", None),
    "pybids": ("https://bids-standard.github.io/pybids/", None),
    "nibabel": ("https://nipy.org/nibabel/", None),
    "nilearn": ("http://nilearn.github.io/stable/", None),
    "datalad": ("https://docs.datalad.org/en/stable/", None),
}

# -----------------------------------------------------------------------------
# sphinxcontrib-bibtex
# -----------------------------------------------------------------------------
bibtex_bibfiles = ["../cubids/data/references.bib"]
bibtex_style = "unsrt"
bibtex_reference_style = "author_year"
bibtex_footbibliography_header = ""

# -----------------------------------------------------------------------------
# Options for LaTeX output
# -----------------------------------------------------------------------------
latex_elements = {
    # The paper size ('letterpaper' or 'a4paper').
    #
    # 'papersize': 'letterpaper',
    # The font size ('10pt', '11pt' or '12pt').
    #
    # 'pointsize': '10pt',
    # Additional stuff for the LaTeX preamble.
    #
    # 'preamble': '',
    # Latex figure (float) alignment
    #
    # 'figure_align': 'htbp',
}

# Grouping the document tree into LaTeX files. List of tuples
# (source start file, target name, title, author, documentclass
# [howto, manual, or own class]).
latex_documents = [
    (master_doc, "cubids.tex", "CuBIDS Documentation", "PennLINC", "manual"),
]

# -----------------------------------------------------------------------------
# Options for manual page output
# -----------------------------------------------------------------------------
# One entry per manual page. List of tuples
# (source start file, name, description, authors, manual section).
man_pages = [(master_doc, "cubids", "CuBIDS Documentation", [author], 1)]

# -----------------------------------------------------------------------------
# Options for Texinfo output
# -----------------------------------------------------------------------------
# Grouping the document tree into Texinfo files. List of tuples
# (source start file, target name, title, author,
#  dir menu entry, description, category)
texinfo_documents = [
    (
        master_doc,
        "cubids",
        "CuBIDS Documentation",
        author,
        "cubids",
        "One line description of project.",
        "Miscellaneous",
    ),
]

# -----------------------------------------------------------------------------
# Automodule
# -----------------------------------------------------------------------------
add_module_names = False

# -----------------------------------------------------------------------------
# Hoverxref
# -----------------------------------------------------------------------------
hoverxref_auto_ref = True
hoverxref_mathjax = True
hoverxref_roles = [
    "numref",
    "confval",
    "setting",
    "term",
    "footcite",
]

# -----------------------------------------------------------------------------
# sphinx_copybutton
# -----------------------------------------------------------------------------
# Configuration for sphinx_copybutton to remove shell prompts, i.e. $
copybutton_prompt_text = "$ "
copybutton_only_copy_prompt_lines = (
    False  # ensures all lines are copied, even those without a prompt
)
