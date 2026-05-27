# Extending Medcat Service

## spaCy models

When using MedCAT for a different language than English, it can be useful to use a different spaCy model. A spaCy model can be included in the MedCAT model pack, but when not using this functionality, it can be useful to install models in the Docker image. This can be done by setting a build-time variable. See the `SPACY_MODELS` variable in [Dockerfile](https://github.com/CogStack/cogstack-nlp/blob/e5827a806c100abafb7c5a70f917d560fdfc374c/medcat-service/Dockerfile) for default value and usage.