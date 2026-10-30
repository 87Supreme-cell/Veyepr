from threading import Thread
from urllib.request import urlopen

from http.server import ThreadingHTTPServer

from ai_observability.app import PipelineRequestHandler
from ai_observability.router import LocalStreamPipeline


def test_console_and_triolingo_pages_are_served() -> None:
    handler = type(
        "TestPipelineRequestHandler",
        (PipelineRequestHandler,),
        {"pipeline": LocalStreamPipeline()},
    )
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        port = server.server_port
        with urlopen(f"http://127.0.0.1:{port}/") as response:
            page = response.read().decode("utf-8")
            assert response.headers["Content-Type"].startswith("text/html")
        with urlopen(f"http://127.0.0.1:{port}/triolingo") as response:
            triolingo = response.read().decode("utf-8")

        assert "VEYEPR" in page
        assert "Triolingo" in page
        assert "Three" in triolingo
    finally:
        server.shutdown()
        server.server_close()

