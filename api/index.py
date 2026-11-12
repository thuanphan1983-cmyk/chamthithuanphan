import sys
import os
import urllib.parse

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.abspath(os.path.join(current_dir, ".."))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from main import app as fastapi_app

class VercelFastAPIWrapper:
    """
    ASGI Wrapper khôi phục chính xác route và query parameters
    từ tham số __path__ mà Vercel rewrite truyền sang.
    """
    def __init__(self, inner_app):
        self.inner_app = inner_app

    async def __call__(self, scope, receive, send):
        if scope.get("type") == "http":
            raw_qs = scope.get("query_string", b"").decode("utf-8", errors="ignore")
            if "__path__=" in raw_qs:
                params = urllib.parse.parse_qs(raw_qs, keep_blank_values=True)
                if "__path__" in params and params["__path__"]:
                    orig_path = params.pop("__path__")[0]
                    scope["path"] = orig_path
                    # Tạo lại query string sạch không còn __path__
                    clean_pairs = []
                    for k, vals in params.items():
                        for v in vals:
                            clean_pairs.append(f"{urllib.parse.quote(k)}={urllib.parse.quote(v)}")
                    scope["query_string"] = "&".join(clean_pairs).encode("utf-8")

        await self.inner_app(scope, receive, send)

app = VercelFastAPIWrapper(fastapi_app)
