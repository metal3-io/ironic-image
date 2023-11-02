# Container Image Ironic Client

This repository contains the build instructions
for a container image of the [Python Ironic Client][PIC].

This container can be used to debug the Ironic component of Metal³.

Once a baremetal-operator-ironic container is running one can start the container
as a debug container using the following command line:

```sh
kubectl debug -it -n baremetal-operator-system $(kubectl get -n baremetal-operator-system pods -o name|grep ironic) --image=ironicclient:0.0.1 --target ironic
```

This opens a shell to the debug container.

The `baremetal` command can be used to access the
[Python Ironic Client Standalone CLI][PICSCLI] e.g. one can use

```sh
baremetal node list
```

to list all nodes and their states registered in Ironic.


## Implementation details

The container image uses bash and starts it as login shell to source the profile
files in `/etc/profile.d`. The `ironic.sh` in `/etc/profile.d` sets the
following environment variables:

* `OS_AUTH_TYPE`: static string "none" as ironic is running in standalone mode
* `OS_ENDPOINT`: the ironic endpoint found in `/etc/ironic/ironic.conf` in the baremetal-ironic-container
* `REQUESTS_CA_BUNDLE`: pointing to `/certs/ca/ironic-inspector/ca.crt` in the baremetal-ironic-container

The environment variables are used by the Ironic CLI client to communicate with
the ironic API endpoint.

In the debug container the filesystem of the ironic container can be found in
`/proc/1/root`.

[PIC]: https://docs.openstack.org/python-ironicclient/latest/
[PICSCLI]: https://docs.openstack.org/python-ironicclient/latest/cli/standalone.html
