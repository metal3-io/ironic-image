"""
Produce a tox.ini file from a template config file.

The template config file is a standard tox.ini file with additional sections.
Theses sections will be combined to create new testenv: sections if they do
not exists yet.

See REAME.rst for more detail.
"""

import itertools
import collections
import optparse

try:
    from configparser import ConfigParser
except:
    from ConfigParser import ConfigParser  # noqa


parser = optparse.OptionParser(epilog=__doc__)
parser.add_option('-i', '--input', dest='input',
                  default='tox-tmpl.ini', metavar='FILE')
parser.add_option('-o', '--output', dest='output',
                  default='tox.ini', metavar='FILE')


class AxisItem(object):
    def __init__(self, axis, name, config):
        self.axis = axis
        self.isdefault = name[-1] == '*'
        self.name = name[:-1] if self.isdefault else name
        self.load(config)

    def load(self, config):
        sectionname = 'axis:%s:%s' % (self.axis.name, self.name)
        if config.has_section(sectionname):
            self.options = collections.OrderedDict(config.items(sectionname))
        else:
            self.options = collections.OrderedDict()

        for name, value in self.axis.defaults.items():
            if name not in self.options:
                self.options[name] = value


class Axis(object):
    def __init__(self, name, config):
        self.name = name
        self.load(config)

    def load(self, config):
        self.items = collections.OrderedDict()
        values = config.get('axes', self.name).split(',')
        if config.has_section('axis:%s' % self.name):
            self.defaults = collections.OrderedDict(
                config.items('axis:%s' % self.name)
            )
        else:
            self.defaults = {}
        for value in values:
            self.items[value.strip('*')] = AxisItem(self, value, config)


def render(incfg):
    axes = collections.OrderedDict()

    if incfg.has_section('axes'):
        for axis in incfg.options('axes'):
            axes[axis] = Axis(axis, incfg)

    out = ConfigParser()
    for section in incfg.sections():
        if section == 'axes' or section.startswith('axis:'):
            continue
        out.add_section(section)
        for name, value in incfg.items(section):
            out.set(section, name, value)

    for combination in itertools.product(
            *[axis.items.keys() for axis in axes.values()]):
        options = collections.OrderedDict()

        section_name = (
            'testenv:' + '-'.join([item for item in combination if item])
        )
        section_alt_name = (
            'testenv:' + '-'.join([
                itemname
                for axis, itemname in zip(axes.values(), combination)
                if itemname and not axis.items[itemname].isdefault
            ])
        )
        if section_alt_name == section_name:
            section_alt_name = None

        axes_items = [
            '%s:%s' % (axis, itemname)
            for axis, itemname in zip(axes, combination)
        ]

        for axis, itemname in zip(axes.values(), combination):
            axis_options = axis.items[itemname].options
            if 'constraints' in axis_options:
                constraints = axis_options['constraints'].split('\n')
                for c in constraints:
                    if c.startswith('!') and c[1:] in axes_items:
                        continue
            for name, value in axis_options.items():
                if name in options:
                    options[name] += value
                else:
                    options[name] = value

        constraints = options.pop('constraints', '').split('\n')
        neg_constraints = [c[1:] for c in constraints if c and c[0] == '!']
        if not set(neg_constraints).isdisjoint(axes_items):
            continue

        if not out.has_section(section_name):
            out.add_section(section_name)

        if (section_alt_name and not out.has_section(section_alt_name)):
            out.add_section(section_alt_name)

        for name, value in reversed(options.items()):
            if not out.has_option(section_name, name):
                out.set(section_name, name, value)
            if section_alt_name and not out.has_option(section_alt_name, name):
                out.set(section_alt_name, name, value)

    return out


def main():
    options, args = parser.parse_args()
    tmpl = ConfigParser()
    tmpl.read(options.input)
    with open(options.output, 'wb') as outfile:
        render(tmpl).write(outfile)


if __name__ == '__main__':
    main()
