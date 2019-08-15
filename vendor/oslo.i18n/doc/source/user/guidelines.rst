=================================
 Guidelines for Use In OpenStack
=================================

The OpenStack I18N team has a limited capacity to translate messages,
so we want to make their work as effective as possible by identifying
the most useful text for them to translate.  All text messages *the
user sees* via exceptions or API calls should be marked for
translation. However, some exceptions are used internally to signal
error conditions between modules and are not intended to be presented
to the user. Those do not need to be translated.

.. seealso::

   * :ref:`usage`
   * :ref:`api`

Gettext Contextual Form and Plural Form
=======================================

Sometimes under different contexts, the same word should be
translated into different phrases using
:py:attr:`TranslatorFactory.contextual_form <oslo_i18n.TranslatorFactory.contextual_form>`.

And recommend the following code to use contextual form::

  # The contextual translation function using the name "_C"
  _C = _translators.contextual_form

  ...
  msg = _C('context', 'string')

In some languages, sometimes the translated strings are different
with different item counts using
:py:attr:`TranslatorFactory.plural_form <oslo_i18n.TranslatorFactory.plural_form>`

And recommend the following code to use plural form::

  # The plural translation function using the name "_P"
  _P = _translators.plural_form

  ...
  msg = _P('single', 'plural', count)

The contextual form and plural form are used only when needed.
By default, the translation should use the ``_()``.

.. note::
   These two functions were only available in oslo.i18n >= 2.1.0.

Log Translation
===============

.. note::

   Starting with the Pike series, OpenStack no longer supports log
   translation. It is not necessary to add translation instructions to
   new code, and the instructions can be removed from old code.  Refer
   to the email thread `understanding log domain change
   <http://lists.openstack.org/pipermail/openstack-dev/2017-March/thread.html#113365>`_
   on the openstack-dev mailing list for more details.

OpenStack supports translating some log levels using separate message
catalogs, and so has separate marker functions. These well-known names
are used by the build system jobs that extract the messages from the
source code and pass it to the translation tool.

========== ==========
 Level      Function
========== ==========
 INFO       ``_LI()``
 WARNING    ``_LW()``
 ERROR      ``_LE()``
 CRITICAL   ``_LC()``
========== ==========

.. note::
   * Debug level log messages are not translated.
   * LOG.exception creates an ERROR level log, so when a marker function is
     used (see below) ``_LE()`` should be used.


Using a Marker Function
=======================
The marker functions are used to mark the translatable strings in the
code.  The strings are extracted into catalogs using a tool that
looks for these specific markers, so the function argument must just
be a string.

For example: **do not do this**::

  # WRONG
  msg = _(variable_containing_msg)
  w_msg = _LW(variable_warning_msg)

Instead, use this style::

  # RIGHT
  msg = _('My message.')
  w_msg = _LW('My warning message')


Choosing a Marker Function
==========================

The purpose of the different marker functions is to separate the
translatable messages into different catalogs, which the translation
teams can prioritize translating. It is important to choose the right
marker function, to ensure that strings the user sees will be
translated and to help the translation team manage their work load.

Everything marked with ``_()`` will be translated. Prioritizing the
catalogs created from strings marked with the log marker functions is
up to the individual translation teams and their users, but it is
expected that they will work on critical and error messages before
warning or info.

``_()`` is preferred for any user facing message, even if it is also
going to a log file.  This ensures that the translated version of the
message will be available to the user.

The log marker functions (``_LI()``, ``_LW()``, ``_LE()``, and ``_LC()``)
must only be used when the message is only sent directly to the log.
Anytime that the message will be passed outside of the current context
(for example as part of an exception) the ``_()`` marker function
must be used.

A common pattern is to define a single message object and use it more
than once, for the log call and the exception.  In that case, ``_()``
must be used because the message is going to appear in an exception that
may be presented to the user.

For example, **do not do this**::

  # WRONG
  msg = _LE('There was an error.')
  LOG.exception(msg)
  raise LocalExceptionClass(msg)

Instead, use this style::

  # RIGHT
  msg = _('There was an error.')
  LOG.exception(msg)
  raise LocalExceptionClass(msg)

Except in the case above, ``_()`` should not be used for translating
log messages. This avoids having the same string in two message
catalogs, possibly translated differently by two different
translators.  The log message will translate properly because when
the message is not found in the log specific catalog the ``_()``
catalog will be used.

If a common message is not being used, they should each be treated
separately with respect to choosing a marker function.

For example, **do not do this**::

  # WRONG
  LOG.exception(_('There was an error.'))
  raise LocalExceptionClass(_('An error occurred.'))

Instead, use this style::

  # RIGHT
  LOG.exception(_LE('There was an error.'))
  raise LocalExceptionClass(_('An error occurred.'))


Adding Variables to Translated Messages
=======================================

Translated messages should not be combined with other literal strings
to create partially translated messages.  For example, **do not do
this**::

  # WRONG
  raise ValueError(_('some message') + ': variable=%s' % variable)

Instead, use this style::

  # RIGHT
  raise ValueError(_('some message: variable=%s') % variable)

Including the variable reference inside the translated message allows
the translator to take into account grammar rules, differences in
left-right vs. right-left rendering, and other factors to make the
translated message more useful to the end user.

Any message with more than one variable should use named interpolation
instead of positional, to allow translators to move the variables
around in the string to account for differences in grammar and writing
direction.

For example, **do not do this**::

  # WRONG
  raise ValueError(_('some message: v1=%s v2=%s') % (v1, v2))

Instead, use this style::

  # RIGHT
  raise ValueError(_('some message: v1=%(v1)s v2=%(v2)s') % {'v1': v1, 'v2': v2})


Adding Variables to Log Messages
================================

String interpolation should be delayed to be handled by the logging
code, rather than being done at the point of the logging call.  For
example, **do not do this**::

  # WRONG
  LOG.info(_LI('some message: variable=%s') % variable)

Instead, use this style::

  # RIGHT
  LOG.info(_LI('some message: variable=%s'), variable)

This allows the logging package to skip creating the formatted log
message if the message is not going to be emitted because of the
current log level.

Avoid Forcing the Translation of Translatable Variables
=======================================================

Translation can also be delayed for variables that potentially contain
translatable objects such as exceptions.

Whenever possible translation should not be forced by use of :func:`str`,
:func:`unicode`, or :func:`six.text_type` on a message being used with
a format string.

For example, **do not do this**::

  # WRONG
  LOG.info(_LI('some message: exception=%s'), six.text_type(exc))

Instead, use this style::

  # RIGHT
  LOG.info(_LI('some message: exception=%s'), exc)

This allows the translation of the translatable replacement text to be
delayed until the message is translated.
