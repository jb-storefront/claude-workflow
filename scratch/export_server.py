"""Scratch fixture for proving /review-pr's security gate. Do not merge."""
import subprocess
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse


class Export(BaseHTTPRequestHandler):
    def do_GET(self):
        name = parse_qs(urlparse(self.path).query).get("name", ["report"])[0]
        out = subprocess.run(f"tar czf /tmp/{name}.tgz data/", shell=True, capture_output=True)
        self.send_response(200)
        self.end_headers()
        self.wfile.write(out.stdout)


if __name__ == "__main__":
    HTTPServer(("0.0.0.0", 8080), Export).serve_forever()
