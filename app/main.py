from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Importar routers
from app.api.v1 import auth, recommendations, interactions, search, content, onboarding

app = FastAPI(
    title="MediaMind API",
    version="1.0.0",
    description="Motor de recomendación multimedia con IA"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registrar routers
app.include_router(auth.router, prefix="/api/v1", tags=["auth"])
app.include_router(recommendations.router, prefix="/api/v1", tags=["recommendations"])
app.include_router(interactions.router, prefix="/api/v1", tags=["interactions"])
app.include_router(search.router, prefix="/api/v1", tags=["search"])
app.include_router(content.router, prefix="/api/v1", tags=["content"])
app.include_router(onboarding.router, prefix="/api/v1", tags=["onboarding"])


@app.get("/")
async def root():
    return {
        "message": "Bienvenido a MediaMind",
        "version": "1.0.0",
        "status": "online",
        "docs": "/docs"
    }

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "services": {
            "api": "online",
            "database": "online"  # Podrías verificar la conexión
        }
    }