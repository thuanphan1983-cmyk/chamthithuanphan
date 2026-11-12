import sys
import os
import traceback

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.abspath(os.path.join(current_dir, ".."))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

try:
    from main import app
except Exception as e:
    err_tb = traceback.format_exc()
    print("FATAL ERROR ON IMPORT:", err_tb)
    from fastapi import FastAPI
    from fastapi.responses import PlainTextResponse
    app = FastAPI()
    @app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
    def catch_all(path: str):
        return PlainTextResponse(f"Python Serverless Initialization Error:\n{err_tb}", status_code=500)
