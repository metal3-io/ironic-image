#!/bin/bash
builds="ironic-api ironic-conductor ironic-dbsync"
need_hooks="osprofiler keystoneauth1 ironic"

# imports needd because they are modules that are loaded.
hidden_imports="--hidden-import distutils --hidden-import eventlet.hubs.epolls --hidden-import eventlet.hubs.kqueue --hidden-import eventlet.hubs.selects --hidden-import osprofiler --hidden-import keystoneauth1.loading._plugins.identity.generic  --hidden-import keystoneauth1.loading._plugins.identity.v2 --hidden-import keystoneauth1.loading._plugins.identity.v3"
python_paths=""
additional_data="--add-data service-types.json:/os_service_types/data/"
additional_hooks="--additional-hooks-dir=."

# copy files we need to inject
cp /usr/lib/python2.7/site-packages/os_service_types/data/service-types.json .

for package in need_hooks;
do
    cat <<EOF >hook-$package.py
from PyInstaller.utils.hooks import copy_metadata

datas = copy_metadata('$package')
EOF

done

for file in $builds;
do
    pyinstaller -F /usr/bin/$file $python_paths $hidden_imports $additional_hooks $additional_data
done
