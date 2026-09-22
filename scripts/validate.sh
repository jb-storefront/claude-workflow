#!/usr/bin/env bash
# Validate the plugin and the marketplace manifest. Run from anywhere; CI runs this too.
set -euo pipefail
cd "$(dirname "$0")/.."

fail=0

echo "== plugin"
# Point at plugin.json, not the directory: a directory holding a marketplace
# manifest resolves to the marketplace and the plugin goes unchecked.
if ! claude plugin validate .claude-plugin/plugin.json --strict; then fail=1; fi

echo "== marketplace"
if ! claude plugin validate .claude-plugin/marketplace.json --strict; then fail=1; fi

# Neither manifest can see the other, so strict validation passes on a version
# disagreement that makes the marketplace advertise a release nobody shipped.
# `claude plugin validate` reads the two manifests and nothing else: pointed at
# the root, at plugin.json, or at skills/ it reports `contents: []` and exits 0
# for a SKILL.md whose YAML does not parse. The one file a skill actually is
# would otherwise reach the default branch unchecked.
echo "== skills"
if ! python3 scripts/check-skill-frontmatter.py skills; then fail=1; fi

echo "== versions"
plugin_version=$(jq -r '.version' .claude-plugin/plugin.json)
marketplace_version=$(jq -r '.metadata.version' .claude-plugin/marketplace.json)
if [ "$plugin_version" = "$marketplace_version" ]; then
  echo "✔ plugin and marketplace agree on $plugin_version"
else
  echo "✘ plugin is $plugin_version but marketplace metadata is $marketplace_version"
  fail=1
fi

exit $fail
