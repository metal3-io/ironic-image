#!/bin/bash
MIRROR="https://github.com"

function install_rpm () {
    yum install $1
}

function install_git () {
    git clone $MIRROR/$2 -b $3 $1
    cd $1
    python setup.py install
    cd ..
}


# Note: versions are train.  We should try stein...

install_rpm python36-pytz

# epel? :(
install_rpm python36-pbr
# pbr!=2.1.0,>=2.0.0 # Apache-2.0

# epel? :(
install_rpm python36-sqlalchemy
# SQLAlchemy!=1.1.5,!=1.1.6,!=1.1.7,!=1.1.8,>=1.0.10 # MIT

# epel? :(
install_rpm alembic
install_rpm alembic-libs
# TODO https://files.pythonhosted.org/packages/7b/8b/0c98c378d93165d9809193f274c3c6e2151120d955b752419c7d43e4d857/alembic-1.0.11.tar.gz
# alembic>=0.8.10 # MIT

install_git automaton openstack/automaton 1.16.0
#automaton>=1.9.0 # Apache-2.0

install_git eventlet eventlet/eventlet 1.16.0
# eventlet!=0.18.3,!=0.20.1,>=0.18.2 # MIT

# latest...
install_git webob Pylons/webob 1.8.4
#WebOb>=1.7.1 # MIT

install_git retrying rholder/retrying v1.3.3
#retrying!=1.3.0,>=1.2.3 # Apache-2.0

install_git jsonschema Julian/jsonschema v3.0.0
# epel has 2.5.1
#jsonschema>=2.6.0 # MIT

install_git psutil giampaolo/psutil release-5.6.3
# psutil 2.2.1-5 is epel7 :(::
# psutil 5.6.3 is latest
# psutil>=3.2.2 # BSD

# unused?!?!?!? No referenes.
#  pysendfile>=2.0.0;sys_platform!='win32' # MIT

install_git pecan pecan/pecan 1.3.3
# pecan!=1.0.2,!=1.0.3,!=1.0.4,!=1.2,>=1.0.0 # BSD

install_git requests psf/requests v2.22.0
#requests>=2.14.2 # Apache-2.0

install_rpm rfc3986
#rfc3986>=0.3.1 # Apache-2.0

install_rpm python36-six
#six>=1.10.0 # MIT

install_git jsonpatch stefankoegl/python-json-patch v1.24
#jsonpatch!=1.20,>=1.16 # BSD

install_git wsme openstack/wsme 0.9.3
#WSME>=0.9.3 # MIT

# TODO https://files.pythonhosted.org/packages/93/ea/d884a06f8c7f9b7afbc8138b762e80479fb17aedbbe2b06515a12de9378d/Jinja2-2.10.1.tar.gz
# ugh, 2.8-9.x is on epel...
Jinja2>=2.10 # BSD License (3 clause)



oslo.concurrency>=3.26.0 # Apache-2.0
oslo.config>=5.2.0 # Apache-2.0
oslo.context>=2.19.2 # Apache-2.0
oslo.db>=4.27.0 # Apache-2.0
oslo.rootwrap>=5.8.0 # Apache-2.0
oslo.i18n>=3.15.3 # Apache-2.0
oslo.log>=3.36.0 # Apache-2.0
oslo.middleware>=3.31.0 # Apache-2.0
oslo.policy>=1.30.0 # Apache-2.0
oslo.reports>=1.18.0 # Apache-2.0
oslo.serialization!=2.19.1,>=2.18.0 # Apache-2.0
oslo.service!=1.28.1,>=1.24.0 # Apache-2.0
oslo.upgradecheck>=0.1.0 # Apache-2.0
oslo.utils>=3.33.0 # Apache-2.0
osprofiler>=1.5.0 # Apache-2.0
os-traits>=0.4.0 # Apache-2.0
keystonemiddleware>=4.17.0 # Apache-2.0
oslo.messaging>=5.29.0 # Apache-2.0
oslo.versionedobjects>=1.31.2 # Apache-2.0




# openstack
install_git futurist openstack/futurist 1.2.0

#futurist>=1.2.0 # Apache-2.0
install_git tooz openstack/tooz 1.58.0
# tooz>=1.58.0 # Apache-2.0

install_git stevedore openstack/stevedore 1.20.0
# stevedore>=1.20.0 # Apache-2.0

# realsitically latest needed... though might not be actively invoked.
install_git keystoneauth1 openstack/keystoneauth 3.11.0
install_git openstacksdk openstack/openstacksdk 0.31.2


python-cinderclient!=4.0.0,>=3.3.0 # Apache-2.0
python-neutronclient>=6.7.0 # Apache-2.0
python-glanceclient>=2.8.0 # Apache-2.0
python-swiftclient>=3.2.0 # Apache-2.0


install_git python-swiftclient openstack/python-swiftclient 
install_git ironic-lib openstack/ironic-lib 2.17.1
install_git ironic openstack/ironic master
