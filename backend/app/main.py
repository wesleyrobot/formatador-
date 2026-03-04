import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from .database import engine, Base, SessionLocal
from .models import ErrorLog
from .routers import upload, sessions, contacts, ml, ai, logs

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
app.include_router(logs.router, prefix="/api")


@app.middleware("http")
async def log_errors_middleware(request: Request, call_next):
    response = await call_next(request)
    if response.status_code >= 400:
        # Ignora health checks e OPTIONS
        if request.url.path not in ("/health", "/", "/api/health/full") and request.method != "OPTIONS":
            try:
                db = SessionLocal()
                entry = ErrorLog(
                    method=request.method,
                    endpoint=str(request.url.path),
                    status_code=response.status_code,
                    error_message=f"HTTP {response.status_code} em {request.method} {request.url.path}",
                )
                db.add(entry)
                db.commit()
                db.close()
                # Limita a 500 entradas
                db2 = SessionLocal()
                count = db2.query(ErrorLog).count()
                if count > 500:
                    oldest = db2.query(ErrorLog).order_by(ErrorLog.created_at).first()
                    if oldest:
                        db2.delete(oldest)
                        db2.commit()
                db2.close()
            except Exception:
                pass
    return response


@app.get("/")
def root():
    return {"status": "ok", "service": "ContactProcessor API v1.0"}


@app.get("/health")
def health():
    return {"status": "healthy"}
