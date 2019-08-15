==============
 Installation
==============

Install using pip
-----------------

At the command line::

    $ pip install keystonemiddleware

Or, if you want to use it in a virtualenvwrapper::

    $ mkvirtualenv keystonemiddleware
    $ pip install keystonemiddleware

Install optional dependencies
-----------------------------

Certain keystonemiddleware features are only available if specific libraries
are available. These libraries can be installed using pip as well.

To install support for audit notifications::

    $ pip install keystonemiddleware[audit_notifications]
