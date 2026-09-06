"""Local, sequential JSON API following the repository's /api/... route convention."""
import argparse
import json
from http.server import BaseHTTPRequestHandler, HTTPServer

from .config import ROOT
from .llm_provider import OpenAIProvider
from .product_agent import ProductSearchAgent


def handler_for(agent):
    images = {p[modality]["image_id"]: ROOT / p[modality]["path"] for p in agent.tools.catalog
              for modality in ("index_image", "query_image") if p.get(modality)}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # Do not log request contents or credentials.

        def respond(self, status, payload):
            body = json.dumps(payload, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            if self.path != "/api/agent/search":
                return self.respond(404, {"error": "Unknown route"})
            # This is a local CLI/demo service, not an authenticated production endpoint.
            if self.headers.get("Origin") or self.headers.get_content_type() != "application/json":
                return self.respond(403, {"error": "Use a local JSON API client; browser-origin requests are disabled"})
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= 8192:
                    return self.respond(413, {"error": "JSON body must be between 1 and 8192 bytes"})
                body = json.loads(self.rfile.read(size))
                if not isinstance(body, dict) or set(body) - {"query", "image", "debug"}:
                    raise ValueError("Invalid request schema")
                if "debug" in body and type(body["debug"]) is not bool:
                    raise ValueError("debug must be a boolean")
                image = body.get("image")
                if image is not None and (not isinstance(image, str) or image not in images):
                    raise ValueError("image must be an ABO image_id registered in the catalog")
                result = agent.run(body.get("query"), images[image] if image else None)
                fields = ("status", "answer", "recommendations", "comparison", "limitations", "latency", "error")
                response = {field: result[field] for field in fields}
                if body.get("debug"):
                    response.update({field: result[field] for field in ("plan", "tool_trace", "grounding", "raw_output")})
                self.respond(502 if result["status"] == "error" else 200, response)
            except (ValueError, TypeError):
                self.respond(400, {"error": "Invalid query, image ID, or request schema"})

    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8067)
    parser.add_argument("--cache-only", action="store_true")
    args = parser.parse_args()
    agent = ProductSearchAgent(provider=OpenAIProvider(cache_only=args.cache_only))
    server = HTTPServer(("127.0.0.1", args.port), handler_for(agent))
    print(f"Product Search Agent: http://127.0.0.1:{args.port}/api/agent/search", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        agent.tools.close()


if __name__ == "__main__":
    main()
