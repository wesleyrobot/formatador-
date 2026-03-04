import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import engine, Base
from .routers import upload, sessions, contacts, ml, ai

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="ContactProcessor API",
    description="Backend para processamento de planilhas de contatos",
    version="1.0.0",
)

allowed_origins = os.getenv("ALLOWED_ORIGINS", "*").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload.router, prefix="/api")
app.include_router(sessions.router, prefix="/api")
app.include_router(contacts.router, prefix="/api")
app.include_router(ml.router, prefix="/api")
app.include_router(ai.router, prefix="/api")


@app.get("/")
def root():
    return {"status": "ok", "service": "ContactProcessor API v1.0"}


@app.get("/health")
def health():
    return {"status": "healthy"}
