=============
API Reference
=============

---------
Executors
---------

.. autoclass:: futurist.GreenThreadPoolExecutor
    :members:
    :special-members: __init__

.. autoclass:: futurist.ProcessPoolExecutor
    :members:
    :special-members: __init__

.. autoclass:: futurist.SynchronousExecutor
    :members:
    :special-members: __init__

.. autoclass:: futurist.ThreadPoolExecutor
    :members:
    :special-members: __init__

-------
Futures
-------

.. autoclass:: futurist.Future
    :members:

.. autoclass:: futurist.GreenFuture
    :members:

---------
Periodics
---------

.. autoclass:: futurist.periodics.PeriodicWorker
    :members:
    :special-members: __init__, __len__

.. autofunction:: futurist.periodics.periodic

.. autoclass:: futurist.periodics.Watcher
    :members:

-------------
Miscellaneous
-------------

.. autoclass:: futurist.ExecutorStatistics
    :members:

----------
Exceptions
----------

.. autoclass:: futurist.RejectedSubmission
    :members:

-------
Waiters
-------

.. autofunction:: futurist.waiters.wait_for_any
.. autofunction:: futurist.waiters.wait_for_all
.. autoclass:: futurist.waiters.DoneAndNotDoneFutures
