#!/bin/bash

set -euxo pipefail

CHECK_RELEASE=${CHECK_RELEASE:-"master"}

for repo in "openstack-ironic" "openstack-ironic-inspector" "openstack-ironic-lib" "openstack-sushy"
do
  line=$(grep "$repo@" requirements.cachito)
  echo $line
  repo_full=$(echo $line | cut -d "+" -f 2)
  echo $repo_full
  commit_hash=$(echo $repo_full | cut -d "@" -f 2)
  echo $commit_hash
  git_url=$(echo $repo_full | cut -d "@" -f 1)
  echo $git_url
  git clone $git_url
  pushd $repo
  git checkout $CHECK_RELEASE
  if git merge-base --is-ancestor $commit_hash HEAD; then
    echo "commit $commit_hash is in $CHECK_RELEASE"
  else
    echo "commit $commit_hash does not belong to $CHECK_RELEASE"
    WRONG_HASH+="$repo "
  fi
  popd
  rm -fr $repo
done

if [ -n "${WRONG_HASH:-}" ]; then
  echo "Wrong commit hash for repos: $WRONG_HASH"
  exit 1
fi

echo "All commit hashes have been successfully verified"
