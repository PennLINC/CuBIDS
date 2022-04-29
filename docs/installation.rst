.. highlight:: shell

.. _installationpage:

============
Installation
============

With ``pip``
-------------

.. note::  We **strongly recommend** using ``CuBIDS`` with environment management. For this, we recommend 
           `miniconda <https://docs.conda.io/en/latest/miniconda.html>`_.

Once you've installed conda, instantiated a new conda environment (for example, named ``cubids``),
and download ``CuBIDS`` from the 
`Python Package Manager (Pypi) <https://pip.pypa.io/en/stable/installation/>`_ by running the following:

.. code-block:: console

    $ conda create -n cubids python=3.7
    $ conda activate cubids
    $ pip install CuBIDS


From Source
------------

Alternatively, the source code for CuBIDS can be downloaded from the `Github repo`_.

To install the software, you can clone the public repository:

.. code-block:: console

    $ git clone https://github.com/PennLINC/CuBIDS.git

Once you have a copy of the source, you can install it with:

.. code-block:: console

    $ cd CuBIDS
    $ pip install .

Appendix — ``cubids-validate``
-------------------------------------

``cubids-validate`` is a convenience tool that wraps the official Bids Validator and parses the output for ease of use.

To use ``cubids-validate``, you need to install ``node.js``, and then install the official Bids Validator. 

.. code-block:: console

    $ conda install nodejs
    $ npm install -g bids-validator

Appendix — ``datalad``
-------------------------------------

We also recommend using ``CuBIDS`` with ``datalad``; to install datalad, simply run (in your conda environment):

.. code-block:: console
    
    $ conda install -y -c conda-forge git-annex datalad
    $ pip install --upgrade datalad datalad_container

.. _Github repo: https://github.com/PennLINC/CuBIDS