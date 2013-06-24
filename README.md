cog Build Testing and CI
========================
An automated build testing and continuous integration tool designed for the
simulation and analysis tools of the [SNO+](http://snoplus.phy.queensu.ca)
experiment.

Tests are expressed in Python modules, which are executed as jobs submitted to
a SLURM cluster.

Requirements
------------
* Python 2.6+
* A SLURM cluster
* A CouchDB server

Installation
------------

First, install the package:

    $ python setup.py install

Use of a `virtualenv` is recommended.

Next, push the web interface to your CouchDB server. This includes both a
CouchApp user interface and the views and filters needed internally by cog.

    $ cd web && ./egret push http://your-server:5984/dbname

If you wish to use the provided web interface, it is installed at
`http://your-server:5984/dbname/_design/cog/index.html`. Use of a proxy to
clean up this URL is recommended.

Usage
-----
Because it submits jobs to a SLURM cluster, cog must be run on a SLURM submit
host, as a user with submission capabilities.

    $ cog config/config.json

Configuration is loaded from a JSON file. An example is provided in the
`config` directory.

Documentation
-------------
Complete documentation is available in the `doc` directory. To build HTML
documentation,

    $ cd doc
    $ make html

Output is placed in `doc/_build/html`.

