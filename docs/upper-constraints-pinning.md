# Pinning openstack/requirements (upper-constraints) via Renovate

## Context

The Dockerfile pins `IRONIC_SOURCE`, `NGS_SOURCE` and
`OPENSTACK_REQUIREMENTS_SOURCE` to git SHAs. Renovate bumps all three via
custom regex managers (dep names `openstack-ironic`,
`networking-generic-switch`, `openstack-requirements`), grouped into a
single PR on `main` ("openstack master sources" group, scheduled before
6am on Mondays). `build-wheels.sh` fetches `upper-constraints.txt` from
the pinned `OPENSTACK_REQUIREMENTS_SOURCE` commit when the local
upper-constraints file is empty.

## Problem

The goal is to never consume an upper-constraints file that Ironic has
not been tested against. Ironic's upstream gate tests each commit
against openstack/requirements master *as of the time that ironic commit
merges*. Therefore "tested by Ironic" is approximated by:

> the newest openstack/requirements commit that is **not newer** than
> the pinned `IRONIC_SOURCE` commit.

However, Renovate samples all three SHAs at the same scan time, and
openstack/requirements receives near-daily bot updates while ironic may
be quiet. The grouped PR will therefore often pin a requirements SHA
*newer* than the ironic SHA, i.e. constraints ironic never gated with.

## Constraints

- Renovate has no cross-dependency ordering rules.
- `minimumReleaseAge` does not work: the `git-refs` datasource
  (`git ls-remote`) provides no commit timestamps.
- `postUpgradeTasks` is unavailable on the hosted Mend app, so Renovate
  itself cannot run a script to correct the SHA.

## Conclusion for now

It would be possible to enforce the proper ordering in CI with a GitHub Actions
job that would run on Renovate PRs touching the Dockerfile.

Then as a result of the followup job there could be two automated outcomes:

- **fail-only**: fail the check if the pinned requirements SHA is
  newer than the resolved one, and fix the PR manually; or
- **auto-fix**: commit the resolved SHA to the PR branch. Caveat:
  Renovate then marks the branch as user-modified and stops updating
  it until the next new digest.

Out of these outcomes the first wouldn't be much of a help as reviewers would
need to manually redo the PR anyhow. The second option is possible but that
would involve a relatively complicated GH action. After the GH action is
executed Renovate would stop updating the PR as it would detect external
changes on the PR and it would mark it tainted and it would stop
updating/managing the PR.

In order to keep the dependency handling relatively understandable and
maintainable currently no followup action is done on the Renovate PRs.

The reason for not triggering a Renovate specific followup GH action is that
the Renovate PR will be tested against other PR tests that will build the
image and produce a failure if the alignment of Ironic, NGS and Openstack
Requirements is not sufficient.

In case the image builder or functional tests would fail the Renovate PR would
be deemed faulty by reviewers. Reviewers would either request Renovate to
recreate the PR or wait until Renovate updates the PR or close the PR and
sort out the dependency mismatch manually.

Right now it is possible that the ironic-image is built with an upper
constraint file that hasn't been tested by the upstream Ironic community but
it is very unlikely that the image would be built with an upper constraint
that would introduce dependencies that would break Metal3 functionality.

In case you find ironic-image produced by the upstream community that
was built with incompatible dependencies, create an issue describing your use
case so that your use case would be tested in the future.
