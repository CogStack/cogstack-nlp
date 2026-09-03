"""Zero-dependency mock OpenAI-compatible chat endpoint for exercising
MyLLMNER end-to-end without a real LLM, an API key, or internet access.

Speaks the same shape as `POST {base_url}/chat/completions` that the
`openai` SDK sends and Ollama/vLLM/etc. accept - point the component
straight at it, same as you'd point it at a real local server:

    cnf = LLMNERConfig(base_url="http://localhost:8009", model="whatever")
    # OpenAI() appends "/chat/completions" itself, given base_url above

Run:
    python mock_llm_server.py

It string-matches a small fixed vocabulary against whatever text you
send it and returns CSV matching MyLLMNER's prompt contract, wrapped
in a chat-completion response envelope. It also deliberately nudges
one match's offsets off by 2 characters so you can watch
`_get_real_start_end`'s reconciliation (trust_llm_span=False) correct
it - useful to confirm that path actually works, not just the happy
path.

This mock only implements the freeform path (what MyLLMNER uses). It
ignores `response_format` if sent, so it won't exercise MyLLMLinker's
structured-output path yet - extend `Handler.do_POST` if/when you need
that (return a JSON body matching the requested schema instead of the
CSV string).

When you're ready to point this at a real local server instead: same
config, just change `base_url` - e.g. `http://localhost:11434/v1` for
Ollama, or wherever your institute's server lives.
"""
from __future__ import annotations

import json
import re
import time
from contextlib import contextmanager
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from medcat.components.types import CoreComponentType

VOCAB = [
    "diabetes", "hypertension", "metformin",
    "chest pain", "aspirin", "kidney disease",
    "kidney failure"
]


def _fake_ner_extract(text: str) -> str:
    rows = ["entity,start,end"]
    for i, term in enumerate(VOCAB):
        for m in re.finditer(re.escape(term), text, re.IGNORECASE):
            start, end = m.start(), m.end()
            if i == 0:  # deliberately mangle the first term's offsets
                start, end = start + 2, end + 2
            rows.append(f"{text[m.start():m.end()]},{start},{end}")
    return "\n".join(rows)


def _fake_linking_return(text: str) -> str:
    # just always this one, whatever for now
    return "C01"


class NERHandler(BaseHTTPRequestHandler):

    def _get_fake_response(self, text: str) -> str:
        return _fake_ner_extract(text)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length).decode("utf-8")
        payload = json.loads(raw)
        messages = payload.get("messages", [])
        prompt = messages[-1]["content"] if messages else ""

        text = prompt.split("TEXT:\n", 1)[-1]
        content = self._get_fake_response(text)

        response = {
            "id": "chatcmpl-mock",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": payload.get("model", "mock"),
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }],
        }
        body = json.dumps(response).encode("utf-8")

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass  # keep test output quiet


class LinkingHandler(NERHandler):

    def _get_fake_response(self, text: str) -> str:
        return _fake_linking_return(text)


@contextmanager
def mock_llm_server(
    mock_for: CoreComponentType = CoreComponentType.ner,
    host: str = "localhost", port: int = 8009
):
    """Context manager to run the mock LLM server in a background thread."""
    handler = NERHandler if mock_for == CoreComponentType.ner else LinkingHandler
    server = HTTPServer((host, port), handler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)

    # Start the server in the background
    server_thread.start()
    print(f"Mock OpenAI-compatible endpoint started on http://{host}:{port}")

    try:
        yield server
    finally:
        # Shut down the server gracefully when exiting the `with` block
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=2)
        print("Mock OpenAI-compatible endpoint stopped.")


if __name__ == "__main__":
    server = HTTPServer(("localhost", 8009), NERHandler)
    print("Mock OpenAI-compatible endpoint on http://localhost:8009 (Ctrl+C to stop)")
    server.serve_forever()
