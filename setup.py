#!/usr/bin/env python3
from setuptools import setup

with open("README.md", "r") as f:
    long_description = f.read()

setup(
    name='nuttssh',
    version='0.1',
    description='SSH switchboard for internally patching forwarded ports',
    long_description=long_description,
    long_description_content_type="text/markdown",
    url='http://github.com/matthijskooijman/nuttssh',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3 :: Only',
        'Environment :: No Input/Output (Daemon)',
        'Framework :: AsyncIO',
        'Topic :: Internet :: Proxy Servers',
        'Topic :: System :: Networking',
    ],
    # For async def / await
    python_requires='>=3.5',
    author='Matthijs Kooijman',
    author_email='matthijs@stdin.nl',
    license='MIT',
    packages=['nuttssh'],
    install_requires=[
        'asyncssh',
    ],
    extras_require={
        'dev': [
            'flake8',
            'flake8-per-file-ignores',
            'flake8-bugbear',
            'flake8-comprehensions',
            'flake8-mutable',
            'flake8-mypy',
            'flake8-docstrings',
            'flake8-print',
            'flake8-tuple',
            'flake8-commas',
            'flake8-isort',
        ],
    },
)
