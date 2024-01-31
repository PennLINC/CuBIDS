.. include:: links.rst

Glossary
========

.. glossary::

    Key Group
        A set of scans whose filenames share all `BIDS filename key-value pairs`_,
        excluding subject and session.
        The key group is derived from the common BIDS filename elements.
        For example, ``acquisition-*_datatype-*_run-*_task-*_suffix``.

    Parameter Group
        A set of scans with identical metadata parameters in their sidecars.
        Defined within a Key Group.
        Numerically identified, meaning that each Key Group will have *n* Param Groups,
        where *n* is the number of unique sets of scanning parameters present in that Key Group
        (e.g., 1, 2, etc.).

    Dominant Group
        The Param Group that contains the most scans in its Key Group.

    Variant Group
        Any Param Group that is non-dominant.

    Rename Key Group
        Auto-generated, recommended new Key Group name for Variant Groups.
        Based on the metadata parameters that cause scans in Variant Groups to vary from those
        in their respective Dominant Groups.

    Acquisition Group
        A collection of sessions across participants that contains the exact same set of Key
        and Param Groups.


References
----------

.. footbibliography::
