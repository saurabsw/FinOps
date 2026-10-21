"""Entrypoint script to launch the FastAPI backend server."""
import os
import sys
import argparse
import uvicorn

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Static FinOps Analyzer FastAPI Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8001, help="Port to bind (fixed: 8001)")
    args = parser.parse_args()

    host = args.host
    port = args.port

    print("=" * 70)
    print(" Static FinOps Analyzer")
    print(" Multi-Cloud FinOps Analyzer & Safe Remediation Engine")
    print(f" Backend Server Active: http://{host}:{port}")
    print(f" Interactive OpenAPI Docs: http://{host}:{port}/docs")
    print(f" Integrated Web Dashboard: http://{host}:{port}/")
    print("=" * 70)

    uvicorn.run("backend.app.main:app", host=host, port=port, reload=True)

