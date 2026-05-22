from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import health, predict, socios

app = FastAPI(
    title=settings.app_name,
    description="API de perfilamiento transaccional y riesgo de mora - CoopTech Tulcán",
    version="1.0.0",
)

origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if origins != ["*"] else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api = FastAPI()
prefix = settings.api_prefix

app.include_router(health.router, prefix=prefix)
app.include_router(predict.router, prefix=prefix)
app.include_router(socios.router, prefix=prefix)


@app.get("/")
def root():
    return {
        "message": "CoopTech Mora API",
        "docs": "/docs",
        "health": f"{prefix}/health",
    }
