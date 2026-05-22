from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import health, predict, socios, upload

app = FastAPI(
    title=settings.app_name,
    description="API de perfilamiento transaccional y riesgo de mora - CoopTech Tulcán",
    version="1.0.0",
)

_raw_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
_use_wildcard = not _raw_origins or _raw_origins == ["*"]

# credentials=True + allow_origins=["*"] rompe el fetch en el navegador (CORS)
if _use_wildcard:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_raw_origins,
        allow_origin_regex=r"https://.*\.vercel\.app",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

prefix = settings.api_prefix

app.include_router(health.router, prefix=prefix)
app.include_router(predict.router, prefix=prefix)
app.include_router(socios.router, prefix=prefix)
app.include_router(upload.router, prefix=prefix)


@app.get("/")
def root():
    return {
        "message": "CoopTech Mora API",
        "docs": "/docs",
        "health": f"{prefix}/health",
    }
