---
name: create-infra-request
description: Raise an Infrastructure request on the team that owns the infrastructure, in the tracker, project and shape the repo's docs/agents/infrastructure.md declares, instead of opening a pull request on their infrastructure repository or changing a live resource by hand. Use whenever a change needs infrastructure this repository does not own - a table column, a TTL or retention policy, an environment variable or setting, a secret, an IAM grant, a bucket, a service - or when the user says "/create-infra-request", "raise a ticket with platform", "ask PE for", "this needs Terraform", or is about to run an ALTER TABLE, a gcloud write or a terraform apply themselves.
---

# Create infra request

A change in this repository sometimes needs a change in infrastructure it does not own: a column
on a table another team's Terraform declares, a policy on a database, a setting or a secret on a
service. The team that owns that code changes it, through their own tracker. This skill raises the
request there, in the shape they already use, so every request reads alike and none of them is a
pull request on their repository or a resource changed by hand.

Changing a live resource by hand is the failure this skill exists to prevent, not a quicker way to
do the same thing. A resource the infrastructure code does not declare is one its next apply tries
to take away, and that can be worse than the gap it closed: a table replaced to drop a column it
never declared takes its data with it.

## 0. Read the repo's infrastructure file

`docs/agents/infrastructure.md`, beside `issue-tracker.md` and `workflow.md`. `CONTRACTS.md` gives
its shape. It names:

- the tracker, the project and the issue type requests go to, and the priorities in use
- one or more **example requests** that the owning team accepted, which are the format
- where the infrastructure code lives, resource by resource
- the read-only commands that show a resource's live state
- what is known to be dangerous here, such as a resource set without deletion protection

**No file → stop.** Say which team owns the infrastructure if you can tell, and offer to write the
file with the user. Do not guess a tracker or invent a format: a request in the wrong place or the
wrong shape is one the owning team bounces, and the user learns of it a week later.

## 1. Find everything the work needs

Scope it to the whole piece of work, not only the change in front of you. When the change belongs
to a Spec, read every Slice of it, including the ones not yet built, and list each piece of
infrastructure any of them needs. A request that covers the Spec once is one the owning team plans
around. Three requests arriving a week apart are three interruptions.

For each piece, record what it is, which Slice needs it, and whether that Slice has merged. A
merged Slice whose infrastructure is missing is a live gap and is said first.

A name the code does not use yet, such as a column or a setting for an unbuilt Slice, is fixed in
the request. After the request is created, write the same name into that Slice's issue (step 6), so
whoever builds it builds against what was provisioned.

## 2. Find the code that owns each piece, and its live state

Search the organisation's infrastructure repositories for the resource (`gh search code` over the
owner, and the paths `docs/agents/infrastructure.md` names). For each piece, read the file that
declares it at the default branch's current SHA, and keep that SHA for the permalinks.

Then read the live state with the file's read-only commands and compare it with the code. Report
what you found, not what the code implies: "the live table matches the leaf", "the database has six
policies and the module lists six". A difference between the two is a finding in its own right,
and it goes in the request.

Never write to a live resource in this step, even one you are sure about. The request is how the
write happens.

## 3. Draft it in the example's shape

Read the example requests and match them: their sections, their headings, their tone, their
length, how they write a title. The repo's file may add rules; follow them. Within that shape:

- **One request per release boundary the owning team would recognise**, unless the user wants them
  together. When combined, number the parts and say which can be applied now and which wait.
- **Facts, with where they came from.** Permalinks pinned to a SHA, never `path:line` and never a
  branch. The live state you read in step 2, with the command.
- **The change, exactly.** Names, types, modes, values, defaults. A table of them when there are
  more than two.
- **Acceptance criteria the owning team can check themselves**, as the commands they would run and
  what each shows. A plan that changes in place rather than replacing anything is usually the first
  one.
- **Secrets by name only.** The request names the secret and where it lives. The infrastructure
  code creates the secret and never a version, and the value is added by a person in the console.
  Wiring a service to a secret with no version fails the deploy, so the wiring waits on the value
  and the request says so.
- **What must not change**, when a neighbour of the change would be wrong to touch: a collection
  that must not get a policy, a setting left unset everywhere.

## 4. Show it, and wait

Show the whole request, its project, type and priority, and the names it fixes for unbuilt Slices.
Create nothing until the user confirms. A request is outward-facing: another team plans from it the
moment it lands.

## 5. Create it, then read it back

Create it in the tracker the file names. Read back the fields you set, priority included: a field a
tracker silently ignored is a request at the wrong priority. Report the key and the link.

## 6. Tie it back

- **Each Slice whose infrastructure it covers** gets a comment naming the request, and the names it
  fixed that the Slice will build against.
- **A pull request that depends on it** says so in its body, in place of any step that told an
  operator to change the resource by hand.
- **Repository docs that say to change it by hand** are corrected in the same change: they say where
  the resource is declared and that changes go through a request.

## Rules

- Never open a pull request on another team's infrastructure repository, and never write to a live
  resource it declares, whatever the user's access allows. Raise the request.
- No request without `docs/agents/infrastructure.md`. Stop and offer to write it.
- Live state is read before it is described. A request that says what the code implies rather than
  what the resource shows is a request built on a guess.
- No secret value in a request, a comment, a commit or a tracked file. Only names.
- Nothing is created before the user confirms the full draft.
