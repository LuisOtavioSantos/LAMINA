# server/openslide_api/app.py
import os
import logging
from flask import Flask, jsonify, send_file, make_response
from flask_cors import CORS

from services.pyczi_tiles import PyCziDZ
from services.openslide_tiles import OpenSlideDZ

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": ["http://localhost:5173", "http://127.0.0.1:5173"]}})

BASE_DIR = os.path.dirname(__file__)
SLIDE_PATH = os.path.join(BASE_DIR, "slides", "slide_one.czi")

# ---------- OpenSlide (vai dar 422 se não suportar seu CZI) ----------
@app.get("/osd/dzi")
def osd_dzi():
    try:
        dz = OpenSlideDZ(SLIDE_PATH, tile_size=256, overlap=0, limit_bounds=True)
        xml = dz.dzi_xml("jpeg")
        resp = make_response(xml)
        resp.headers["Content-Type"] = "application/xml"
        return resp
    except Exception as e:
        return jsonify({"error": str(e)}), 422

@app.get("/osd/tile/<int:level>/<int:col>_<int:row>.jpeg")
def osd_tile(level, col, row):
    try:
        dz = OpenSlideDZ(SLIDE_PATH, tile_size=256, overlap=0, limit_bounds=True)
        buf = dz.tile_jpeg(level, col, row)
        return send_file(buf, mimetype="image/jpeg")
    except Exception as e:
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
    buf = _py.tile_jpeg(level, col, row)
    return send_file(buf, mimetype="image/jpeg")

@app.get("/czirw/debug/<int:level>/<int:col>_<int:row>")
def czirw_debug(level, col, row):
    return jsonify(_py.debug_tile(level, col, row))

@app.get("/")
def home():
    return {"status": "ok", "file": SLIDE_PATH}

if __name__ == "__main__":
    app.run(port=5000, debug=True)
