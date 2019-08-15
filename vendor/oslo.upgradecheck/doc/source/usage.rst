=======
 Usage
=======

See the module ``oslo_upgradecheck.__main__`` for an example of how to use this
project.

Each consuming project should create a class that inherits from
:class:`oslo_upgradecheck.upgradecheck.UpgradeCommands` and implement check
methods on it. Those check methods should then be added to the
``_upgrade_checks`` tuple so they will be run when the
:meth:`oslo_upgradecheck.upgradecheck.UpgradeCommands.check` method is
called. For example::

    from oslo_upgradecheck import upgradecheck

    class ProjectSpecificUpgradeCommands(upgradecheck.UpgradeCommands):
        def an_upgrade_check(self):
            if everything_is_awesome():
                return upgradecheck.Result(
                    upgradecheck.Code.SUCCESS, 'Success details')
            else:
                return upgradecheck.Result(
                    upgradecheck.Code.FAILURE, 'Failure details')

        _upgrade_checks = (('Awesome upgrade check', an_upgrade_check))

oslo.upgradecheck also includes a basic implementation of command line argument
handling that can be used to provide the minimum processing needed to implement
a ``$SERVICE-status upgrade check`` command. To make use of it, write a method
that creates an instance of the class created above, then pass that class's
``check`` function into :func:`oslo_upgradecheck.upgradecheck.main`. The
project's ConfigOpts instance must also be passed. In most projects this will
just be cfg.CONF. For example::

    from oslo_config import cfg

    def main():
        return upgradecheck.main(
            conf=cfg.CONF,
            project='myprojectname',
            upgrade_command=ProjectSpecificUpgradeCommands(),
        )

The entry point for the ``$SERVICE-status`` command should then point at this
function.

Alternatively, if a project has its own CLI code that it would prefer to reuse,
it simply needs to ensure that the ``inst.check`` method is called when the
``upgrade check`` parameters are passed to the ``$SERVICE-status`` command.

Example
-------

The following is a fully functional example of implementing a check command:

.. literalinclude:: main.py
