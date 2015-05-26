#!/usr/bin/env python
# encoding: utf-8
#
# Licensed to the Apache Software Foundation (ASF) under one or more
# contributor license agreements.  See the NOTICE file distributed with
# this work for additional information regarding copyright ownership.
# The ASF licenses this file to You under the Apache License, Version 2.0
# (the "License"); you may not use this file except in compliance with
# the License.  You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# $Id$

import os.path

try:
    from ez_setup import use_setuptools
    use_setuptools()
except ImportError:
    pass

try:
    from setuptools import setup, find_packages
except ImportError:
    from distutils.core import setup, find_packages

version = '1.8.9'

_descr = u'''**********
tika
***************

.. contents::
Tika python pure REST based library.
'''
_keywords = 'tika digital babel fish apache'
_classifiers = [
    'Development Status :: 3 - Alpha',
    'Environment :: Console',
    'Intended Audience :: Developers',
    'Intended Audience :: Information Technology',
    'Intended Audience :: Science/Research',
    'License :: OSI Approved :: Apache Software License',
    'Operating System :: OS Independent',
    'Programming Language :: Python',
    'Topic :: Database :: Front-Ends',
    'Topic :: Scientific/Engineering',
    'Topic :: Software Development :: Libraries :: Python Modules',
]

def read(*rnames):
    return open(os.path.join(os.path.dirname(__file__), *rnames)).read()

long_description = _descr

setup(
    name='tika',
    version=version,
    description='Apache Tika Python library',
    long_description=long_description,
    classifiers=_classifiers,
    keywords=_keywords,
    author='Chris Mattmann',
    author_email='chris.a.mttmnn@nasa.gov',
    url='http://github.com/chrismattmann/tika-python',
    download_url='http://github.com/chrismattmann/tika-python',
    license=read('LICENSE.txt'),
    packages=find_packages(exclude=['ez_setup']),
    namespace_packages=['tika'],
    include_package_data=True,
    zip_safe=True,
    test_suite='tika.tests',
    entry_points={
        'console_scripts': [
            'tika-python = tika.tika:main'
        ],
    },
    package_data = {
        # And include any *.conf files found in the 'conf' subdirectory
        # for the package
    },
    install_requires=[
        'setuptools',
        'requests'
    ],
    extras_require={
    },
)
