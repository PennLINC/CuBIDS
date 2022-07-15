#!/usr/bin/env python

"""The setup script."""

from setuptools import setup, find_packages

# with open('README.rst') as readme_file:
#     readme = readme_file.read()

with open("README.rst", "r", encoding='utf-8') as readme_file:
    readme = readme_file.read()

with open('HISTORY.rst') as history_file:
    history = history_file.read()

setup_requirements = ['pytest-runner']

setup(
    author="Neuroinformatics Team of PennLINC",
    author_email='sydney.covitz@pennmecidine.upenn.edu',
    maintainer='Sydney Covitz',
    python_requires='>=3.5',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
    ],
    description="BIDS Curation Tool",
    entry_points={
        'console_scripts': [
            'cubids-group=cubids.cli:cubids_group',
            'cubids-apply=cubids.cli:cubids_apply',
            'cubids-purge=cubids.cli:cubids_purge',
            'cubids-add-nifti-info=cubids.cli:cubids_add_nifti_info',
            'cubids-copy-exemplars=cubids.cli:cubids_copy_exemplars',
            'cubids-undo=cubids.cli:cubids_undo',
            'bids-sidecar-merge=cubids.cli:bids_sidecar_merge',
            'cubids-validate=cubids.cli:cubids_validate',
            'cubids-datalad-save=cubids.cli:cubids_datalad_save',
            'cubids-print-metadata-fields=cubids.cli:'
            'cubids_print_metadata_fields',
            'cubids-remove-metadata-fields=cubids.cli:'
            'cubids_remove_metadata_fields'
        ],
    },
    license="MIT License",
    long_description=readme + '\n\n' + history,
    include_package_data=True,
    keywords='cubids',
    name='cubids',
    packages=find_packages(include=['cubids', 'cubids.*']),
    setup_requires=setup_requirements,
    test_suite='tests',
    url='https://github.com/pennlinc/cubids',
    version='1.0.4',
    zip_safe=False,
)
