from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import models so SQLAlchemy registers them before create_all
import app.models.user  # noqa: F401
import app.models.transaction  # noqa: F401

from app.database import Base, engine
from app.routers import auth, transactions, analytics, users


def create_app() -> FastAPI:
    application = FastAPI(
        title="Finance Tracker API",
        description=(
            "A RESTful backend for managing personal finance records.\n\n"
            "**Roles & Permissions:**\n"
            "- `viewer` — read transactions + summary\n"
            "- `analyst` — viewer + filters + full analytics\n"
            "- `admin` — full access including create/update/delete and user management\n\n"
            "Use `/auth/login` to obtain a Bearer token, then click **Authorize** above."
        ),
        version="1.0.0",
        contact={"name": "Finance Tracker"},
        license_info={"name": "MIT"},
    )

    # Allow all origins for development; tighten this in production
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Create all tables on startup (safe no-op if they already exist)
    Base.metadata.create_all(bind=engine)

    # Register routers
    application.include_router(auth.router)
    application.include_router(transactions.router)
    application.include_router(analytics.router)
    application.include_router(users.router)

    @application.get("/", tags=["Health"], summary="Root")
    def root():
        return {
            "message": "Finance Tracker API is running",
            "docs": "/docs",
            "redoc": "/redoc",
        }

    @application.get("/health", tags=["Health"], summary="Health check")
    def health():
        return {"status": "healthy"}

    return application


app = create_app()