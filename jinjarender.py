#!/usr/bin/env python3

import os
import sys
import jinja2

rendered = jinja2.Template(sys.stdin.read()).render(env=os.environ)
sys.stdout.write(rendered)