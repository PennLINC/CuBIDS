.. highlight:: shell

============
Installation
============


From sources
------------

The sources for BOnD can be downloaded from the `Github repo`_.

You can either clone the public repository:

.. code-block:: console

    $ git clone git://github.com/PennLINC/BOnD

Or download the `tarball`_:

.. code-block:: console

    $ curl -OJL https://github.com/PennLINC/BOnD/tarball/master

Once you have a copy of the source, you can install it with:

.. code-block:: console

    $ python setup.py install


.. _Github repo: https://github.com/PennLINC/BOnD
.. _tarball: https://github.com/PennLINC/BOnD/tarball/master

For running ``bond-validate``, we recommend pulling our Docker image to use the most appropriate version of the validator:

.. code-block:: console

    $ docker pull pennlinc/bond
