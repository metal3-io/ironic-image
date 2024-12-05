# Releasing ironic-image

This document explains how to prepare and publish a release for ironic-image, and
how often a new release branch is created.

**NOTE**: Always follow
[release documentation from the main branch](https://github.com/metal3-io/ironic-image/blob/main/docs/releasing.md).
Release documentation in release branches may be outdated.

## Pre-release actions

Things you should check before making a release:

- Check the
  [Metal3 release process](https://github.com/metal3-io/metal3-docs/blob/main/processes/releasing.md)
  for high-level process and possible follow-up actions
- Verify the latest bugfix or stable branches (which is the most recent) in ironic
  upstream repository;
- Verify compatibility with latest sushy and ironic-lib upstream releases or master
  branches based on ironic bugfix or stable requirements and constraints
- Verify openstack upper-constraints compatibility with ironic bugfix or stable branches
- Verify any other direct or indirect dependency is uplifted to close any public
  vulnerabilities

## Permissions

Creating a release requires repository `write` permissions for:

- Tag pushing
- Branch creation
- GitHub Release publishing

These permissions are implicit for the org admins and repository admins.
A release team member gets permissions via `metal3-release-team`
membership. This GitHub team has the required permissions in each repository
to make a release. Adding person to the team provides the necessary
rights  in all relevant repositories in the organization. Individual persons
should not be given permissions directly.

## Process

ironic-image uses [semantic versioning](https://semver.org). For version `vX.Y.Z`:

### Repository setup

Clone the repository:
`git clone git@github.com:metal3-io/ironic-image`

or if using existing repository, verify your intended remote is set to
`metal3-io`: `git remote -v`. For this document, we assume it is `origin`.

- If creating a new release branch, identify the commit you wish to create the
  branch from, and create a branch `release-X.Y` where `X.Y` corresponds to the
  ironic upstream release version, for example for `ironic 22.1` it's `release-22.1`:
  `git checkout <sha> -b release-X.Y` and push it to remote:
  `git push origin release-X.Y` to create it
- If creating a new patch release, use existing branch `release-X.Y`:
  `git checkout origin/release-X.Y`
- Wait for the CI support to be configured, then in the newly created release branch:
   - Add a copy of upper-constraints.txt from [Openstack Requirements](https://opendev.org/openstack/requirements)
     to replace the placeholder; if the ironic branch is a stable branch
     we should use the corresponding file from the same stable branch, in
     case of a bugfix branch we can use the current one from master
   - Pin ironic to match the corresponding bugfix or stable branches

### Tags

First we create a primary release tag, that triggers release note creation and
image building processes.

- Create a signed, annotated tag with: `git tag -s -a vX.Y.Z -m vX.Y.Z`
- Push the tags to the GitHub repository: `git push origin vX.Y.Z`

TODO(elfosardo): we should probably create an automated workflow with github
actions as it's been done for other repositories like BMO

### Release artifacts

NOTE(elfosardo): TODO once we have an automated workflow

### Release notes

Next step is to clean up the release note manually.

- Check for duplicates, reverts, and incorrect classifications of PRs, and
  whatever release creation tagged to be manually checked.
- For any superseded PRs (like same dependency uplifted multiple times, or
  commit revertions) that provide no value to the release, move them to
  Superseded section. This way the changes are acknowledged to be part of the
  release, but not overwhelming the important changes contained by the release.
- If the release you're making is not a new major release, new minor release, or
  a new patch release from the latest release branch, uncheck the box for latest
  release.
- Publish the release.

## Post-release actions for new release branches

Some post-release actions are needed when a new release branch is created.

### Branch protection rules

Branch protection rules need to be applied to the new release branch. Copy the
settings after the previous release branch, with the exception of
`Required tests` selection. Required tests can only be selected after new
keywords are implemented in Jenkins JJB, and project-infra, and have been run at
least once in the PR targeting the branch in question.

### Update README.md and build badges

Update `README.md` with release specific information, both on `main` and in the
new `release-X.Y` branch as necessary.

<!-- No example PR yet. To be added when first release from branch is made -->

In the `release-X.Y` branch, update the build badges in the `README.md` to point
to correct Jenkins jobs, so the build statuses of the release branch are
visible.

<!-- No example PR yet. To be added when first release from branch is made -->

### Branches lifecycle

Stable branches are maintained for 6 months after their creation unless
specified differently at the moment of the branch creation.
We aim to cut 2-3 stable branches every year and release as often
as possible to cover the majority of bug fixes and security updates.
Ideally a new stable branch should be created as close as possible after
an ironic stable or bugfix branch is created to avoid too much distance
from it and therefore the risk to go back in time with the ironic code.

## Additional actions outside this repository

Further additional actions may be required in the Metal3 project after
ironic-image release.
For that, please continue following the instructions provided in
[Metal3 release process](https://github.com/metal3-io/metal3-docs/blob/main/processes/releasing.md)

## Keeping sync with other images and tools

- The [sushy-tools](<https://github.com/metal3-io/ironic-image/tree/main/resources/sushy-tools>),
  [vbmc](https://github.com/metal3-io/ironic-image/tree/main/resources/vbmc)
  and [ironic-client](https://github.com/metal3-io/ironic-image/tree/main/resources/ironic-client)
  images won't be versioned, we expect them to work with any version.
- The [ipa-downloader](https://github.com/metal3-io/ironic-ipa-downloader)
  image uses the [ironic-python-agent](https://opendev.org/openstack/ironic-python-agent)
  which is strictly tied to the ironic features. Despite that, considering
  the relatively short lifetime of an ironic-image release, we expect it to
  work with no versioning so we'll keep using the master version for the
  time being. In the future we re-evaluate this consideration and eventually
  move to a versioned ipa-downloader too.
