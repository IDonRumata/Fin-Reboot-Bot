"""
HTTP API сервер для интеграции с n8n.
Запуск: python api_server.py (порт 8000)

Endpoints:
  POST /generate          - генерировать контент для темы
  POST /generate/auto     - выбрать тему автоматически и сгенерировать
  GET  /topics            - список всех тем
  GET  /health            - проверка доступности
"""
import json
import asyncio
import logging
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

from gemini_generator import ContentGenerator
from config import get_pushup_stats

logging.basicConfig(level=logging.INFO, format="%(asctime)s [API] %(message)s")
logger = logging.getLogger(__name__)


def _json_response(handler, status: int, data: dict):
    body = json.dumps(data, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


class GraFinAPIHandler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        logger.info("%s - %s", self.address_string(), format % args)

    def do_GET(self):
        path = urlparse(self.path).path

        if path == "/health":
            _json_response(self, 200, {"status": "ok", "service": "grafin-api"})

        elif path == "/topics":
            gen = ContentGenerator()
            topics = [{"id": t["id"], "title": t.get("topic", t.get("title", "")), "series": t.get("series", "")}
                      for t in gen.topics]
            _json_response(self, 200, {"topics": topics, "count": len(topics)})

        else:
            _json_response(self, 404, {"error": "Not found"})

    def do_POST(self):
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length", 0))
        body = {}
        if length:
            try:
                body = json.loads(self.rfile.read(length).decode("utf-8"))
            except Exception:
                _json_response(self, 400, {"error": "Invalid JSON"})
                return

        if path == "/generate":
            topic_id = body.get("topic_id")
            if not topic_id:
                _json_response(self, 400, {"error": "topic_id required"})
                return
            self._run_generate(topic_id)

        elif path == "/generate/auto":
            # Автоматически выбираем следующую тему по расписанию
            gen = ContentGenerator()
            topic_id = gen.get_next_topic_id()
            if not topic_id:
                _json_response(self, 500, {"error": "No topic available"})
                return
            self._run_generate(topic_id)

        elif path == "/pushup":
            stats = get_pushup_stats()
            _json_response(self, 200, stats)

        else:
            _json_response(self, 404, {"error": "Not found"})

    def _run_generate(self, topic_id: str):
        try:
            gen = ContentGenerator()
            logger.info("Generating content for topic: %s", topic_id)
            package = gen.generate_full_content_package(topic_id)
            _json_response(self, 200, {
                "status": "ok",
                "topic_id": topic_id,
                "topic": package.get("topic", ""),
                "tiktok_script": package.get("tiktok_script", ""),
                "grafin_post": package.get("grafin_post", ""),
                "instagram_caption": package.get("instagram_caption", ""),
                "ab_hooks": package.get("ab_hooks", ""),
            })
        except ValueError as e:
            _json_response(self, 404, {"error": str(e)})
        except Exception as e:
            logger.error("Generation error: %s", e)
            _json_response(self, 500, {"error": str(e)})


def run(port: int = 8000):
    server = HTTPServer(("127.0.0.1", port), GraFinAPIHandler)
    logger.info("GraFin API server started on http://127.0.0.1:%d", port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("API server stopped")


if __name__ == "__main__":
    run()
