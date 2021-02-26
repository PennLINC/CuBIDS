#!/usr/bin/env python

"""The setup script."""

from setuptools import setup, find_packages

with open('README.rst') as readme_file:
    readme = readme_file.read()

with open('HISTORY.rst') as history_file:
    history = history_file.read()

setup_requirements = ['pytest-runner']

setup(
    author="PennLINC",
    author_email='matthew.cieslak@pennmecidine.upenn.edu',
    python_requires='>=3.5',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT',
        'Natural Language :: English',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
    ],
    description="BIDS On Disk Editor",
    entry_points={
        'console_scripts': [
            'bond-group=bond.cli:bond_group',
            'bond-apply=bond.cli:bond_apply',
            'bond-purge=bond.cli:bond_purge',
            'bond-undo=bond.cli:bond_undo',
            'bids-sidecar-merge=bond.cli:bids_sidecar_merge',
            'bond-validate=bond.cli:bond_validate',
            'bond-datalad-save=bond.cli:bond_datalad_save',
            'bond-print-metadata-fields=bond.cli:'
            'bond_print_metadata_fields',
            'bond-remove-metadata-fields=bond.cli:'
            'bond_remove_metadata_fields'
        ],
    },
    license="GNU General Public License v3",
    long_description=readme + '\n\n' + history,
    include_package_data=True,
    keywords='bond',
    name='bond',
    packages=find_packages(include=['bond', 'bond.*']),
    setup_requires=setup_requirements,
    test_suite='tests',
    url='https://github.com/pennlinc/bond',
    version='0.1.0',
    zip_safe=False,
)
