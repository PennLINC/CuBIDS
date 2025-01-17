.. highlight:: shell

.. _installationpage:

============
Installation
============

.. note::
    We **strongly recommend** using ``CuBIDS`` with environment management.
    For this, we recommend `miniconda <https://docs.conda.io/en/latest/miniconda.html>`_
    (`miniforge <https://github.com/conda-forge/miniforge>`_ for M1 Chip Mac Machines).

Once you've installed conda,
initialize a new conda environment (for example, named ``cubids``) as follows:

.. code-block:: console

    $ conda create -n cubids python=3.12 pip
    $ conda activate cubids

You are now ready to install CuBIDS.
You can do so in one of two ways.

To obtain ``CuBIDS`` locally, we can use ``pip`` to download our software from the
`Python Package Manager (Pypi) <https://pypi.org/project/cubids/>`_ by running the following commands:

.. code-block:: console

    $ pip install CuBIDS

Alternatively,
you can clone the source code for ``CuBIDS`` from our `GitHub repository`_ using the following command:

.. code-block:: console

    $ git clone https://github.com/PennLINC/CuBIDS.git

Once you have a copy of the source, you can install it with:

.. code-block:: console

    $ cd CuBIDS
    $ pip install -e .

We will now need to install some dependencies of ``CuBIDS``.
To do this, we first must install deno to run `bids-validator`.
We can accomplish this using the following command:

.. code-block:: console

    $ conda install deno

The new schema-based ``bids-validator`` doesn't need to be installed 
and will be implemented automatically when `cubids validate` is called

.. dropdown:: If there is no Internet connection on compute nodes

    You should run one of these commands below, after installing deno, that downloads the latest version 
    of the bids-validator in your virtual environment either by installing a lightscript version 
    (into ``$HOME/.deno/bin``) or by compiling, respectively:

    ..  code-block:: console

        $ deno install -ERN -g -n bids-validator jsr:@bids/validator
    
    or:

    ..  code-block:: console

        $ deno compile -ERN -o bids-validator jsr:@bids/validator

    For more information, you can read: https://bids-validator.readthedocs.io/en/latest/user_guide/command-line.html

We also recommend using ``CuBIDS`` with the optional ``DataLad`` version control capabilities.
We use ``DataLad`` throughout our walkthrough of the CuBIDS Workflow on
:doc:`the Example Walkthrough page <example>`.
To leverage the version control capabilities,
you will need to install both ``DataLad`` and ``git-annex``,
the large file storage software ``DataLad`` runs under the hood.
Installation instructions for ``DataLad`` and ``git-annex`` can be found
`here <https://handbook.datalad.org/en/latest/intro/installation.html>`_.

.. _GitHub repository: https://github.com/PennLINC/CuBIDS
