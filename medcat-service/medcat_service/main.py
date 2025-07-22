
import uvicorn
from fastapi import FastAPI

from medcat_service.routers import health, process

app = FastAPI(
    title="MedCAT Service",
    summary="MedCAT Service Annotation API.",
    contact={
        "name": "CogStack Org",
        "url": "https://cogstack.org/",
        "email": "contact@cogstack.org",
    },
    license_info={
        "name": "Apache 2.0",
        "identifier": "Apache-2.0",
    },
)

app.include_router(health.router)
app.include_router(process.router)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
