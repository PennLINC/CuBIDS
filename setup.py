#!/usr/bin/env python

"""The setup script."""

from setuptools import setup, find_packages

with open('README.rst') as readme_file:
    readme = readme_file.read()

with open('HISTORY.rst') as history_file:
    history = history_file.read()

requirements = ['pybids', 'tqdm', 'pandas', 'numpy']

setup_requirements = ['pytest-runner']

test_requirements = ['pytest>=3']

setup(
    author="Matt Cieslak",
    author_email='mattcieslak@gmail.com',
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
            'bond=bond.cli:main',
        ],
    },
    install_requires=requirements,
    license="GNU General Public License v3",
    long_description=readme + '\n\n' + history,
    include_package_data=True,
    keywords='bond',
    name='bond',
    packages=find_packages(include=['bond', 'bond.*']),
    setup_requires=setup_requirements,
    test_suite='tests',
    tests_require=test_requirements,
    url='https://github.com/pennlinc/bond',
    version='0.1.0',
    zip_safe=False,
)
