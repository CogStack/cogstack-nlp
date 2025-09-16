# Security Policy

## Supported Versions

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

The following projects are provided as-is for demonstration and experimentation purposes.  
They are not intended for production use and do not come with active support.  

- [Deidentify app](anoncat-demo-app/README.md)
- [MedCAT Demo App](medcat-demo-app/README.md)
- [MedCAT Tutorials](medcat-v2-tutorials/README.md)

## Reporting a Vulnerability

If you discover a security vulnerability, **please do not open a public issue**.

Instead, report it privately by using the **[GitHub Security Advisories](https://github.com/CogStack/cogstack-nlp/security/advisories)** for this repo

### Guidelines for Responsible Disclosure

- Do not publicly disclose details of the vulnerability until we have released a fix.
- Do not attempt to exploit the vulnerability beyond what is necessary to demonstrate it.
- Provide as much detail as possible (affected versions, reproduction steps, etc.) to help us triage the issue quickly.