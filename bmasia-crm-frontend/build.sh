#!/bin/bash
# Build script that ensures CI=false for ESLint warnings
export CI=false
export DISABLE_ESLINT_PLUGIN=true
export ESLINT_NO_DEV_ERRORS=true
export SKIP_PREFLIGHT_CHECK=true
react-scripts build
