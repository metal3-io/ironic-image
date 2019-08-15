import six

from wsme.utils import _


class ClientSideError(RuntimeError):
    def __init__(self, msg=None, status_code=400):
        self.msg = msg
        self.code = status_code
        super(ClientSideError, self).__init__(self.faultstring)

    @property
    def faultstring(self):
        if self.msg is None:
            return str(self)
        elif isinstance(self.msg, six.text_type):
            return self.msg
        else:
            return six.u(self.msg)


class InvalidInput(ClientSideError):
    def __init__(self, fieldname, value, msg=''):
        self.fieldname = fieldname
        self.value = value
        super(InvalidInput, self).__init__(msg)

    @property
    def faultstring(self):
        return _(six.u(
            "Invalid input for field/attribute %s. Value: '%s'. %s")
        ) % (self.fieldname, self.value, self.msg)


class MissingArgument(ClientSideError):
    def __init__(self, argname, msg=''):
        self.argname = argname
        super(MissingArgument, self).__init__(msg)

    @property
    def faultstring(self):
        return _(six.u('Missing argument: "%s"%s')) % (
            self.argname, self.msg and ": " + self.msg or "")


class UnknownArgument(ClientSideError):
    def __init__(self, argname, msg=''):
        self.argname = argname
        super(UnknownArgument, self).__init__(msg)

    @property
    def faultstring(self):
        return _(six.u('Unknown argument: "%s"%s')) % (
            self.argname, self.msg and ": " + self.msg or "")


class UnknownFunction(ClientSideError):
    def __init__(self, name):
        self.name = name
        super(UnknownFunction, self).__init__()

    @property
    def faultstring(self):
        return _(six.u("Unknown function name: %s")) % (self.name)


class UnknownAttribute(ClientSideError):
    def __init__(self, fieldname, attributes, msg=''):
        self.fieldname = fieldname
        self.attributes = attributes
        self.msg = msg
        super(UnknownAttribute, self).__init__(self.msg)

    @property
    def faultstring(self):
        error = _("Unknown attribute for argument %(argn)s: %(attrs)s")
        if len(self.attributes) > 1:
            error = _("Unknown attributes for argument %(argn)s: %(attrs)s")
        str_attrs = ", ".join(self.attributes)
        return error % {'argn': self.fieldname, 'attrs': str_attrs}

    def add_fieldname(self, name):
        """Add a fieldname to concatenate the full name.

        Add a fieldname so that the whole hierarchy is displayed. Successive
        calls to this method will prepend ``name`` to the hierarchy of names.
        """
        if self.fieldname is not None:
            self.fieldname = "{}.{}".format(name, self.fieldname)
        else:
            self.fieldname = name
        super(UnknownAttribute, self).__init__(self.msg)
