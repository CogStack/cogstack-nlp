# Installation

Medcat Service can be run using helm or docker compose

The recommended approach is using helm

## Helm installation

Bring up medcat service with one line using helm

```
helm install medcat-service-helm oci://registry-1.docker.io/cogstacksystems/medcat-service-helm
```

See [medcat-service-helm](https://docs.cogstack.org/en/latest/platform/deployment/helm/charts/medcat-service-helm/) for the full documentation of how to use this chart.

## Docker compose

You also can bring up medcat service using docker compose with an example like this:


```yaml
name: cogstack-medcat-service
services:
  medcat-service:
    image: cogstacksystems/medcat-service:${IMAGE_TAG-latest}
    restart: unless-stopped
    environment:
      # Uses a preloaded model pack example inside the image
      - APP_MEDCAT_MODEL_PACK=/cat/models/examples/example-medcat-v2-model-pack.zip
      - APP_ENABLE_METRICS=True
      - APP_ENABLE_DEMO_UI=True
    ports:
      - "5555:5000"
```

You can now access medcat service on `localhost:5555`

See the other examples and scenarios for running medcat service on [cogstack-nlp github](https://github.com/CogStack/cogstack-nlp/tree/main/medcat-service/docker)

