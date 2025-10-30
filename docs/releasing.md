# ironic-image releasing

This document details the steps to create a release for
`ironic-image`.

**NOTE**: Always follow
[release documentation from the main branch](https://github.com/metal3-io/ironic-image/blob/main/docs/releasing.md).
Release documentation in release branches may be outdated.

## Before making a release

Things you should check before making a release:

- Check the
  [Metal3 release process](https://github.com/metal3-io/metal3-docs/blob/main/processes/releasing.md)
  for high-level process and possible follow-up actions
- Verify the latest bugfix or stable branches (which is the most recent) in ironic
  upstream repository;
- Verify compatibility with latest sushy upstream releases or master
  branches based on ironic bugfix or stable requirements and constraints
- Verify openstack upper-constraints compatibility with ironic bugfix or stable branches
- Verify any other direct or indirect dependency is uplifted to close any public
  vulnerabilities

## Permissions

Creating a release requires repository `write` permissions for:

- Branch creation

These permissions are implicit for the org admins and repository admins.
A release team member gets permissions via `metal3-release-team`
membership. This GitHub team has the required permissions in each repository
required to release Ironic-image. Adding person to the team gives him/her the
necessary rights in all relevant repositories in the organization. Individual
persons should not be given permissions directly.

Patch releases don't require extra permissions.

## Process

Ironic-image uses [semantic versioning](https://semver.org).

- Regular releases: `vx.y.z`
- Beta releases: `vx.y.z-beta.w`
- Release candidate releases: `vx.y.z-rc.w`

### Repository setup

Clone the repository:
`git clone git@github.com:metal3-io/ironic-image`

or if using existing repository, make sure origin is set to the fork and
upstream is set to `metal3-io`. Verify if your remote is set properly or not
by using following command `git remote -v`.

- Fetch the remote (`metal3-io`): `git fetch upstream`
This makes sure that all the tags are accessible.

### Preparing a branch

Ironic-image requires a branch to be created and updated before the automation runs.
If (and only if) you're creating a release `vx.y.0` (i.e. a minor release):

- Switch to the main branch: `git checkout main`

- Identify the commit you wish to create the branch from, and create a branch
  `release-x.y`: `git checkout <sha> -b release-x.y` and push it to remote:
  `git push upstream release-x.y` to create it. Replace `upstream` with
  the actual remote name for the upstream source (not your private fork).

- Setup the CI for the new branch in the prow configuration.
  [Prior art](https://github.com/metal3-io/project-infra/pull/976)

Create a development branch (e.g. `prepare-x.y`) from the newly created branch:

- Pin the constraints.
   [Prior art](https://github.com/metal3-io/ironic-image/pull/655).

- Pin the `IRONIC_SOURCE` to specific SHA in the upstream release branch. It must
   be in format `ARG IRONIC_SOURCE=<sha> # <branch_name>` for Renovate bot to
   be able to update it automatically in the future.
   [Prior art](https://github.com/metal3-io/ironic-image/pull/771)

- Commit your changes, push the new branch and create a pull request:
   - The commit and PR title should be
    :seedling: Pin constraints, prepare release-0.x:
    -`git commit -S -s -m "Pin constraints, prepare release-x.y"`
     where X.Y is the Ironic branch you used above
    -`git push -u origin prepare-x.y`
   - The pull request must target the new branch (`release-x.y`), not `main`!

Wait for the pull request to be merged before proceeding.

### Creating Release notes

- Switch to the main branch: `git checkout main`

- Create a new branch for the release notes**:
  `git checkout origin/main -b release-notes-x.y.z`

- Generate the release notes: `RELEASE_TAG=vx.y.z make release-notes`
   - Replace `vx.y.z` with the new release tag you're creating.
   - This command generates the release notes here
    `releasenotes/<RELEASE_TAG>.md` .

- Next step is to clean up the release note manually.
   - If release is not a beta or release candidate, check for duplicates,
    reverts, and incorrect classifications of PRs, and whatever release
    creation tagged to be manually checked.
   - For any superseded PRs (like same dependency uplifted multiple times, or
    commit revertion) that provide no value to the release, move them to
    Superseded section. This way the changes are acknowledged to be part of the
    release, but not overwhelming the important changes contained by the
    release.

- Commit your changes, push the new branch and create a pull request:
   - The commit and PR title should be 🚀 Release vx.y.z:
     -`git commit -S -s -m ":rocket: Release vx.y.z"`
     -`git push -u origin release-notes-x.y.z`
   - Important! The commit should only contain the release notes file, nothing
    else, otherwise automation will not work.

- Ask maintainers and release team members to review your pull request.

Once PR is merged following GitHub actions are triggered:

- GitHub action `Create Release` runs following jobs:
   - GitHub job `push_release_tags` will create and push the tags. This action
    will also create release branch if its missing and release is `rc` or
    minor.
   - GitHub job `create draft release` creates draft release. Don't publish the
    release until release tag is visible in. Running actions are visible on the
    [Actions](https://github.com/metal3-io/ironic-image/actions)
    page, and draft release will be visible on top of the
    [Releases](https://github.com/metal3-io/ironic-image/releases).
    If the release you're making is not a new major release, new minor release,
    or a new patch release from the latest release branch, uncheck the box for
    latest release. If it is a release candidate (RC) or a beta release,
    tick pre-release box.
   - GitHub jobs `build_ironic_image` and `build_ironic_image_cs10` build release
    images with the release tag, and push them to Quay. Make sure the release
    tags are visible in Quay tags pages:
      - [Ironic CS9](https://quay.io/repository/metal3-io/ironic?tab=tags)
      - [Ironic CS10](https://quay.io/repository/metal3-io/ironic_cs10?tab=tags)
    If the new release tag is not available for any of the images, check if the
    action has failed and retrigger as necessary.

### Release artifacts

We need to verify all release artifacts are correctly built or generated by the
release workflow. You can use `./hack/verify-release.sh` to check for existence
of release artifacts, which should include the following:

Git tags pushed:

- Primary release tag: `v0.x.y`
- Go module tags: `api/v0.x.y` and `test/v0.x.y`

Container images built and tagged at Quay registry:

- [ironic:vx.y.z](https://quay.io/repository/metal3-io/ironic?tab=tags)
- [ironic_cs10:vx.y.z](https://quay.io/repository/metal3-io/ironic_cs10?tab=tags)

You can also check the draft release and its tags in the Github UI.

### Make the release

After everything is checked out, hit the `Publish` button your GitHub draft
release!

## Post-release actions for new release branches

Some post-release actions are needed if new minor or major branch was created.

### Dependabot configuration

In `main` branch, Dependabot configuration must be amended to allow updates
to release branch dependencies and GitHub Workflows.

If project dependencies or modules have not changed, previous release branch
configuration can be copied and amend the `target-branch` to point to our new
release branch. Release branches that are End-of-Life should be removed in the
same PR, as updating `dependabot.yml` causes Dependabot to run the rules,
ignoring the configured schedules, causing unnecessary PR creation for EOL
branches.

If project dependencies have changed, then copy the configuration of `main`,
and adjust the `ignore` rules to match release branches. As generic rule we
don't allow major or minor bumps in release branches.

[Prior art](https://github.com/metal3-io/ironic-image/pull/702)

### Renovate configuration

Renovate bot monitors Ironic upstream branches for updates and creates
PRs when changes are detected. The configuration in `renovate.json` must be
updated in the `main` branch to include the new release branch.

Update `renovate.json` in `main` branch:

- Add the new release branch (e.g., `release-32.0`) to the `baseBranchPatterns`
   array
- Add the new release branch to the `packageRules` section with the daily
   schedule configuration matching other release branches

### Branch protection rules

Branch protection rules need to be applied to the new release branch. Copy the
settings after the previous release branch, with the exception of
`Required tests` selection. Required tests can only be selected after new
keywords are implemented in Jenkins JJB, and project-infra, and have been run at
least once in the PR targeting the branch in question.
Branch protection rules require user to have `admin` permissions in the repository.

### Documentation

Update the [user guide](https://github.com/metal3-io/metal3-docs/tree/main/docs/user-guide/src):

- Update [supported versions](https://github.com/metal3-io/metal3-docs/blob/main/docs/user-guide/src/version_support.md)
  with the new Ironic-image version. As a rule of thumb, the latest 3 stable
  branches are Supported, but we keep testing older stable branches (usually
  up to 2 beyond the Supported branches) based on the
  [CI Test Matrix][ci-test-matrix].
  Please keep in mind that the ironic-image releases are strictly tied
  to the [ironic releases](https://docs.openstack.org/releasenotes/ironic/)
  and its bugfix and stable branches. While ironic stable branches have
  a lifespan of 18 months, following this [schema](https://releases.openstack.org/),
  the bugfix branches are supported for only 6 months after their creation;
  for this reason it's not possible to guarantee backports of bug fixes
  in older ironic-image branches.

- Update `README.md` with release specific information, both on `main` and in the
  new `release-X.Y` branch as necessary.
  [Prior art](https://github.com/metal3-io/ironic-image/pull/594)

- In the `release-X.Y` branch, update the build badges in the `README.md` to point
  to correct Jenkins jobs, so the build statuses of the release branch are
  visible.
  [Prior art](https://github.com/metal3-io/ironic-image/pull/595)

### Update milestones

- Make sure the next two milestones exist. For example, after 29.0 is out, 30.0
  and 31.0 should exist in Github.
- Set the next milestone date based on the expected release date, which usually
  happens shortly after the next Ironic release.
- Remove milestone date for passed milestones.

Milestones must also be updated in the Prow configuration.

[Prior art](https://github.com/metal3-io/project-infra/pull/976).

## Ironic Standalone Operator updates

[IrSO](https://github.com/metal3-io/ironic-standalone-operator) needs to be
updated to support the new release branch. At the very least, the new branch
must be added to

- [API](https://github.com/metal3-io/ironic-standalone-operator/blob/e45e6be580c07fcca560dadb33bdd3006257ae87/api/v1alpha1/ironic_types.go#L23-L26)
- [implemented versions](https://github.com/metal3-io/ironic-standalone-operator/blob/main/pkg/ironic/version.go)

If explicit upgrade actions are required, they must be implemented in the
operator code as well. After that, an
[IrSO release](https://github.com/metal3-io/ironic-standalone-operator/blob/main/docs/releasing.md)
will be prepared.

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

[ci-test-matrix]: https://github.com/metal3-io/metal3-docs/blob/main/docs/user-guide/src/version_support.md#ci-test-matrix

<!-- cspell:ignore revertion -->
