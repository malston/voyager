#!/bin/bash
# Script to set the Concourse pipeline

if [ -z "$CONCOURSE_TOKEN" ]; then
    echo "Error: CONCOURSE_TOKEN environment variable is not set"
    exit 1
fi

if [ -z "$GITHUB_TOKEN" ]; then
    echo "Error: GITHUB_TOKEN environment variable is not set"
    exit 1
fi

# These values should be set by the user
CONCOURSE_URL="YOUR_CONCOURSE_URL"
TEAM="YOUR_TEAM_NAME"
PIPELINE="release-pipeline"

# Get the current directory name as the repo name
REPO_NAME=$(basename $(pwd))
# Get the github username - this is a placeholder, user should modify
OWNER="YOUR_GITHUB_USERNAME"

# Make the script executable
chmod +x ci/set-pipeline.sh

echo "Setting up Concourse pipeline for $OWNER/$REPO_NAME"

# Replace placeholders in pipeline.yml
sed -i "s/{{owner}}/$OWNER/g" ci/pipeline.yml
sed -i "s/{{repo}}/$REPO_NAME/g" ci/pipeline.yml

# Command to set the pipeline (uncomment when ready to use)
# fly -t $TEAM login -c $CONCOURSE_URL -n $TEAM
# fly -t $TEAM set-pipeline -p $PIPELINE -c ci/pipeline.yml \
#    -v github_token=$GITHUB_TOKEN \
#    -v version="0.1.0"

echo "Pipeline prepared. Edit ci/set-pipeline.sh with your Concourse details and uncomment the fly commands to set up the pipeline."
echo "Then run: ./ci/set-pipeline.sh"
