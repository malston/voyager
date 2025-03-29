#!/bin/bash
# Script to set the Concourse pipeline

if [ -z "$GITHUB_TOKEN" ]; then
    echo "Error: GITHUB_TOKEN environment variable is not set"
    exit 1
fi

# These values should be set by the user
TARGET="main" # Default target name, can be changed by user
PIPELINE="release-pipeline"
RELEASE_BODY="Release notes for the new version"

usage() {
    cat << EOF
Usage:
    $0 [-t target] [-u url] [-p pipeline_name]

Options:
   -t target         Name of the concourse target to use. (default: $TARGET)

   -u url            URL of the Concourse server. (default: $CONCOURSE_URL)

   -p pipeline_name  Name of the pipeline to set. (default: $PIPELINE)

   -h Help. Displays this message
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
    -v version="0.1.0"
