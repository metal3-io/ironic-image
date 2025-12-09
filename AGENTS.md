# Metal3 Ironic Image - AI Agent Instructions

Instructions for AI coding agents. For project overview, see [README.md](README.md).
For contribution guidelines, see [CONTRIBUTING.md](CONTRIBUTING.md).

## Repository Structure

| Directory | Purpose |
|-----------|---------|
| `scripts/` | Entry point scripts (runironic, rundnsmasq, runhttpd, etc.) |
| `ironic-config/` | Jinja2 templates for Ironic/dnsmasq/httpd configuration |
| `hack/` | CI scripts (shellcheck, markdownlint) |

## Key Files

| File | Purpose |
|------|---------|
| `Dockerfile` | Main image build definition |
| `prepare-image.sh` | Image setup (Ironic, dnsmasq, httpd configs) |
| `configure-nonroot.sh` | Non-root user setup for security |
| `ironic-packages-list` | Python packages (Ironic, IPA, dependencies) |
| `upper-constraints.txt` | Python version pins (from [OpenStack requirements](https://opendev.org/openstack/requirements/src/branch/master/upper-constraints.txt)) |

## Testing Standards

CI uses GitHub Actions (`.github/workflows/`). Run locally before PRs:

| Command | Purpose |
|---------|---------|
| `make build` | Build container image |
| `./hack/shellcheck.sh` | Shell script linting |
| `./hack/markdownlint.sh` | Markdown linting |

## Code Conventions

- **Shell**: Use `set -euxo pipefail` in scripts
- **Jinja2**: Templates in `ironic-config/` render at container runtime

## Key Workflows

### Modifying Entry Point Scripts

1. Edit script in `scripts/`
1. Run `./hack/shellcheck.sh`
1. Test with `make build` and manual container run

### Modifying Configuration Templates

1. Edit Jinja2 template in `ironic-config/`
1. Document new environment variables in `README.md`
1. Test configuration renders correctly at runtime

### Updating Ironic Version

1. Update `ironic-packages-list` with new version
1. Update `upper-constraints.txt` (from OpenStack release)
1. Run `make build` and test

## Code Review Guidelines

When reviewing pull requests:

1. **Security** - No hardcoded credentials, proper file permissions
1. **Consistency** - Match existing shell script patterns
1. **Breaking changes** - Flag environment variable or mount changes

Focus on: `scripts/`, `ironic-config/`, `Dockerfile`, `prepare-*.sh`.

## AI Agent Guidelines

1. Read `README.md` for environment variables and configuration
1. Make minimal, surgical edits
1. Run `./hack/shellcheck.sh` and `./hack/markdownlint.sh` before committing
1. Document new environment variables in `README.md`

## Integration

This image is deployed by
[Ironic Standalone Operator (IrSO)](https://github.com/metal3-io/ironic-standalone-operator).
IrSO manages the Kubernetes manifests and container configuration.

**Read-only root filesystem:** Supports read-only root with writable mounts
at `/conf`, `/data`, `/tmp`, and `/shared`.

## Related Documentation

- [Baremetal Operator](https://github.com/metal3-io/baremetal-operator)
- [Metal3 Book](https://book.metal3.io/ironic/introduction)
