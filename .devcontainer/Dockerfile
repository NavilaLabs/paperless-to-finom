# Dev image for the devcontainer. Kept separate from the production
# Dockerfile at the repo root (that one ships only runtime deps).
FROM mcr.microsoft.com/devcontainers/python:1-3.12-bookworm

# Non-root user 'vscode' already exists in this base image.

# The base image ships a yarn apt source whose GPG key is missing/expired,
# which makes `apt-get update` fail. We don't need yarn here, so drop that
# source before updating.
RUN rm -f /etc/apt/sources.list.d/yarn.list

# Handy CLI tools for poking at the API and DB during development.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    sqlite3 \
    jq \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Dev-time Python tooling (app deps get installed in post-create from
# requirements.txt so the editable install picks up your local code).
RUN pip install --no-cache-dir \
    ruff \
    pytest \
    pytest-cov \
    ipython
