# Deidentify app

Demo for AnonCAT. It uses [MedCAT](https://github.com/CogStack/cogstack-nlp/tree/main/medcat-v1), an advanced natural language processing tool, to identify and classify sensitive information, such as names, addresses, and medical terms.

## Example

## Features
- Redact sensitive information: The Deidentify app can automatically redact sensitive information from a document, replacing it with a placeholder value, such as "[REDACTED]".
- Replace sensitive information: Alternatively, the app can replace sensitive information with a different value, such as a random name or address, to maintain the structure and context of the original document.
- Add customizable rules: The app allows users to create custom rules for identifying and classifying sensitive information based on their specific needs and use cases.
- Batch processing: The app can process multiple documents at once, making it easy to redact or replace sensitive information in large datasets.
  
## DeID Model
 *For out of the box models please contact: contact@cogstack.org*

Models configured in .env
 `../models/` mounted into the container under `/home/models/` 
```bash
MODEL_NAME = '<NAME OF MODEL HERE.zip>'
```


### Build your own model

To build your own models please follow the tutorials outlined in [MedCATtutorials](https://github.com/CogStack/cogstack-nlp/tree/main/medcat-v1-tutorials)

*__Note:__ This is currently under development*

## Starting the demo service

Start the Docker services by using `docker-compose`. This will build the necessary Docker images and start the services.
```bash
docker-compose up
```

