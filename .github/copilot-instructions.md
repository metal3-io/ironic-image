# Metal3 Ironic Container Image - AI Coding Assistant Instructions

## Project Overview

This repository builds the container images used by Metal3 to run OpenStack
Ironic for bare metal provisioning. The image includes multiple entry points to
run different services (Ironic API/Conductor, dnsmasq, httpd, log watcher) that
work together to provision bare metal hosts. Base images: CentOS Stream 9 and
CentOS Stream 10.

## Architecture

### Container Entry Points

The image provides multiple entry points sharing the same base but running
different services:

1. **`runironic`** (default) - Runs Ironic API and Conductor

   - Manages bare metal node provisioning
   - Communicates with BMCs via IPMI, Redfish, etc.
   - Coordinates PXE boot, inspection, deployment

2. **`rundnsmasq`** - DHCP/PXE server
   - Provides DHCP addresses to booting hosts
   - Serves TFTP for PXE boot files
   - Lightweight integrated TFTP server

3. **`runhttpd`** - Apache web server
   - Serves IPA (Ironic Python Agent) images via HTTP
   - Serves final deployment images (qcow2)
   - Provides inspection/deployment artifacts

4. **`runlogwatch`** - Log monitoring
   - Watches for IPA ramdisk logs
   - Prints logs for debugging
   - Cleans up log files

### Shared Storage Requirements

All containers require a shared mount point at `/shared`:

```text
/shared/
  ├── html/

  │   └── images/
  │       ├── ironic-python-agent.kernel
  │       ├── ironic-python-agent.initramfs
  │       └── <deployment-image>.qcow2
  ├── tftpboot/          # PXE boot files
  └── ironic_prometheus_exporter/
```

## Key Configuration

### Environment Variables

**Network Configuration:**

- `PROVISIONING_INTERFACE` - Interface for Ironic/DHCP (default:
  `provisioning`)

- `PROVISIONING_MACS` - MACs to calculate provisioning interface
- `PROVISIONING_IP` - Specific IP to use (auto-calculated if not set)
- `HTTP_PORT` - HTTP server port (default: `80`)
- `GATEWAY_IP` - Gateway for DHCP
- `DNS_IP` - DNS server for DHCP

**DHCP Configuration:**

- `DHCP_RANGE` - DHCP range, e.g., `172.22.0.10,172.22.0.100`

- `DHCP_HOSTS` - Known MAC addresses (`;` separated)
- `DHCP_IGNORE` - Tags to ignore (e.g., `tag:!known` for unknown hosts)
- `DNSMASQ_EXCEPT_INTERFACE` - Exclude interfaces (default: `lo`)

**Ironic Configuration:**

- `OS_<section>__<name>=<value>` - Set arbitrary Ironic config options
  (overrides templates)

- `IRONIC_KERNEL_PARAMS` - Additional kernel parameters for IPA
- `IRONIC_RAMDISK_SSH_KEY` - SSH public key for IPA access
- `IRONIC_IPA_COLLECTORS` - Inspection collectors (default: `default,logs`)
- `IRONIC_CONDUCTOR_HOST` - Conductor hostname (defaults to provisioning IP)
- `IRONIC_EXTERNAL_IP` - External IP if different from provisioning IP
- `IRONIC_EXTERNAL_CALLBACK_URL` - Override callback URL
- `IRONIC_EXTERNAL_HTTP_URL` - Override HTTP URL
- `IRONIC_ENABLE_VLAN_INTERFACES` - Enable VLAN interfaces on agent

**HTTP Server:**

- `HTTPD_SERVE_NODE_IMAGES` - Serve images from `/shared/html/images`
  (default: `true`)

- `HTTPD_ENABLE_SENDFILE` - Enable Apache SendFile (default: `false`)

## Development Workflows

### Building the Image

```bash
# Build with podman (default)
make build

# Build with docker
CONTAINER_ENGINE=docker make build

# Build directly
podman build -f Dockerfile -t quay.io/metal3-io/ironic:dev .
```

### Image Structure

**Build Process:**

1. Base image: CentOS Stream (9 or 10)

2. Install system packages from `main-packages-list.txt`
3. Install Ironic packages from `ironic-packages-list`
4. Run `prepare-image.sh` - Sets up Ironic, dnsmasq, httpd configs
5. Run `prepare-efi.sh` - Prepares EFI boot files
6. Configure non-root execution via `configure-nonroot.sh`
7. Install entry point scripts from `scripts/`

**Key Scripts:**

- `scripts/runironic.sh` - Ironic entry point

- `scripts/rundnsmasq.sh` - dnsmasq entry point
- `scripts/runhttpd.sh` - Apache entry point
- `scripts/runlogwatch.sh` - Log watcher entry point

### Local Testing

```bash
# Run Ironic locally (requires shared volume)
podman run -d --net=host \
  -v /opt/metal3-dev-env/ironic:/shared:z \
  -e PROVISIONING_INTERFACE=ironicendpoint \
  quay.io/metal3-io/ironic:latest

# Run dnsmasq
podman run -d --net=host --privileged \
  -v /opt/metal3-dev-env/ironic:/shared:z \
  -e PROVISIONING_INTERFACE=ironicendpoint \
  -e DHCP_RANGE=172.22.0.10,172.22.0.100 \
  --entrypoint /bin/rundnsmasq \
  quay.io/metal3-io/ironic:latest

# Run httpd
podman run -d --net=host \
  -v /opt/metal3-dev-env/ironic:/shared:z \
  --entrypoint /bin/runhttpd \
  quay.io/metal3-io/ironic:latest
```

### Configuration Templates

Ironic configuration is rendered from templates in `ironic-config/`:

- `ironic.conf.j2` - Main Ironic configuration

- Templates use environment variables for runtime configuration
- `OS_` prefix variables override template settings

## Code Patterns and Conventions

### Entry Point Scripts

All entry point scripts follow similar patterns:

```bash
#!/bin/bash

set -euxo pipefail

# Wait for shared storage to be ready
wait-for-shared-storage

# Render configuration from templates
render-config

# Start the service
exec <service-command>
```

### Configuration Rendering

Configuration uses `oslo-config-generator` and Jinja2 templates:

1. Templates in `ironic-config/` define structure

2. Environment variables provide values
3. Scripts render final configs at runtime
4. `OS_` variables override template defaults

### Package Management

**`main-packages-list.txt`:**

- System-level packages (httpd, dnsmasq, python3, etc.)

- One package per line
- Comments with `#`

**`ironic-packages-list`:**

- Python packages for Ironic

- Installed via pip
- Includes Ironic, IPA, and dependencies

**`upper-constraints.txt`:**

- Pin Python package versions

- Based on OpenStack release constraints
- Updated periodically via renovate

### Non-root Execution

`configure-nonroot.sh` sets up the image to run as non-root:

- Creates `ironic` user/group

- Sets proper permissions on shared directories
- Configures sudo for specific commands
- Security best practice for Kubernetes

## Integration Points

### With Baremetal Operator

BMO deploys Ironic as pods in Kubernetes:

- Uses `baremetal-operator/ironic-deployment/` manifests

- Deploys Ironic, dnsmasq, httpd as separate containers
- Shares volume for `/shared` across containers
- BMO controller communicates with Ironic API

### With IPA (Ironic Python Agent)

Ironic deploys IPA to bare metal hosts:

- Serves IPA kernel/initramfs via HTTP

- IPA boots via PXE (dnsmasq provides TFTP)
- IPA performs inspection, cleaning, deployment
- IPA reports back to Ironic via callbacks

### Network Architecture

```text
Bare Metal Host
      ↓ (PXE boot)

   dnsmasq (DHCP/TFTP)
      ↓
   httpd (serves IPA images)
      ↓ (downloads IPA)
Bare Metal Host boots IPA
      ↓ (API calls)
   Ironic API/Conductor
      ↓ (manages provisioning)
Updates BareMetalHost status
```

## Key Files Reference

- `Dockerfile` - Main image build definition
- `Makefile` - Build commands
- `prepare-image.sh` - Image setup script
- `prepare-efi.sh` - EFI boot configuration
- `configure-nonroot.sh` - Non-root user setup
- `scripts/*` - Entry point scripts for each service
- `ironic-config/` - Jinja2 templates for Ironic config
- `main-packages-list.txt` - System packages
- `ironic-packages-list` - Python packages
- `upper-constraints.txt` - Python version pins

## Common Workflows

### Updating Ironic Version

1. Update `ironic-packages-list` with new version constraints
2. Update `upper-constraints.txt` (usually from OpenStack release)
3. Test build locally
4. Open PR - automated builds on quay.io trigger
5. Test with BMO integration

### Adding Configuration Options

1. Add environment variable to `README.md` documentation
2. Update Jinja2 template in `ironic-config/` to use variable
3. Update entry point script if needed to set/export variable
4. Test configuration renders correctly

### Debugging Container Issues

```bash
# Run container interactively
podman run -it --rm --entrypoint /bin/bash quay.io/metal3-io/ironic:latest

# Check rendered configuration
podman exec <container-id> cat /etc/ironic/ironic.conf

# Check service logs
podman logs <container-id>

# Check Ironic API status
curl http://<ironic-ip>:6385/v1/nodes
```

## Common Pitfalls

1. **Shared Storage Missing** - All containers need `/shared` volume mounted
2. **Permissions Issues** - Ensure shared volume has proper permissions for
   `ironic` user (UID 997)
3. **Network Conflicts** - `PROVISIONING_INTERFACE` must be correct for
   network topology
4. **DHCP Range** - Must not conflict with other DHCP servers on network
5. **Image Paths** - IPA kernel/initramfs must be in `/shared/html/images/`
6. **Port Conflicts** - HTTP_PORT, Ironic API port (6385), TFTP (69) must be
   available
7. **EFI Boot** - Some hardware requires specific EFI file locations, check
   `prepare-efi.sh`

## CI/CD and Releases

- Automated builds on quay.io on push to main

- Tagged releases trigger versioned image builds
- Tested via metal3-dev-env and BMO e2e tests
- Integration testing with full Metal3 stack

## Multi-Service Deployment Pattern

In Kubernetes (via BMO ironic-deployment):

```yaml
# Ironic pod
- container: ironic
  image: quay.io/metal3-io/ironic
  # Uses default runironic entry point

- container: ironic-dnsmasq
  image: quay.io/metal3-io/ironic
  command: ["/bin/rundnsmasq"]

- container: ironic-httpd
  image: quay.io/metal3-io/ironic
  command: ["/bin/runhttpd"]

- container: ironic-log-watch
  image: quay.io/metal3-io/ironic
  command: ["/bin/runlogwatch"]

# All share same /shared volume
```

## Version Compatibility

- Tracks OpenStack Ironic releases (Antelope, Bobcat, Caracal, etc.)
- Compatible with BMO versions expecting same Ironic API version
- IPA version should match Ironic version (both from same OpenStack release)
- Python 3.9+ required
