# Security Policy

## Supported Projects

There are multiple projects in this repo. Versions are released as tags with a prefix to denote which project is targeted.

We actively support security updates for the following versions:

### MedCAT NLP Library
- [Medical Concept Annotation Tool](medcat-v2/README.md)

| Version         | Supported          |
| -------         | ------------------ |
| medcat/v2.x.x   | :white_check_mark: |
| medcat/v1.x.x   | :white_check_mark: |
| < 1.0           | :x:                | 

### MedCAT Trainer
- [Medical Concept Annotation Tool Trainer](medcat-trainer/README.md)

| Version                | Supported          |
| -------                | ------------------ |
| MedCATTrainer/v2.x.x   | :white_check_mark: |
| < 2.0                  | :x:                |


### MedCAT Service
- [MedCAT Service](medcat-service/README.md)

| Version               | Supported          |
| -------               | ------------------ |
| MedCATService/1.x     | :white_check_mark: |
| < 1.0                 | :x:                |


## Unsupported Projects
Unless a project is explicitly stated in the previous section, all other projects in this monorepo are provided as-is for demonstration, testing, or experimentation purposes.

In terms of secuirty the unlisted projects are not intended for use with production data or in a live environment. 

By using them, you acknowledge that:

- They are provided without warranties of any kind, express or implied, including but not limited to security, reliability, or suitability for a particular purpose.
- They may contain incomplete features, insecure defaults, or other issues that could compromise data or operations.
- The maintainers do not guarantee active support, monitoring, or security updates for these projects.
- You are solely responsible for reviewing, testing, and securing any code before use with sensitive or production data.

## Reporting a Vulnerability

If you discover a security vulnerability, **please do not open a public issue**.

Instead, report it privately by using the **[GitHub Security Advisories](https://github.com/CogStack/cogstack-nlp/security/advisories)** for this repo

### Guidelines for Responsible Disclosure

- Do not publicly disclose details of the vulnerability until we have released a fix.
- Do not attempt to exploit the vulnerability beyond what is necessary to demonstrate it.
- Provide as much detail as possible (affected versions, reproduction steps, etc.) to help us triage the issue quickly.