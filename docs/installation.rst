.. highlight:: shell

============
Installation
============

With ``pip``
-------------

Download from the `Python Package Manager (Pypi) <https://pip.pypa.io/en/stable/installation/>`_ by running the command:

.. code-block:: console

    $ pip install CuBIDS


From Source
------------

The source code for CuBIDS can be downloaded from the `Github repo`_.

To install the software, you can either clone the public repository:

.. code-block:: console

    $ git clone git://github.com/PennLINC/CuBIDS

Once you have a copy of the source, you can install it with:

.. code-block:: console

    $ cd CuBIDS
    $ python setup.py install

Appendix — ``cubids-validate``
-------------------------------------

``cubids-validate`` is a convenience tool that wraps the official Bids Validator and parses the output for ease of use.

To use ``cubids-validate``, you need to install `node.js <https://nodejs.org/en/>`_, and then install the official Bids Validator available `here <http://bids-standard.github.io/bids-validator/>`_.

.. _Github repo: https://github.com/PennLINC/CuBIDS