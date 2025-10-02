 # Medical <img src="https://github.com/CogStack/cogstack-nlp/blob/main/media/cat-logo.png?raw=true" width=45>oncept Annotation Tool Trainer

MedCATTrainer is an interface for building, improving and customising a given Named Entity Recognition and Linking (NER+L) model (MedCAT) for biomedical domain text.

[![Build Status](https://github.com/CogStack/cogstack-nlp/actions/workflows/medcat-trainer_qa.yml/badge.svg?branch=main)](https://github.com/CogStack/cogstack-nlp/actions/workflows/medcat-trainer_qa.yml?query=branch%3Amain)
[![Build Status](https://github.com/CogStack/cogstack-nlp/actions/workflows/medcat-trainer_release.yml/badge.svg)](https://github.com/CogStack/cogstack-nlp/actions/workflows/medcat-trainer_release.yml)
[![Documentation Status](https://readthedocs.org/projects/cogstack-nlp-medcat-trainer/badge/?version=latest)](https://readthedocs.org/projects/cogstack-nlp-medcat-trainer/badge/?version=latest)
[![Latest release](https://img.shields.io/github/v/release/CogStack/cogstack-nlp?filter=medcat-trainer/*)](https://github.com/CogStack/cogstack-nlp/releases/latest)

MedCATTrainer was presented at EMNLP/IJCNLP 2019 :tada:
[here](https://www.aclweb.org/anthology/D19-3024.pdf)

# Documentation and Discussion

Official docs available [here](https://docs.cogstack.org/projects/medcat-trainer)

If you have any questions why not reach out to the community [discourse forum here](https://discourse.cogstack.org/)

# OIDC Authentication

You can enable OIDC (OpenID Connect) authentication for the MedCAT Trainer. To do so, you must configure the following environment variables:

| Variable                                | 	Used by	Description                                 |
|-----------------------------------------|------------------------------------------------------|
| USE_OIDC                                | 	Backend	Enable OIDC login flow (true/false or 1/0). |
| VITE_USE_OIDC                           | 	Frontend                                            | 	Exposed version of USE_OIDC for Vue.|
| VITE_API_URL                            | 	Frontend                                            |	Base API URL for frontend calls.|
| VITE_KEYCLOAK_URL                       | 	Frontend                                            |	Keycloak base URL (e.g. http://keycloak.cogstack.localhost/).|
| VITE_KEYCLOAK_REALM                     | 	Frontend                                            |	Keycloak realm name.|
| VITE_KEYCLOAK_CLIENT_ID                 | 	Frontend                                            |	Keycloak client ID for this app.|
| VITE_KEYCLOAK_TOKEN_REFRESH_INTERVAL_MS | 	Frontend                                            |	Token refresh frequency in ms.|
| VITE_KEYCLOAK_TOKEN_MIN_VALIDITY_SECS   | 	Frontend                                            |	Minimum token validity before refresh.|
| VITE_LOGOUT_REDIRECT_URI                | 	Frontend                                            |	Where to send user after logout.|

You can either use the Gateway Auth stack available in cogstack-ops or deploy your own Keycloak instance.

Currently, there are two roles that can be assigned to users:
- medcattrainer_superuser: grants superuser privileges in the application.
- medcattrainer_staff: grants staff-level privileges without full superuser access.
