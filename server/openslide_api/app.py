# server/openslide_api/app.py
import os
import sys
import time
import uuid
import logging
import faulthandler
from flask import Flask, jsonify, send_file, make_response, request, g
from flask_cors import CORS

from services.pyczi_tiles import PyCziDZ
from services.openslide_tiles import OpenSlideDZ

BASE_DIR = os.path.dirname(__file__)
LOG_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] pid=%(process)d %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join(LOG_DIR, "server.log"), encoding="utf-8"),
    ],
)

_crash_fh = open(os.path.join(LOG_DIR, "crash.log"), "a", encoding="utf-8")
faulthandler.enable(file=_crash_fh, all_threads=True)

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": ["http://localhost:5173", "http://127.0.0.1:5173"]}})

SLIDE_PATH = os.path.join(BASE_DIR, "slides", "slide_one.czi")
app.logger.info(f"Iniciando API. PID={os.getpid()} SLIDE={SLIDE_PATH}")

@app.before_request
def _start_timer():
    g.req_id = request.headers.get("X-Request-ID", str(uuid.uuid4())[:8])
    g.t0 = time.time()
    app.logger.info(f"[{g.req_id}] --> {request.method} {request.path} args={dict(request.args)}")

@app.after_request
def _log_response(resp):
    try:
        dt = (time.time() - getattr(g, "t0", time.time())) * 1000.0
        rid = getattr(g, "req_id", "-")
        resp.headers["X-Request-ID"] = rid
        size = resp.calculate_content_length()
        app.logger.info(f"[{rid}] <-- {resp.status_code} {request.method} {request.path} {dt:.1f}ms bytes={size}")
    except Exception:
        app.logger.exception("Falha ao logar resposta")
    return resp

@app.teardown_request
def _teardown(exc):
    if exc:
        app.logger.exception(f"[{getattr(g,'req_id','-')}] exceção no request", exc_info=exc)

@app.get("/osd/dzi")
def osd_dzi():
    try:
        dz = OpenSlideDZ(SLIDE_PATH, tile_size=256, overlap=0, limit_bounds=True)
        xml = dz.dzi_xml("jpeg")
        resp = make_response(xml)
        resp.headers["Content-Type"] = "application/xml"
        return resp
    except Exception as e:
        app.logger.exception("Erro em /osd/dzi")
        return jsonify({"error": str(e)}), 422

@app.get("/osd/tile/<int:level>/<int:col>_<int:row>.jpeg")
def osd_tile(level, col, row):
    try:
        dz = OpenSlideDZ(SLIDE_PATH, tile_size=256, overlap=0, limit_bounds=True)
        buf = dz.tile_jpeg(level, col, row)
        return send_file(buf, mimetype="image/jpeg")
    except Exception as e:
        app.logger.exception("Erro em /osd/tile")
        return jsonify({"error": str(e)}), 422

_py = PyCziDZ(SLIDE_PATH, tile_size=512, scene=0)

@app.get("/czirw/info")
def czirw_info():
    return jsonify(_py.info_dict)

@app.get("/czirw/dzi")
def czirw_dzi():
    xml = _py.dzi_xml("jpeg")
    resp = make_response(xml)
    resp.headers["Content-Type"] = "application/xml"
    return resp

@app.get("/czirw/tile/<int:level>/<int:col>_<int:row>.jpeg")
def czirw_tile(level, col, row):
    try:
        dbg = _py.debug_tile(level, col, row)
        app.logger.debug(f"[czirw/tile] L={level} col={col} row={row} dbg={dbg}")

        buf = _py.tile_jpeg(level, col, row)
        return send_file(buf, mimetype="image/jpeg")
    except Exception as e:
        app.logger.exception("Erro em /czirw/tile")
        return jsonify({"error": str(e)}), 500

@app.get("/czirw/debug/<int:level>/<int:col>_<int:row>")
def czirw_debug(level, col, row):
    return jsonify(_py.debug_tile(level, col, row))

@app.get("/healthz")
def healthz():
    return {"status": "ok", "pid": os.getpid()}

@app.get("/")
def home():
    return {"status": "ok", "file": SLIDE_PATH, "pid": os.getpid()}

if __name__ == "__main__":
    app.logger.info("Subindo Flask sem reloader…")
    app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)
