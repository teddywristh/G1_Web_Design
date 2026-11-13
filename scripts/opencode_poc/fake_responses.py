"""Synthetic OpenAI Responses endpoint on 127.0.0.1:9081 for latency checks; never a real provider.

The streamed answer reports the reasoning effort the request carried, so a test can see what OpenCode
really sent. Text arrives in several pieces with a short pause, like a model writing.
"""

import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
        effort = (body.get("reasoning") or {}).get("effort")
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()

        def send(event):
            self.wfile.write(f"event: {event['type']}\ndata: {json.dumps(event)}\n\n".encode())
            self.wfile.flush()

        response = {"id": "r1", "model": "m", "created_at": 0, "status": "in_progress", "output": []}
        item = {"id": "m1", "type": "message", "role": "assistant", "status": "in_progress", "content": []}
        send({"type": "response.created", "response": response})
        send({"type": "response.output_item.added", "output_index": 0, "item": item})
        send(
            {
                "type": "response.content_part.added",
                "item_id": "m1",
                "output_index": 0,
                "content_index": 0,
                "part": {"type": "output_text", "text": "", "annotations": []},
            }
        )
        pieces = ["effort=", str(effort), " ", "done"]
        for piece in pieces:
            time.sleep(0.25)
            send(
                {
                    "type": "response.output_text.delta",
                    "item_id": "m1",
                    "output_index": 0,
                    "content_index": 0,
                    "delta": piece,
                }
            )
        text = "".join(pieces)
        send({"type": "response.output_text.done", "item_id": "m1", "output_index": 0, "content_index": 0, "text": text})
        done = {**item, "status": "completed", "content": [{"type": "output_text", "text": text, "annotations": []}]}
        send({"type": "response.output_item.done", "output_index": 0, "item": done})
        usage = {
            "input_tokens": 1,
            "output_tokens": 1,
            "total_tokens": 2,
            "input_tokens_details": {"cached_tokens": 0},
            "output_tokens_details": {"reasoning_tokens": 0},
        }
        send({"type": "response.completed", "response": {**response, "status": "completed", "output": [done], "usage": usage}})


ThreadingHTTPServer(("127.0.0.1", 9081), Handler).serve_forever()
