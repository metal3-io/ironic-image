#!/bin/bash
MIRROR="https://github.com"
function gc () {
git clone $MIRROR/$2 -b $3 $1
pip install $1
}

# repos
gc pyinstaller pyinstaller/pyinstaller -b v3.5
