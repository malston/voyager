#!/usr/bin/env bash
# Script to set the Concourse pipeline

if [ -z "$GITHUB_TOKEN" ]; then
    echo "Error: GITHUB_TOKEN environment variable is not set"
    exit 1
fi

get_latest_version() {
    git pull -q --all
    if ! GIT_RELEASE_TAG=$(git describe --tags "$(git rev-list --tags --max-count=1)" 2>/dev/null); then
        echo "No release tags found. Make sure to fly the release pipeline."
        exit 1
    fi
    echo "${GIT_RELEASE_TAG##*release-v}"
}

# These values should be set by the user
TARGET="main" # Default target name, can be changed by user
PIPELINE="release-pipeline"
VERSION=$(get_latest_version)
RELEASE_BODY=""

usage() {
    cat <<EOF
Usage:
    $0 [-t target] [-p pipeline_name] [-v version] [-b release_body]

Options:
   -t target        Name of the concourse target to use. (default: $TARGET)

   -p pipeline_name Name of the pipeline to set. (default: $PIPELINE)

   -v version       Version of the release. (default: $VERSION)

   -b release_body  Body of the release notes.
                    If not provided, it will be empty.

   --help           Show this help message and exit.
EOF
}

while [[ $1 =~ ^- && $1 != "--" ]]; do
    case $1 in
    -t | --target)
        shift
        TARGET=$1
        ;;
    -p | --pipeline)
        shift
        PIPELINE=$1
        ;;
    -v | --version)
        shift
        VERSION=$1
        ;;
    -b | --release-body | --body)
        shift
        RELEASE_BODY=$1
        ;;
    -h | --help)
        usage
        exit 0
        ;;
    esac
    shift
done
if [[ $1 == '--' ]]; then shift; fi

fly -t "$TARGET" set-pipeline -p "$PIPELINE" -c ci/pipeline.yml \
    -v github_token="$GITHUB_TOKEN" \
    -v release_body="$RELEASE_BODY" \
    -v version="$VERSION"
