import os
import tarfile
from setuptools import setup

def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

setup(
    name = "cog",
    version = "0.6",
    author = "Andy Mastbaum",
    author_email = "amastbaum@gmail.com",
    description = ("An automatic testing utility for SNO+ code"),
    license = "BSD",
    keywords = "continuous integration couchdb build test",
    url = "http://github.com/mastbaum/cog",
    long_description = read('README.md'),
    classifiers = [
        "Development Status :: 3 - Alpha",
        "Topic :: Software Development :: Libraries :: Application Frameworks",
        "License :: OSI Approved :: BSD License",
    ],
    packages = ['cog', 'cog.tasks'],
    scripts = ['bin/cog', 'bin/q', 'bin/qsetup', 'bin/sbatch.scr'],
    install_requires = ['couchdb', 'sphinx'],
    include_package_data = True
)

