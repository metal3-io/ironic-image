.. _usage:

=====================================================
 How to Use oslo.i18n in Your Application or Library
=====================================================

Installing
==========

At the command line::

    $ pip install oslo.i18n

.. _integration-module:

Creating an Integration Module
==============================

To use oslo.i18n in a project (e.g. myapp), you will need to create a
small integration module to hold an instance of
:class:`~oslo_i18n.TranslatorFactory` and references to
the marker functions the factory creates.

.. note::

   Libraries probably do not want to expose the new integration module
   as part of their public API, so rather than naming it
   ``myapp.i18n`` it should be called ``myapp._i18n`` to indicate that
   it is a private implementation detail, and not meant to be used
   outside of the library's own code.

.. note::

   Starting with the Pike series, OpenStack no longer supports log
   translation. It is not necessary to add translation instructions to
   new code, and the instructions can be removed from old code.  Refer
   to the email thread `understanding log domain change
   <http://lists.openstack.org/pipermail/openstack-dev/2017-March/thread.html#113365>`_
   on the openstack-dev mailing list for more details.

.. code-block:: python

    # myapp/_i18n.py

    import oslo_i18n

    DOMAIN = "myapp"

    _translators = oslo_i18n.TranslatorFactory(domain=DOMAIN)

    # The primary translation function using the well-known name "_"
    _ = _translators.primary

    # The contextual translation function using the name "_C"
    # requires oslo.i18n >=2.1.0
    _C = _translators.contextual_form

    # The plural translation function using the name "_P"
    # requires oslo.i18n >=2.1.0
    _P = _translators.plural_form

    def get_available_languages():
        return oslo_i18n.get_available_languages(DOMAIN)

.. TODO: Provide examples for _C and _P

Then, in the rest of your code, use the appropriate marker function
for each message:

.. code-block:: python

    from myapp._i18n import _

    # ...

    variable = "openstack"
    some_object.name_msg = _('my name is: %s') % variable

    # ...

    try:

        # ...

    except AnException1:

        # Log only, log messages are no longer translated
        LOG.exception('exception message')

    except AnException2:

        # Raise only
        raise RuntimeError(_('exception message'))

    else:

        # Log and Raise
        msg = _('Unexpected error message')
        LOG.exception(msg)
        raise RuntimeError(msg)

.. note::

   The import of multiple modules from _i18n on a single line is
   a valid exception to
   `OpenStack Style Guidelines <https://docs.openstack.org/hacking/latest/#imports>`_
   for import statements.


It is important to use the marker functions (e.g. _), rather than
the longer form of the name, because the tool that scans the source
code for translatable strings looks for the marker function names.

.. warning::

    The old method of installing a version of ``_()`` in the builtins
    namespace is deprecated. Modifying the global namespace affects
    libraries as well as the application, so it may interfere with
    proper message catalog lookups. Calls to
    :func:`gettextutils.install` should be replaced with the
    application or library integration module described here.


Handling hacking Objections to Imports
======================================

The `OpenStack Style Guidelines <https://docs.openstack.org/hacking/latest/#imports>`_
prefer importing modules and accessing names from those modules after
import, rather than importing the names directly. For example:

::

    # WRONG
    from foo import bar

    bar()

    # RIGHT

    import foo

    foo.bar()

The linting tool hacking_ will typically complain about importing
names from within modules. It is acceptable to bypass this for the
translation marker functions, because they must have specific names
and their use pattern is dictated by the message catalog extraction
tools rather than our style guidelines. To bypass the hacking check
for imports from this integration module, add an import exception to
``tox.ini``.

For example::

    # tox.ini
    [hacking]
    import_exceptions = myapp._i18n

.. _hacking: https://pypi.org/project/hacking

.. _lazy-translation:

Lazy Translation
================

Lazy translation delays converting a message string to the translated
form as long as possible, including possibly never if the message is
not logged or delivered to the user in some other way. It also
supports logging translated messages in multiple languages, by
configuring separate log handlers.

Lazy translation is implemented by returning a special object from the
translation function, instead of a unicode string. That special
message object supports some, but not all, string manipulation
APIs. For example, concatenation with addition is not supported, but
interpolation of variables is supported. Depending on how translated
strings are used in an application, these restrictions may mean that
lazy translation cannot be used, and so it is not enabled by default.

To enable lazy translation, call :func:`enable_lazy`.

::

    import oslo_i18n

    oslo_i18n.enable_lazy()

Translating Messages
====================

Use :func:`~oslo_i18n.translate` to translate strings to
a specific locale. :func:`translate` handles delayed translation and
strings that have already been translated immediately. It should be
used at the point where the locale to be used is known, which is often
just prior to the message being returned or a log message being
emitted.

::

    import oslo_i18n

    trans_msg = oslo_i18n.translate(msg, my_locale)

If a locale is not specified the default locale is used.

Available Languages
===================

Only the languages that have translations provided are available for
translation. To determine which languages are available the
:func:`~oslo_i18n.get_available_languages` is provided. The integration
module provides a domain defined specific function.

.. code-block:: python

    import myapp._i18n

    languages = myapp._i18n.get_available_languages()

.. seealso::

   * :doc:`guidelines`

Displaying translated messages
==============================

Several preparations are required to display translated messages in your
running application.

Preferred language
  You need to specify your preferred language through an environment variable.
  The preferred language can be specified by ``LANGUAGE``, ``LC_ALL``,
  ``LC_MESSAGES``, or ``LANGUAGE`` (A former one has a priority).

  ``oslo_i18n.translate()`` can be used to translate a string to override the
  preferred language.

  .. note::

     You need to use ``enable_lazy()`` to override the preferred language
     by using ``oslo_i18n.translate()``.

Locale directory
  Python ``gettext`` looks for binary ``mo`` files for the given domain
  using the path ``<localedir>/<language>/LC_MESSAGES/<domain>.mo``.
  The default locale directory varies on distributions,
  and it is ``/usr/share/locale`` in most cases.

  If you store message catalogs in a different location,
  you need to specify the location via an environment variable
  named ``<DOMAIN>_LOCALEDIR`` where ``<DOMAIN>`` is an upper-case
  domain name with replacing ``_`` and ``.`` with ``-``.
  For example, ``NEUTRON_LOCALEDIR`` for a domain ``neutron`` and
  ``OSLO_I18N_LOCALEDIR`` for a domain ``oslo_i18n``.

  .. note::

     When you specify locale directories via ``<DOMAIN>_LOCALEDIR``
     environment variables, you need to specify an environment variable per
     domain. More concretely, if your application using a domain ``myapp`
     uses oslo.policy, you need to specify both ``MYAPP_LOCALEDIR`` and
     ``OSLO_POLICY_LOCALEDIR`` to ensure that translation messages from
     both your application and oslo.policy are displayed.
