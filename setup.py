#!/usr/bin/env python

from setuptools import find_packages, setup

DEPENDENCIES = [
    'alpheus',
    'BeautifulSoup>=3.2.0',
    'cssselect',
    'Django>=1.4,<1.5',
    'django-compressor==1.1.2',
    'django-debug-toolbar==0.8.3',
    'django-devserver==0.0.2',
    'django-extensions',
    'django-haystack==1.0.1-final',
    'django-piston==0.2.3',
    'django-tastypie==0.9.10',
    'feedparser==4.1',
    'freebase',
    'httplib2',
    'lxml',
    'Markdown==2.0.3',
    'Pillow',
    'PyBrowserID',
    'pysolr==2.0.9',
    'sorl-thumbnail==3.2.5',
    'South==0.7.2',
    'twitter>=1.5',
    'wsgiref==0.1.2',
    ]

setup(
    name='openparliament',
    version='0.5',
    description='A site that scrapes and republishes information on Canada\'s'\
                'House of Commons.',
    author='Michael Mulley',
    url='http://openparliament.ca',
    packages=find_packages(),
    include_package_data=True,
    install_requires=DEPENDENCIES,
    dependency_links=[
        'https://github.com/rhymeswithcycle/alpheus/archive/master.zip#egg=alpheus',
        'https://github.com/django-extensions/django-extensions/archive/master.zip#egg=django-extensions',
        ]
    )
