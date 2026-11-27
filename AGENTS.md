# Metal3 Ironic Image

Container image that runs OpenStack Ironic and its helpers (dnsmasq, httpd,
ironic-networking, log watcher) for Metal3. One image, many entry points in
`scripts/`. Usage and every runtime variable: [README.md](README.md).
Contribution rules: [CONTRIBUTING.md](CONTRIBUTING.md) and the
[Metal3 community guide](https://github.com/metal3-io/community/blob/main/CONTRIBUTING.md).

This file holds only what you cannot cheaply infer from the code. Where it
disagrees with the code or the Dockerfile, trust those and report the
mismatch.

## AI-assisted contributions

Metal3 follows the CNCF and
[Linux Foundation generative AI policy](https://www.linuxfoundation.org/legal/generative-ai).

- AI is a tool. The human who opens a PR is its author and is responsible
  for every line of it, including licensing and third-party content.
- Review is a conversation between humans. A PR where an agent or bot
  answers reviewers will be closed. Agents may draft changes; the
  contributor reads them, understands them, and replies personally.

- Keep changes surgical. The smallest complete change that solves the
  stated problem wins. Every added file, function, flag, dependency or
  test helper must trace to that problem; anything that does not is
  bloat and gets removed. Prefer reusing existing code over new code.
  Report unrelated findings instead of fixing them in the same PR.

## Repository map

- Build time: `Dockerfile` (multi-stage), `build-wheels.sh`,
  `prepare-image.sh`, `patch-image.sh`, `configure-nonroot.sh`, package
  lists (`main-packages-list*.txt`, `ironic-packages-list`,
  `ironic-deps-list`). `ironic-packages-list` is a Jinja2 template rendered
  by `build-wheels.sh` from the `*_SOURCE` build args.
- Run time: `scripts/run*` entry points and their `*-common.sh` helpers.
  At container start they render the `ironic-config/*.j2` templates baked
  into the image into `/conf` (`CUSTOM_CONFIG_DIR`), using the container
  environment as template input.
- `resources/`: separate, unversioned sushy-tools, vbmc and ironic-client
  images used by test environments.

## Testing

- Build: `make build` (`CONTAINER_ENGINE`, default `podman`). Checks:
  `hack/*.sh`, plus `python3 -m pytest tests/` for Python. CI jobs:
  [Prow](https://github.com/metal3-io/project-infra/blob/main/prow/config/jobs/metal3-io/ironic-image.yaml)
  and `.github/workflows/`.
- Conventions are whatever the existing code, scripts, and lint configs
  do. Read neighboring files before writing new ones.
- Before finishing, add or update tests for every behavior change, build
  the image, and run the `hack/` checks for the file types you touched.
  All must pass.
- Do not touch `releasenotes/` outside a release PR. `make release-notes`
  generates them from PR titles; only release PRs curate them by hand
  ([docs/releasing.md](docs/releasing.md)).
- PR titles start with `:warning:` (breaking), `:sparkles:` (feature),
  `:bug:` (fix), `:book:` (docs) or `:seedling:` (other). The release
  notes tool sorts PRs by this prefix.
- Do not run `hack/prepare-bmo-tests.sh` or `hack/prepare-irso-tests.sh`
  unless the user asks: they need a kind or minikube cluster, load images
  into it, and write a kustomize overlay into a sibling
  `../baremetal-operator` checkout. CI runs them (`bmo-e2e`,
  `irso-functional`).

## Invariants

These apply to writing and to reviewing changes.

- **Runtime contract.** Entry point names, environment variables, and
  mount paths (`/conf`, `/data`, `/shared`, `/certs/...`, `/auth/...`) are
  consumed by the
  [Ironic Standalone Operator](https://github.com/metal3-io/ironic-standalone-operator),
  BMO's `ironic-deployment/` and metal3-dev-env. Never rename or remove
  one without a deprecation path, and mark such PRs as breaking. New
  variables are documented in [README.md](README.md).
- **Read-only root.** The image must keep working with a read-only root
  filesystem and only `/conf`, `/data`, `/tmp` and `/shared` writable, as
  the non-root `ironic` user. Runtime writes go there, never to `/etc` or
  `/bin`.
- **Config overrides.** Any Ironic option can already be set at runtime
  with `OS_<section>__<option>` (see `ironic-config/ironic.conf.j2`). Do
  not add a dedicated variable when that works.
- **Upstream pins.** `IRONIC_SOURCE`, `NGS_SOURCE` and
  `OPENSTACK_REQUIREMENTS_SOURCE` in the `Dockerfile` are SHAs in the form
  `ARG X=<sha> # <branch>`; Renovate (`renovate.json`) depends on that
  form. On `main`, `upper-constraints.txt` stays empty and constraints
  come from the pinned requirements commit; release branches carry a
  pinned file. See
  [docs/upper-constraints-pinning.md](docs/upper-constraints-pinning.md)
  and [docs/releasing.md](docs/releasing.md).
- **Security.** Never weaken security to make something work: no
  disabled TLS verification, weaker TLS protocol or cipher defaults,
  broader file permissions, secrets in images or logs, or skipped
  validation. The API runs `noauth` unless htpasswd credentials are
  provided (`scripts/auth-common.sh`); keep that path intact. Treat
  environment variables and mounted files as input that ends up verbatim
  in rendered config. Call out any change to
  `scripts/auth-common.sh`, `scripts/tls-common.sh`, httpd vhosts or
  JSON-RPC exposure in the PR description.
- **Tenancy and isolation.** One Ironic serves every namespace BMO
  manages, so a leak here reaches every tenant. Review these areas with
  extra care:
   - Cross-service access. The API, JSON-RPC, ironic-networking
     JSON-RPC, vmedia and iPXE httpd vhosts, and the Prometheus exporter
     have separate TLS or auth settings. A change to one must not open
     another.
   - Role isolation. The image is prepared to run as the non-root
     `ironic` user (`configure-nonroot.sh`; the `Dockerfile` sets no
     `USER`). Do not add runtime steps that need root, or widen
     group-writable paths.
   - Multi-tenancy. httpd serves `/shared/html` to the provisioning
     network. Never place credentials, node data or logs under it.
- **Pinning.** Pin new external references: GitHub Actions by commit SHA,
  container images by digest, upstream sources by commit SHA, downloaded
  binaries by checksum.

## External references

- [Metal3 Book, Ironic](https://book.metal3.io/ironic/introduction)
- [Ironic documentation](https://docs.openstack.org/ironic/latest/)
- [Metal3 design proposals](https://github.com/metal3-io/metal3-docs/tree/main/design)
