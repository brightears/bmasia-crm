#!/bin/bash
# Build script that ensures CI=false for ESLint warnings
export CI=false
export DISABLE_ESLINT_PLUGIN=true
npm run build:base
