#!/usr/bin/env python3
"""A stand-in for the SGLang server, for exercising the engine without a GPU.

It answers the two endpoints the client uses. Each request holds one of --slots
execution slots for --ms-per-token milliseconds per generated token, which is
enough to make the schedulers' relative parallelism visible. Timings from this
server say nothing about real inference performance.
"""
import argparse
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    slots = None
    ms_per_token = 0.0

    def log_message(self, *args):
        pass

    def reply(self, payload):
        body = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self.reply({"model_path": "fake/model"})

    def do_POST(self):
        request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        tokens = request["sampling_params"].get("max_new_tokens") or 1
        with self.slots:
            if self.ms_per_token:
                time.sleep(tokens * self.ms_per_token / 1000)
        self.reply({"text": "x " * tokens, "meta_info": {"prompt_tokens": 0, "completion_tokens": tokens}})


class Server(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 512


def serve(port=30000, slots=8, ms_per_token=0.0):
    handler = type("ConfiguredHandler", (Handler,), {
        "slots": threading.BoundedSemaphore(slots),
        "ms_per_token": ms_per_token,
    })
    return Server(("127.0.0.1", port), handler)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=30000)
    parser.add_argument("--slots", type=int, default=8)
    parser.add_argument("--ms-per-token", type=float, default=0.0)
    args = parser.parse_args()
    serve(args.port, args.slots, args.ms_per_token).serve_forever()
