#!/bin/bash

curl -LsSf https://astral.sh/uv/install.sh | sh

uv tool install fastapi
uv pip sync
uv run fastapi dev main.py
export AZURE_SUBSCRIPTION_ID="2c4288a1-0490-403e-99f8-5e7b533d1a7e"
