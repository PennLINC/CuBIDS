.. highlight:: shell

.. _installationpage:

============
Installation
============

.. note::  We **strongly recommend** using ``CuBIDS`` with environment management. For this, we recommend 
           `miniconda <https://docs.conda.io/en/latest/miniconda.html>`_ 
           (`miniforge <https://github.com/conda-forge/miniforge>`_ for M1 Chip Mac Machines).

Once you've installed conda, initialize a new conda environment (for example, named ``cubids``) as follows:

.. code-block:: console

    $ conda create -n cubids python=3.8
    $ conda activate cubids

You are now ready to install CuBIDS. You can do so in one of two ways. 

To obtain ``CuBIDS`` locally, we can use ``pip`` to download our software from the
`Python Package Manager (Pypi) <https://pypi.org/project/cubids/>`_ by running the following commands:

.. code-block:: console

    $ pip install CuBIDS

Alternatively, you can clone the source code for ``CuBIDS`` from our `GitHub repository`_ 
using the following command: 

.. code-block:: console

    $ git clone https://github.com/PennLINC/CuBIDS.git

Once you have a copy of the source, you can install it with:

.. code-block:: console

    $ cd CuBIDS
    $ pip install -e .


We will now need to install some dependencies of ``CuBIDS``. To do this, we first must install 
nodejs. We can accomplish this using the following command:

.. code-block:: console

    $ conda install nodejs

Now that we have npm installed, we can install the ``bids-validator`` using the following command:

.. code-block:: console

    $ npm install -g bids-validator@1.7.2

In our example walkthrough, we use ``bids-validator`` v1.7.2. using a different version of the 
validator may result in slightly different validation CSV printouts, but ``CuBIDS`` is compatible with all 
versions of the validator at or above v1.6.2.

We also recommend using ``CuBIDS`` with the optional ``DatLad`` version control capabilities.
We use ``DataLad`` throughout our walkthrough of the CuBIDS Workflow on :doc:`the Example Walkthrough page <example>`.
To leverage the version control capabilities, you will need to install both ``DataLad`` and ``git-annex``, 
the large file storage software ``DataLad`` runs under the hood. Installation instructions 
for ``DataLad`` and ``git-annex`` can be found `here <https://handbook.datalad.org/en/latest/intro/installation.html>`_

.. _GitHub repository: https://github.com/PennLINC/CuBIDS