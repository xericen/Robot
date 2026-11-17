"""Serve the installed Viser client and its bounded binary HTTP transport."""
import json
from pathlib import Path
import re
import urllib.request
import flask

parts = flask.request.path.split("/warehouse-viewer/", 1)[-1].split("/")
token = parts[0]
if not re.fullmatch(r"[a-f0-9]{32}", token):
    wiz.response.abort(404)
root = Path(wiz.project.path()) / "warehouse-collision-avoidance"
folder = root / "results/live" / token
try:
    status = json.loads((folder / "status.json").read_text())
except (OSError, ValueError):
    wiz.response.abort(404)
try:
    if len(parts) == 1:
        target = "http://127.0.0.1:" + str(int(status["port"])) + "/"
        with urllib.request.urlopen(target, timeout=5) as upstream:
            html = upstream.read().decode()
        endpoint = "/warehouse-viewer/" + token + "/bridge"
        shim = (root / "viewer_transport.js").read_text().replace("__WAREHOUSE_ENDPOINT__", json.dumps(endpoint))
        html = html.replace("<head>", "<head><script>" + shim + "</script>", 1)
        response = flask.Response(html, content_type="text/html; charset=utf-8")
    else:
        if parts[1] != "bridge" or len(parts) not in (3, 4) or parts[2] not in ("open", "poll", "send", "close"):
            raise ValueError("invalid transport path")
        if len(parts) == 4 and not re.fullmatch(r"[a-f0-9]{32}", parts[3]):
            raise ValueError("invalid connection")
        if flask.request.method != "POST":
            wiz.response.abort(405)
        if flask.request.content_length and flask.request.content_length > 2 * 1024 * 1024:
            wiz.response.abort(413)
        target = "http://127.0.0.1:" + str(int(status["transport_port"])) + "/" + "/".join(parts[2:])
        request = urllib.request.Request(target, data=flask.request.get_data(), method="POST")
        with urllib.request.urlopen(request, timeout=5) as upstream:
            response = flask.Response(upstream.read(), content_type="application/json")
except (OSError, ValueError, KeyError):
    wiz.response.abort(503)
response.headers["Cache-Control"] = "no-store"
response.headers["Referrer-Policy"] = "same-origin"
wiz.response.response(response)
