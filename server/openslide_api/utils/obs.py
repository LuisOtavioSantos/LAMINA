# server/openslide_api/utils/obs.py
import os, sys, time, uuid, atexit, logging, faulthandler
from flask import request, g

_FMT = "%(asctime)s [%(levelname)s] pid=%(process)d %(name)s: %(message)s"

def setup_logging(log_dir: str, level=logging.DEBUG) -> None:
    os.makedirs(log_dir, exist_ok=True)
    root = logging.getLogger()
    root.setLevel(level)
    fmt = logging.Formatter(_FMT)

    if not any(isinstance(h, logging.StreamHandler) for h in root.handlers):
        ch = logging.StreamHandler(sys.stdout)
        ch.setFormatter(fmt)
        root.addHandler(ch)

    if not any(getattr(h, "_siat_file", False) for h in root.handlers):
        fh = logging.FileHandler(os.path.join(log_dir, "server.log"), encoding="utf-8")
        fh.setFormatter(fmt)
        fh._siat_file = True
        root.addHandler(fh)

def enable_crash_dumps(log_dir: str) -> None:
    os.makedirs(log_dir, exist_ok=True)
    crash_path = os.path.join(log_dir, "crash.log")
    fh = open(crash_path, "a", encoding="utf-8")
    faulthandler.enable(file=fh, all_threads=True)
    atexit.register(fh.close)

def install_request_logging(app) -> None:
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
