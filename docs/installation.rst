.. highlight:: shell

============
Installation
============

With ``pip``
-------------

.. note::  We **strongly recommend** using ``CuBIDS`` with environment management. For this, we recommend 
           `miniconda <https://docs.conda.io/en/latest/miniconda.html>`_.

Once you've installed and instantiated a new conda environment (for example, named ``cubids``),
download ``CuBIDS`` from the 
`Python Package Manager (Pypi) <https://pip.pypa.io/en/stable/installation/>`_ by running the following:

.. code-block:: console

    $ conda activate cubids
    $ pip install CuBIDS


From Source
------------

The source code for CuBIDS can be downloaded from the `Github repo`_.

To install the software, you can clone the public repository:

.. code-block:: console

    $ git clone https://github.com/PennLINC/CuBIDS.git

Once you have a copy of the source, you can install it with:

.. code-block:: console

    $ cd CuBIDS
    $ python setup.py install

Appendix — ``cubids-validate``
-------------------------------------

``cubids-validate`` is a convenience tool that wraps the official Bids Validator and parses the output for ease of use.

To use ``cubids-validate``, you need to install `node.js <https://nodejs.org/en/>`_, and then install the official Bids Validator available `here <http://bids-standard.github.io/bids-validator/>`_.

Appendix — ``datalad``
-------------------------------------

We also recommend using ``CuBIDS`` with ``datalad``; to install datalad, simply run (in your conda environment):

.. code-block:: console
    
    $ conda install -y -c conda-forge git-annex datalad
    $ pip install --upgrade datalad datalad_container

.. _Github repo: https://github.com/PennLINC/CuBIDS