import sys
import os
import traceback

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.abspath(os.path.join(current_dir, ".."))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

try:
    from main import app as fastapi_app
    
    class VercelPathMiddleware:
        def __init__(self, inner_app):
            self.inner_app = inner_app

        async def __call__(self, scope, receive, send):
            if scope["type"] == "http":
                headers = dict(scope.get("headers", []))
                # Vercel đặt đường dẫn gốc trong x-matched-path hoặc x-now-route-matches
                matched_path = headers.get(b"x-matched-path", b"").decode("utf-8")
                if matched_path:
                    if "?" in matched_path:
                        matched_path = matched_path.split("?")[0]
                    scope["path"] = matched_path
            await self.inner_app(scope, receive, send)

    app = VercelPathMiddleware(fastapi_app)

except Exception as e:
    err_tb = traceback.format_exc()
    print("FATAL ERROR ON IMPORT:", err_tb)
    from fastapi import FastAPI
    from fastapi.responses import PlainTextResponse
    app = FastAPI()
    @app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
    def catch_all(path: str):
        return PlainTextResponse(f"Python Serverless Initialization Error:\n{err_tb}", status_code=500)
