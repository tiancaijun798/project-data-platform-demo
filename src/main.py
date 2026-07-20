"""
project-data-platform-demo
FastAPI Application Entry Point
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Data Platform Demo",
    version="0.1.0",
    description="全栈数据平台演示项目 API",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"message": "Data Platform Demo API is running", "version": "0.1.0"}


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.get("/info")
async def info():
    return {
        "project": "project-data-platform-demo",
        "environment": "dev",
        "python_version": "3.13",
        "framework": "FastAPI",
    }
