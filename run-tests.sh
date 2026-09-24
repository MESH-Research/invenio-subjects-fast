#!/usr/bin/env bash
# Copyright (C) 2023-2026 MESH Research
#
# SPDX-License-Identifier: MIT


# Quit on errors
set -o errexit

# Quit on unbound symbols
set -o nounset

pytest_args=()
for arg in "$@"; do
	# from the CLI args, filter out some known values and forward the rest to "pytest"
	# note: we don't use "getopts" here b/c of some limitations (e.g. long options),
	#       which means that we can't combine short options (e.g. "./run-tests -Kk pattern")
	case ${arg} in
		*)
			pytest_args+=( "${arg}" )
			;;
	esac
done


uv run check-manifest --no-build-isolation

echo "Running ty on invenio_subjects_fast"
uv run ty check invenio_subjects_fast/

# Note: expansion of pytest_args looks like below to not cause an unbound
# variable error when 1) "nounset" and 2) the array is empty.
if [ ${#pytest_args[@]} -eq 0 ]; then
	uv run pytest -vv
else
	uv run pytest "${pytest_args[@]}"
fi
tests_exit_code=$?
exit "$tests_exit_code"
