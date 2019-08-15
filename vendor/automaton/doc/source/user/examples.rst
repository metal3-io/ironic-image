========
Examples
========

-------------------------
Creating a simple machine
-------------------------

.. testcode::

    from automaton import machines
    m = machines.FiniteMachine()
    m.add_state('up')
    m.add_state('down')
    m.add_transition('down', 'up', 'jump')
    m.add_transition('up', 'down', 'fall')
    m.default_start_state = 'down'
    print(m.pformat())

**Expected output:**

.. testoutput::

    +---------+-------+------+----------+---------+
    |  Start  | Event | End  | On Enter | On Exit |
    +---------+-------+------+----------+---------+
    | down[^] |  jump |  up  |    .     |    .    |
    |    up   |  fall | down |    .     |    .    |
    +---------+-------+------+----------+---------+

------------------------------
Transitioning a simple machine
------------------------------

.. testcode::

    m.initialize()
    m.process_event('jump')
    print(m.pformat())
    print(m.current_state)
    print(m.terminated)
    m.process_event('fall')
    print(m.pformat())
    print(m.current_state)
    print(m.terminated)

**Expected output:**

.. testoutput::

    +---------+-------+------+----------+---------+
    |  Start  | Event | End  | On Enter | On Exit |
    +---------+-------+------+----------+---------+
    | down[^] |  jump |  up  |    .     |    .    |
    |   @up   |  fall | down |    .     |    .    |
    +---------+-------+------+----------+---------+
    up
    False
    +----------+-------+------+----------+---------+
    |  Start   | Event | End  | On Enter | On Exit |
    +----------+-------+------+----------+---------+
    | @down[^] |  jump |  up  |    .     |    .    |
    |    up    |  fall | down |    .     |    .    |
    +----------+-------+------+----------+---------+
    down
    False


-------------------------------------
Running a complex dog-barking machine
-------------------------------------

.. testcode::

    from automaton import machines
    from automaton import runners


    # These reaction functions will get triggered when the registered state
    # and event occur, it is expected to provide a new event that reacts to the
    # new stable state (so that the state-machine can transition to a new
    # stable state, and repeat, until the machine ends up in a terminal
    # state, whereby it will stop...)

    def react_to_squirrel(old_state, new_state, event_that_triggered):
        return "gets petted"


    def react_to_wagging(old_state, new_state, event_that_triggered):
        return "gets petted"


    m = machines.FiniteMachine()

    m.add_state("sits")
    m.add_state("lies down", terminal=True)
    m.add_state("barks")
    m.add_state("wags tail")

    m.default_start_state = 'sits'

    m.add_transition("sits", "barks", "squirrel!")
    m.add_transition("barks", "wags tail", "gets petted")
    m.add_transition("wags tail", "lies down", "gets petted")

    m.add_reaction("barks", "squirrel!", react_to_squirrel)
    m.add_reaction('wags tail', "gets petted", react_to_wagging)

    print(m.pformat())
    r = runners.FiniteRunner(m)
    for (old_state, new_state) in r.run_iter("squirrel!"):
        print("Leaving '%s'" % old_state)
        print("Entered '%s'" % new_state)

**Expected output:**

.. testoutput::

    +--------------+-------------+-----------+----------+---------+
    |    Start     |    Event    |    End    | On Enter | On Exit |
    +--------------+-------------+-----------+----------+---------+
    |    barks     | gets petted | wags tail |    .     |    .    |
    | lies down[$] |      .      |     .     |    .     |    .    |
    |   sits[^]    |  squirrel!  |   barks   |    .     |    .    |
    |  wags tail   | gets petted | lies down |    .     |    .    |
    +--------------+-------------+-----------+----------+---------+
    Leaving 'sits'
    Entered 'barks'
    Leaving 'barks'
    Entered 'wags tail'
    Leaving 'wags tail'
    Entered 'lies down'


------------------------------------
Creating a complex CD-player machine
------------------------------------

.. testcode::

    from automaton import machines


    def print_on_enter(new_state, triggered_event):
       print("Entered '%s' due to '%s'" % (new_state, triggered_event))


    def print_on_exit(old_state, triggered_event):
       print("Exiting '%s' due to '%s'" % (old_state, triggered_event))


    m = machines.FiniteMachine()

    m.add_state('stopped', on_enter=print_on_enter, on_exit=print_on_exit)
    m.add_state('opened',  on_enter=print_on_enter, on_exit=print_on_exit)
    m.add_state('closed',  on_enter=print_on_enter, on_exit=print_on_exit)
    m.add_state('playing',  on_enter=print_on_enter, on_exit=print_on_exit)
    m.add_state('paused',  on_enter=print_on_enter, on_exit=print_on_exit)

    m.add_transition('stopped', 'playing', 'play')
    m.add_transition('stopped', 'opened', 'open_close')
    m.add_transition('stopped', 'stopped', 'stop')

    m.add_transition('opened', 'closed', 'open_close')

    m.add_transition('closed', 'opened', 'open_close')
    m.add_transition('closed', 'stopped', 'cd_detected')

    m.add_transition('playing', 'stopped', 'stop')
    m.add_transition('playing', 'paused', 'pause')
    m.add_transition('playing', 'opened', 'open_close')

    m.add_transition('paused', 'playing', 'play')
    m.add_transition('paused', 'stopped', 'stop')
    m.add_transition('paused', 'opened', 'open_close')

    m.default_start_state = 'closed'

    m.initialize()
    print(m.pformat())

    for event in ['cd_detected', 'play', 'pause', 'play', 'stop',
                  'open_close', 'open_close']:
        m.process_event(event)
        print(m.pformat())
        print("=============")
        print("Current state => %s" % m.current_state)
        print("=============")



**Expected output:**

.. testoutput::

    +------------+-------------+---------+----------------+---------------+
    |   Start    |    Event    |   End   |    On Enter    |    On Exit    |
    +------------+-------------+---------+----------------+---------------+
    | @closed[^] | cd_detected | stopped | print_on_enter | print_on_exit |
    | @closed[^] |  open_close |  opened | print_on_enter | print_on_exit |
    |   opened   |  open_close |  closed | print_on_enter | print_on_exit |
    |   paused   |  open_close |  opened | print_on_enter | print_on_exit |
    |   paused   |     play    | playing | print_on_enter | print_on_exit |
    |   paused   |     stop    | stopped | print_on_enter | print_on_exit |
    |  playing   |  open_close |  opened | print_on_enter | print_on_exit |
    |  playing   |    pause    |  paused | print_on_enter | print_on_exit |
    |  playing   |     stop    | stopped | print_on_enter | print_on_exit |
    |  stopped   |  open_close |  opened | print_on_enter | print_on_exit |
    |  stopped   |     play    | playing | print_on_enter | print_on_exit |
    |  stopped   |     stop    | stopped | print_on_enter | print_on_exit |
    +------------+-------------+---------+----------------+---------------+
    Exiting 'closed' due to 'cd_detected'
    Entered 'stopped' due to 'cd_detected'
    +-----------+-------------+---------+----------------+---------------+
    |   Start   |    Event    |   End   |    On Enter    |    On Exit    |
    +-----------+-------------+---------+----------------+---------------+
    | closed[^] | cd_detected | stopped | print_on_enter | print_on_exit |
    | closed[^] |  open_close |  opened | print_on_enter | print_on_exit |
    |   opened  |  open_close |  closed | print_on_enter | print_on_exit |
    |   paused  |  open_close |  opened | print_on_enter | print_on_exit |
    |   paused  |     play    | playing | print_on_enter | print_on_exit |
    |   paused  |     stop    | stopped | print_on_enter | print_on_exit |
    |  playing  |  open_close |  opened | print_on_enter | print_on_exit |
    |  playing  |    pause    |  paused | print_on_enter | print_on_exit |
    |  playing  |     stop    | stopped | print_on_enter | print_on_exit |
    |  @stopped |  open_close |  opened | print_on_enter | print_on_exit |
    |  @stopped |     play    | playing | print_on_enter | print_on_exit |
    |  @stopped |     stop    | stopped | print_on_enter | print_on_exit |
    +-----------+-------------+---------+----------------+---------------+
    =============
    Current state => stopped
    =============
    Exiting 'stopped' due to 'play'
    Entered 'playing' due to 'play'
    +-----------+-------------+---------+----------------+---------------+
    |   Start   |    Event    |   End   |    On Enter    |    On Exit    |
    +-----------+-------------+---------+----------------+---------------+
    | closed[^] | cd_detected | stopped | print_on_enter | print_on_exit |
    | closed[^] |  open_close |  opened | print_on_enter | print_on_exit |
    |   opened  |  open_close |  closed | print_on_enter | print_on_exit |
    |   paused  |  open_close |  opened | print_on_enter | print_on_exit |
    |   paused  |     play    | playing | print_on_enter | print_on_exit |
    |   paused  |     stop    | stopped | print_on_enter | print_on_exit |
    |  @playing |  open_close |  opened | print_on_enter | print_on_exit |
    |  @playing |    pause    |  paused | print_on_enter | print_on_exit |
    |  @playing |     stop    | stopped | print_on_enter | print_on_exit |
    |  stopped  |  open_close |  opened | print_on_enter | print_on_exit |
    |  stopped  |     play    | playing | print_on_enter | print_on_exit |
    |  stopped  |     stop    | stopped | print_on_enter | print_on_exit |
    +-----------+-------------+---------+----------------+---------------+
    =============
    Current state => playing
    =============
    Exiting 'playing' due to 'pause'
    Entered 'paused' due to 'pause'
    +-----------+-------------+---------+----------------+---------------+
    |   Start   |    Event    |   End   |    On Enter    |    On Exit    |
    +-----------+-------------+---------+----------------+---------------+
    | closed[^] | cd_detected | stopped | print_on_enter | print_on_exit |
    | closed[^] |  open_close |  opened | print_on_enter | print_on_exit |
    |   opened  |  open_close |  closed | print_on_enter | print_on_exit |
    |  @paused  |  open_close |  opened | print_on_enter | print_on_exit |
    |  @paused  |     play    | playing | print_on_enter | print_on_exit |
    |  @paused  |     stop    | stopped | print_on_enter | print_on_exit |
    |  playing  |  open_close |  opened | print_on_enter | print_on_exit |
    |  playing  |    pause    |  paused | print_on_enter | print_on_exit |
    |  playing  |     stop    | stopped | print_on_enter | print_on_exit |
    |  stopped  |  open_close |  opened | print_on_enter | print_on_exit |
    |  stopped  |     play    | playing | print_on_enter | print_on_exit |
    |  stopped  |     stop    | stopped | print_on_enter | print_on_exit |
    +-----------+-------------+---------+----------------+---------------+
    =============
    Current state => paused
    =============
    Exiting 'paused' due to 'play'
    Entered 'playing' due to 'play'
    +-----------+-------------+---------+----------------+---------------+
    |   Start   |    Event    |   End   |    On Enter    |    On Exit    |
    +-----------+-------------+---------+----------------+---------------+
    | closed[^] | cd_detected | stopped | print_on_enter | print_on_exit |
    | closed[^] |  open_close |  opened | print_on_enter | print_on_exit |
    |   opened  |  open_close |  closed | print_on_enter | print_on_exit |
    |   paused  |  open_close |  opened | print_on_enter | print_on_exit |
    |   paused  |     play    | playing | print_on_enter | print_on_exit |
    |   paused  |     stop    | stopped | print_on_enter | print_on_exit |
    |  @playing |  open_close |  opened | print_on_enter | print_on_exit |
    |  @playing |    pause    |  paused | print_on_enter | print_on_exit |
    |  @playing |     stop    | stopped | print_on_enter | print_on_exit |
    |  stopped  |  open_close |  opened | print_on_enter | print_on_exit |
    |  stopped  |     play    | playing | print_on_enter | print_on_exit |
    |  stopped  |     stop    | stopped | print_on_enter | print_on_exit |
    +-----------+-------------+---------+----------------+---------------+
    =============
    Current state => playing
    =============
    Exiting 'playing' due to 'stop'
    Entered 'stopped' due to 'stop'
    +-----------+-------------+---------+----------------+---------------+
    |   Start   |    Event    |   End   |    On Enter    |    On Exit    |
    +-----------+-------------+---------+----------------+---------------+
    | closed[^] | cd_detected | stopped | print_on_enter | print_on_exit |
    | closed[^] |  open_close |  opened | print_on_enter | print_on_exit |
    |   opened  |  open_close |  closed | print_on_enter | print_on_exit |
    |   paused  |  open_close |  opened | print_on_enter | print_on_exit |
    |   paused  |     play    | playing | print_on_enter | print_on_exit |
    |   paused  |     stop    | stopped | print_on_enter | print_on_exit |
    |  playing  |  open_close |  opened | print_on_enter | print_on_exit |
    |  playing  |    pause    |  paused | print_on_enter | print_on_exit |
    |  playing  |     stop    | stopped | print_on_enter | print_on_exit |
    |  @stopped |  open_close |  opened | print_on_enter | print_on_exit |
    |  @stopped |     play    | playing | print_on_enter | print_on_exit |
    |  @stopped |     stop    | stopped | print_on_enter | print_on_exit |
    +-----------+-------------+---------+----------------+---------------+
    =============
    Current state => stopped
    =============
    Exiting 'stopped' due to 'open_close'
    Entered 'opened' due to 'open_close'
    +-----------+-------------+---------+----------------+---------------+
    |   Start   |    Event    |   End   |    On Enter    |    On Exit    |
    +-----------+-------------+---------+----------------+---------------+
    | closed[^] | cd_detected | stopped | print_on_enter | print_on_exit |
    | closed[^] |  open_close |  opened | print_on_enter | print_on_exit |
    |  @opened  |  open_close |  closed | print_on_enter | print_on_exit |
    |   paused  |  open_close |  opened | print_on_enter | print_on_exit |
    |   paused  |     play    | playing | print_on_enter | print_on_exit |
    |   paused  |     stop    | stopped | print_on_enter | print_on_exit |
    |  playing  |  open_close |  opened | print_on_enter | print_on_exit |
    |  playing  |    pause    |  paused | print_on_enter | print_on_exit |
    |  playing  |     stop    | stopped | print_on_enter | print_on_exit |
    |  stopped  |  open_close |  opened | print_on_enter | print_on_exit |
    |  stopped  |     play    | playing | print_on_enter | print_on_exit |
    |  stopped  |     stop    | stopped | print_on_enter | print_on_exit |
    +-----------+-------------+---------+----------------+---------------+
    =============
    Current state => opened
    =============
    Exiting 'opened' due to 'open_close'
    Entered 'closed' due to 'open_close'
    +------------+-------------+---------+----------------+---------------+
    |   Start    |    Event    |   End   |    On Enter    |    On Exit    |
    +------------+-------------+---------+----------------+---------------+
    | @closed[^] | cd_detected | stopped | print_on_enter | print_on_exit |
    | @closed[^] |  open_close |  opened | print_on_enter | print_on_exit |
    |   opened   |  open_close |  closed | print_on_enter | print_on_exit |
    |   paused   |  open_close |  opened | print_on_enter | print_on_exit |
    |   paused   |     play    | playing | print_on_enter | print_on_exit |
    |   paused   |     stop    | stopped | print_on_enter | print_on_exit |
    |  playing   |  open_close |  opened | print_on_enter | print_on_exit |
    |  playing   |    pause    |  paused | print_on_enter | print_on_exit |
    |  playing   |     stop    | stopped | print_on_enter | print_on_exit |
    |  stopped   |  open_close |  opened | print_on_enter | print_on_exit |
    |  stopped   |     play    | playing | print_on_enter | print_on_exit |
    |  stopped   |     stop    | stopped | print_on_enter | print_on_exit |
    +------------+-------------+---------+----------------+---------------+
    =============
    Current state => closed
    =============

----------------------------------------------------------
Creating a complex CD-player machine (using a state-space)
----------------------------------------------------------

This example is equivalent to the prior one but creates a machine in
a more declarative manner. Instead of calling ``add_state``
and ``add_transition`` a explicit and declarative format can be used. For
example to create the same machine:

.. testcode::

    from automaton import machines


    def print_on_enter(new_state, triggered_event):
       print("Entered '%s' due to '%s'" % (new_state, triggered_event))


    def print_on_exit(old_state, triggered_event):
       print("Exiting '%s' due to '%s'" % (old_state, triggered_event))

    # This will contain all the states and transitions that our machine will
    # allow, the format is relatively simple and designed to be easy to use.
    state_space = [
        {
            'name': 'stopped',
            'next_states': {
                # On event 'play' transition to the 'playing' state.
                'play': 'playing',
                'open_close': 'opened',
                'stop': 'stopped',
            },
            'on_enter': print_on_enter,
            'on_exit': print_on_exit,
        },
        {
            'name': 'opened',
            'next_states': {
                'open_close': 'closed',
            },
            'on_enter': print_on_enter,
            'on_exit': print_on_exit,
        },
        {
            'name': 'closed',
            'next_states': {
                'open_close': 'opened',
                'cd_detected': 'stopped',
            },
            'on_enter': print_on_enter,
            'on_exit': print_on_exit,
        },
        {
            'name': 'playing',
            'next_states': {
                'stop': 'stopped',
                'pause': 'paused',
                'open_close': 'opened',
            },
            'on_enter': print_on_enter,
            'on_exit': print_on_exit,
        },
        {
            'name': 'paused',
            'next_states': {
                'play': 'playing',
                'stop': 'stopped',
                'open_close': 'opened',
            },
            'on_enter': print_on_enter,
            'on_exit': print_on_exit,
        },
    ]

    m = machines.FiniteMachine.build(state_space)
    m.default_start_state = 'closed'
    print(m.pformat())

**Expected output:**

.. testoutput::

    +-----------+-------------+---------+----------------+---------------+
    |   Start   |    Event    |   End   |    On Enter    |    On Exit    |
    +-----------+-------------+---------+----------------+---------------+
    | closed[^] | cd_detected | stopped | print_on_enter | print_on_exit |
    | closed[^] |  open_close |  opened | print_on_enter | print_on_exit |
    |   opened  |  open_close |  closed | print_on_enter | print_on_exit |
    |   paused  |  open_close |  opened | print_on_enter | print_on_exit |
    |   paused  |     play    | playing | print_on_enter | print_on_exit |
    |   paused  |     stop    | stopped | print_on_enter | print_on_exit |
    |  playing  |  open_close |  opened | print_on_enter | print_on_exit |
    |  playing  |    pause    |  paused | print_on_enter | print_on_exit |
    |  playing  |     stop    | stopped | print_on_enter | print_on_exit |
    |  stopped  |  open_close |  opened | print_on_enter | print_on_exit |
    |  stopped  |     play    | playing | print_on_enter | print_on_exit |
    |  stopped  |     stop    | stopped | print_on_enter | print_on_exit |
    +-----------+-------------+---------+----------------+---------------+

.. note::

    As can be seen the two tables from this example and the prior one are
    exactly the same.
