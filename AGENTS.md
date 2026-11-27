# Python style

- Use explicit type annotations for variables, attributes, function parameters, and return values in new or changed code.
- Use modern Python syntax: `type Name = ...` for type aliases and PEP 695 square bracket type parameters for generic classes and functions when needed.
- Separate logical blocks with blank lines and follow the surrounding project style.
- Preserve existing uncommitted work when editing the repository.

# Task completion and commits

- After completing each implementation task, run the checks relevant to the changed behavior and review the diff before committing.
- If checks fail, fix the problem and rerun the relevant checks. If a problem cannot be resolved or requires clarification, ask the user before committing.
- Once the implementation is complete and checks pass, create a local Git commit for the task.
- Do not push commits unless the user requests it.
