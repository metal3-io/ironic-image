========
Features
========

Async
-----

* A :py:class:`.futurist.GreenThreadPoolExecutor` using `eventlet`_ green
  thread pools. It provides a standard `executor`_ API/interface and it also
  gathers execution statistics. It returns instances of
  :py:class:`.futurist.GreenFuture` objects.
* A :py:class:`.futurist.ProcessPoolExecutor` derivative that gathers execution
  statistics. It returns instances of :py:class:`.futurist.Future` objects.
* A :py:class:`.futurist.SynchronousExecutor` that **doesn't** run
  concurrently. It has the same `executor`_ API/interface and it also
  gathers execution statistics. It returns instances
  of :py:class:`.futurist.Future` objects.
* A :py:class:`.futurist.ThreadPoolExecutor` derivative that gathers
  execution statistics. It returns instances
  of :py:class:`.futurist.Future` objects.

Periodics
---------

* A :py:class:`.futurist.periodics.PeriodicWorker` that can use the previously
  mentioned executors to run asynchronous work periodically in parallel
  or synchronously. It does this by executing arbitrary functions/methods
  that have been decorated with the :py:func:`.futurist.periodics.periodic`
  decorator according to a internally maintained schedule (which itself is
  based on the `heap`_ algorithm).

.. _heap: https://en.wikipedia.org/wiki/Heap_%28data_structure%29
.. _eventlet: http://eventlet.net/
.. _executor: https://docs.python.org/dev/library/concurrent.futures.html#executor-objects
