# AI Coding playbook

Roles: planner (`plan`) → builder (`implement`) → reviewer (`review`).

A `plan` task should include:

- `path`: file to create or modify, relative to the repo
- `content` or `body`: expected contents

The planner spawns an `implement` task and a `review` task that depends on it.
The reviewer fails the pipeline if the file or implement result is missing.
