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

# Neither of the two commands above opens a SKILL.md; see the checker's docstring.
echo "== skills"
if ! python3 scripts/test-check-skill-frontmatter.py; then fail=1; fi
if ! python3 scripts/check-skill-frontmatter.py skills; then fail=1; fi

# Neither manifest can see the other, so strict validation passes on a version
# disagreement that makes the marketplace advertise a release nobody shipped.
echo "== versions"
plugin_version=$(jq -r '.version' .claude-plugin/plugin.json)
marketplace_version=$(jq -r '.metadata.version' .claude-plugin/marketplace.json)
if [ "$plugin_version" = "$marketplace_version" ]; then
  echo "✔ plugin and marketplace agree on $plugin_version"
else
  echo "✘ plugin is $plugin_version but marketplace metadata is $marketplace_version"
  fail=1
fi

# `claude plugin validate` only ever reads a manifest. A SKILL.md with no `name`
# passes it, so "the skill validates" would be true by construction and could
# never disagree with the file. These two checks are what make that claim mean
# something.
frontmatter() { awk 'NR==1 && $0!="---" {exit} NR>1 && $0=="---" {exit} NR>1' "$1"; }

# Without this an empty glob is passed through literally and the loop runs once
# on a filename that does not exist, which reads as a failure rather than as
# nothing to check.
shopt -s nullglob

echo "== skills"
for skill in skills/*/SKILL.md; do
  dir=$(basename "$(dirname "$skill")")
  fm=$(frontmatter "$skill")
  name=$(printf '%s\n' "$fm" | sed -n 's/^name:[[:space:]]*//p')
  desc=$(printf '%s\n' "$fm" | sed -n 's/^description:[[:space:]]*//p')
  ok=1
  if [ -z "$name" ]; then
    echo "✘ $skill: frontmatter has no name"
    ok=0
  elif [ "$name" != "$dir" ]; then
    # The name is what a skill is invoked by; a name that disagrees with its
    # directory is a skill nobody can call by the path they can see.
    echo "✘ $skill: name is '$name' but the directory is '$dir'"
    ok=0
  fi
  if [ -z "$desc" ]; then
    # The description is the only thing the model reads when deciding whether a
    # skill applies, so a skill without one is a skill that never triggers.
    echo "✘ $skill: frontmatter has no description"
    ok=0
  fi
  if [ "$ok" -eq 1 ]; then echo "✔ $dir"; else fail=1; fi
done

# /finalize-pr finds agents by the role in their frontmatter, not by filename,
# and the adopter is asked to teach each one the domain in exactly one place.
# Both are properties of the shipped file, so both are checkable here.
echo "== agent templates"
for template in skills/*/templates/agents/*.md; do
  fm=$(frontmatter "$template")
  name=$(printf '%s\n' "$fm" | sed -n 's/^name:[[:space:]]*//p')
  desc=$(printf '%s\n' "$fm" | sed -n 's/^description:[[:space:]]*//p')
  placeholders=$(grep -c '{{DOMAIN}}' "$template" || true)
  ok=1
  [ -z "$name" ] && { echo "✘ $template: frontmatter has no name"; ok=0; }
  [ -z "$desc" ] && { echo "✘ $template: frontmatter has no description"; ok=0; }
  if [ "$placeholders" -ne 1 ]; then
    echo "✘ $template: $placeholders {{DOMAIN}} placeholders, expected exactly 1"
    ok=0
  fi
  if [ "$ok" -eq 1 ]; then echo "✔ $(basename "$template")"; else fail=1; fi
done

exit $fail
