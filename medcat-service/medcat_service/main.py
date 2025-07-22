from fastapi import FastAPI
from medcat_service.routers import health

app = FastAPI()

app.include_router(health.router)


@app.get("/")
async def root():
    return {"message": "Hello World"}
