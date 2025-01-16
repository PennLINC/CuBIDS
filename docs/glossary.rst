.. _BIDS filename key-value pairs: https://bids-specification.readthedocs.io/en/stable/02-common-principles.html#file-name-key-value-pairs

Glossary
========

.. glossary::

    Entity Set
        A set of scans whose filenames share all `BIDS filename key-value pairs`_,
        excluding subject and session.
        The entity set is derived from the common BIDS filename elements.
        For example, ``acquisition-*_datatype-*_run-*_task-*_suffix``.

    Parameter Group
        A set of scans with identical metadata parameters in their sidecars.
        Defined within a Entity Set.
        Numerically identified, meaning that each Entity Set will have *n* Param Groups,
        where *n* is the number of unique sets of scanning parameters present in that Entity Set
        (e.g., 1, 2, etc.).

    Dominant Group
        The Param Group that contains the most scans in its Entity Set.

    Variant Group
        Any Param Group that is non-dominant.

    Rename Entity Set
        Auto-generated, recommended new Entity Set name for Variant Groups.
        Based on the metadata parameters that cause scans in Variant Groups to vary from those
        in their respective Dominant Groups.

    Acquisition Group
        A collection of sessions across participants that contains the exact same set of Entity
        and Param Groups.


References
----------

.. footbibliography::
