.. Logshipper documentation master file, created by
   sphinx-quickstart on Sun Oct 19 11:51:10 2014.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to Logshipper's documentation!
======================================

Logshipper is a perfomant, flexible tool to get log entries from one system
to the other. There's support for tailing files, listening to syslog, as well
as sending log entries to RabbitMQ, Statsd and all python-supported logs.


Inputs
======

syslog
------

.. autoclass:: logshipper.input.Syslog

command
-------

.. autoclass:: logshipper.input.Command

stdin
-----

.. autoclass:: logshipper.input.Stdin

tail
----

.. autoclass:: logshipper.tail.Tail

Log manipulation
================

match
-----

.. autofunction:: logshipper.filters.prepare_match

set
---

.. autofunction:: logshipper.filters.prepare_set

unset
-----

.. autofunction:: logshipper.filters.prepare_unset

drop
----

.. autofunction:: logshipper.filters.prepare_drop

call
----

.. autofunction:: logshipper.filters.prepare_call

jump
----

.. autofunction:: logshipper.filters.prepare_jump

logging
-------

.. autofunction:: logshipper.pylogging.prepare_logging

Outputs
=======

rabbitmq
--------

.. autofunction:: logshipper.filters.prepare_rabbitmq

statsd
------

.. autofunction:: logshipper.filters.prepare_statsd

stdout
------

.. autofunction:: logshipper.filters.prepare_stdout

debug
-----

.. autofunction:: logshipper.filters.prepare_debug



Contents:

.. toctree::
   :maxdepth: 2



Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

