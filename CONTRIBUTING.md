# Contributing to CogStack
First of all, we would like to thank you for considering contributing towards CogStack!

Please consider the below a guideline. Best judgment should be used in situations where the guidelines are not clear.

## Code of Conduct

All contributors are expected to follow our [Code of Conduct](CODE_OF_CONDUCT.md).

## Questions

If you have questions regarding this project, you are better off expressing them in our [discourse](https://discourse.cogstack.org/) rather than creating an issue on github.

## Background Information

Most of the relevant links to background information are listed in our [README](README.md).

## How to Contribute

There are many ways of contributing to the project
- Reporting issues
- Suggesting new features
- Contributing to code

The following subsections will go into a little more detail regarding each of the above:

### Reporting Issues

Some things to remember when reporting an issue:
- Describe the issue clearly
- Provide the steps to reproduce the issue (if possible)
- Describe the behaviour you observed
- Describe the behaviour you expected
- Include all relevant information, including (but not limited to)
  - Version of MedCAT used
  - Versions of dependencies used
  - Config file(s)
  - Database(s) used
  - Deployment environment

### Suggesting New Features

CogStack is always looking to grow and provide new features.

Some things to remember when suggesting a new feature:
- Describe the new feature in detail
- Describe the benefits of this new feature

### Contributing to Code
Thank you for taking the time to contribute! We appreciate your efforts to improve this project and make it better for everyone.

Before submitting a pull request, try to make sure that it's likely to pass checks and be up to date

Each project in this repository may have its own specific commands or tools used, so be sure to check the readme or documentation for each part for details.

Here are a few guidelines to follow:
- The changes are based on the `main` branch (i.e., merge the `main` branch into your feature branch before submitting a PR).
- There are no issues with static type checks (e.g., run `mypy` ).
- The code passes linting and style checks (e.g., `flake8` or `ruff`).
- All tests pass successfully (run your project's test suite as documented, eg run `python -m unittest discover`).


## Code Guidelines

### Commit Message Guidelines

We recommend following a conventional commit style to keep the project history clear and meaningful. This is well documented on https://www.conventionalcommits.org/en/v1.0.0/

The Conventional Commit standard looks like this:

```
<type>(<scope>): <short summary>
<blank line>
[optional body]
<blank line>
[optional footer(s)]
```

An example commit message could be

```
feat(medcat-service): Create APIs for healthchecks for container monitoring
```

For internal devs, you can include an issue number in the format CU-xxxxx in your commit and/or PR title, and it will automatically link the issue showing in github and clickup.

#### Types
These are some of the types that can be used in your commit message header:

- feat: New features
- fix: Bug fixes
- test: Changes to tests, eg adding a new unit test
- chore: Miscelanous cleanups or toil like changing .gitignore
- docs: Adding documentation
- style: Code formatting only changes
- refactor: Code refactoring that doesnt change the runtime
- perf: Performance improvement changes
- build: Build related changes, such as updating dependencies or github actions

#### Scopes
Provide the project as a scope. 

This is likely to be the parent folder name your changes are under, for example "medcat-service", or "medcat-trainer".

Scope is optional, for changes that target the whole repo or multiple projects.


### Pull Request Guidelines

#### Pull Request Titles
We recommend using your PR title in the same format as your commit message header, so it clearly describes the change. 

To repeat the above, a typical format for a PR title could be:

```
<type>(<scope>): <short summary>
```

An example PR title could be

```
feat(medcat-service): Create API for healthchecks for container monitoring
```

#### Pull Request Bodies
We haven't put a formal template in for pull requests yet.

Though the structure isn’t enforced, a good PR description helps reviewers and future maintainers.

Consider including things such as:

- Why is this change needed? – explain the motivation or problem being solved. What is the current behavior, and what is the new behavior. 
- How was this implemented? – detail the approach, architecture decisions, or dependencies.
- How was this tested? – provide instructions for verifying the change works correctly.
- Are there any references? – link to issues, discussions, or design documents.