from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
def setup_cors(app: FastAPI) -> None:
    origins = [
        "http://localhost:3000",
        "https://your-production-domain.com",
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
        allow_headers=["Authorization", "Content-Type"],
        max_age=3600,
    )