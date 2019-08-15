from wsme.exc import MissingArgument


def check_arguments(funcdef, args, kw):
    """Check if some arguments are missing"""
    assert len(args) == 0
    for arg in funcdef.arguments:
        if arg.mandatory and arg.name not in kw:
            raise MissingArgument(arg.name)
