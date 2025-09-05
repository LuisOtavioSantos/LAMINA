import logging
from dataclasses import dataclass
from io import BytesIO
from math import ceil, log2
from typing import Dict, Tuple, Any

import numpy as np
from PIL import Image
from pylibCZIrw import czi as pyczi

logger = logging.getLogger("pyczi")
logger.setLevel(logging.DEBUG)  # deixe DEBUG enquanto investiga

@dataclass(frozen=True)
class CziInfo:
    width: int
    height: int
    tile_size: int
    max_level: int
    scene: int
    origin_x: int
    origin_y: int

def _unpack_rect(rect: Any):
    if rect is None:
        return None
    if hasattr(rect, "x") and hasattr(rect, "y") and hasattr(rect, "w") and hasattr(rect, "h"):
        return int(rect.x), int(rect.y), int(rect.w), int(rect.h)
    if isinstance(rect, (tuple, list)) and len(rect) == 4:
        x, y, w, h = rect
        return int(x), int(y), int(w), int(h)
    if isinstance(rect, dict):
        lower = {k.lower(): k for k in rect.keys()}
        if all(k in lower for k in ("x", "y", "w", "h")):
            return (int(rect[lower["x"]]), int(rect[lower["y"]]),
                    int(rect[lower["w"]]), int(rect[lower["h"]]))
        # também pode vir como {'X': (x0,x1), 'Y': (y0,y1)}
        KX = "X" if "X" in rect else ("x" if "x" in rect else None)
        KY = "Y" if "Y" in rect else ("y" if "y" in rect else None)
        if KX and KY:
            x0, x1 = rect[KX]
            y0, y1 = rect[KY]
            return int(x0), int(y0), int(x1 - x0), int(y1 - y0)
    raise ValueError(f"Não sei desfazer o rect: {type(rect)} -> {rect}")

class PyCziDZ:
    """
    DeepZoom tiles a partir de CZI via pylibCZIrw, com ROI clampado ao bounds da cena.
    """

    def __init__(self, path: str, tile_size: int = 512, scene: int = 0):
        self.path = path
        self.tile_size = tile_size
        self.scene = scene

        logger.info("[PyCziDZ] Abrindo CZI: %s", self.path)
        with pyczi.open_czi(self.path) as czidoc:
            scenes_attr = getattr(czidoc, "scenes_bounding_rectangle", None)
            if scenes_attr is None:
                raise RuntimeError("czidoc.scenes_bounding_rectangle ausente")
            scenes = scenes_attr if not callable(scenes_attr) else scenes_attr()

            try:
                logger.info("[PyCziDZ] Scenes disponíveis: %s", list(scenes.keys()))
            except Exception:
                logger.info("[PyCziDZ] Scenes disponíveis (tipo=%s)", type(scenes))

            rect_scene = scenes.get(scene) if isinstance(scenes, dict) else None
            if rect_scene is None:
                tbr = getattr(czidoc, "total_bounding_rectangle", None)
                if tbr is None:
                    tbb = getattr(czidoc, "total_bounding_box", None)
                    if tbb is None:
                        raise RuntimeError("Sem total_bounding_rectangle/box")
                    x, y, w, h = _unpack_rect(tbb)
                else:
                    x, y, w, h = _unpack_rect(tbr)
            else:
                x, y, w, h = _unpack_rect(rect_scene)

            logger.info("[PyCziDZ] Cena %d -> origin=(%d,%d) size=(%d x %d)", scene, x, y, w, h)

        max_dim = max(w, h)
        max_level = int(ceil(log2(max_dim)))
        logger.info("[PyCziDZ] tile_size=%d | max_dim=%d | max_level=%d", tile_size, max_dim, max_level)

        self._info = CziInfo(
            width=w, height=h,
            tile_size=tile_size,
            max_level=max_level,
            scene=scene,
            origin_x=x, origin_y=y,
        )

    # ---------- helpers ----------
    @property
    def info_dict(self) -> Dict:
        i = self._info
        return dict(width=i.width, height=i.height, tileSize=i.tile_size, maxLevel=i.max_level, scene=i.scene)

    def _scale_at_level(self, level: int) -> int:
        return 2 ** (self._info.max_level - level)

    def _level_dims(self, level: int) -> Tuple[int, int, int]:
        scale = self._scale_at_level(level)
        wL = int(ceil(self._info.width  / float(scale)))
        hL = int(ceil(self._info.height / float(scale)))
        return scale, wL, hL

    def _scene_bounds(self) -> Tuple[int, int, int, int]:
        x0 = self._info.origin_x
        y0 = self._info.origin_y
        x1 = x0 + self._info.width
        y1 = y0 + self._info.height
        return x0, y0, x1, y1

    def _tile_roi_fullres(self, level: int, col: int, row: int) -> Tuple[int, int, int, int, float]:
        T = self._info.tile_size
        scale, wL, hL = self._level_dims(level)

        u0 = col * T
        v0 = row * T
        u1 = min(u0 + T, wL)
        v1 = min(v0 + T, hL)

        tile_wL = max(0, u1 - u0)
        tile_hL = max(0, v1 - v0)
        if tile_wL <= 0 or tile_hL <= 0:
            return 0, 0, 0, 0, 1.0

        x = self._info.origin_x + u0 * scale
        y = self._info.origin_y + v0 * scale
        w = tile_wL * scale
        h = tile_hL * scale
        zoom = 1.0 / float(scale)

        logger.debug("[ROI(full)] L=%d col=%d row=%d | scale=%d | levelWH=(%d,%d) | "
                     "u0v0=(%d,%d) u1v1=(%d,%d) | full=(%d,%d,%d,%d) | zoom=%.8f",
                     level, col, row, scale, wL, hL, u0, v0, u1, v1, x, y, w, h, zoom)
        return int(x), int(y), int(w), int(h), zoom

    # ---------- public ----------
    def dzi_xml(self, imgfmt: str = "jpeg") -> str:
        i = self._info
        fmt = imgfmt.lower()
        return (
            f'<?xml version="1.0" encoding="UTF-8"?>'
            f'<Image xmlns="http://schemas.microsoft.com/deepzoom/2008" '
            f'Format="{fmt}" Overlap="0" TileSize="{i.tile_size}">'
            f'<Size Width="{i.width}" Height="{i.height}"/></Image>'
        )

    def tile_jpeg(self, level: int, col: int, row: int) -> BytesIO:
        x, y, w, h, zoom = self._tile_roi_fullres(level, col, row)
        if w <= 0 or h <= 0:
            logger.debug("[tile] ROI vazio -> tile preto")
            return self._empty_tile()

        # ---- clamp ao bounds da cena (evita segfault no nativo) ----
        sx0, sy0, sx1, sy1 = self._scene_bounds()
        rx0 = max(x, sx0)
        ry0 = max(y, sy0)
        rx1 = min(x + w, sx1)
        ry1 = min(y + h, sy1)
        w_clamp = max(0, rx1 - rx0)
        h_clamp = max(0, ry1 - ry0)

        logger.debug("[tile] full=(%d,%d,%d,%d) scene=(%d,%d,%d,%d) -> clamp=(%d,%d,%d,%d)",
                     x, y, w, h, sx0, sy0, sx1, sy1, rx0, ry0, w_clamp, h_clamp)

        if w_clamp <= 0 or h_clamp <= 0:
            logger.debug("[tile] Fora do bounds -> tile preto")
            return self._empty_tile()

        # ---- zoom mínimo para garantir pelo menos 1x1 px de saída ----
        min_zoom_w = 1.0 / float(max(w_clamp, 1))
        min_zoom_h = 1.0 / float(max(h_clamp, 1))
        zoom_safe = max(zoom, min_zoom_w, min_zoom_h)
        if zoom_safe != zoom:
            logger.debug("[tile] zoom ajustado: %.8f -> %.8f", zoom, zoom_safe)
            zoom = zoom_safe

        # ---- leitura segura ----
        with pyczi.open_czi(self.path) as czidoc:
            arr = czidoc.read(
                roi=(int(rx0), int(ry0), int(w_clamp), int(h_clamp)),
                scene=self._info.scene,
                plane={'C': 0},
                pixel_type='Bgr24',
                zoom=zoom
            )

        if arr.size == 0:
            logger.debug("[tile] array vazio -> tile preto")
            return self._empty_tile()

        try:
            logger.debug("[tile] shape=%s dtype=%s min=%.1f max=%.1f",
                         arr.shape, arr.dtype, float(arr.min()), float(arr.max()))
        except ValueError:
            logger.debug("[tile] shape=%s dtype=%s (sem min/max)", arr.shape, arr.dtype)

        # BGR -> RGB; não redimensionar (bordas menores são OK)
        rgb = arr[..., ::-1].copy()
        img = Image.fromarray(rgb, mode="RGB")

        buf = BytesIO()
        img.save(buf, format="JPEG", quality=90)
        buf.seek(0)
        return buf

    def _empty_tile(self) -> BytesIO:
        img = Image.new("RGB", (self._info.tile_size, self._info.tile_size), color=(0, 0, 0))
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=80)
        buf.seek(0)
        return buf

    def debug_tile(self, level: int, col: int, row: int):
        T = self._info.tile_size
        scale, wL, hL = self._level_dims(level)
        u0, v0 = col * T, row * T
        u1, v1 = min(u0 + T, wL), min(v0 + T, hL)
        tile_wL = max(0, u1 - u0)
        tile_hL = max(0, v1 - v0)
        x = self._info.origin_x + u0 * scale
        y = self._info.origin_y + v0 * scale
        w = tile_wL * scale
        h = tile_hL * scale
        zoom = 1.0 / float(scale)
        sx0, sy0, sx1, sy1 = self._scene_bounds()
        return {
            "level": level, "col": col, "row": row,
            "level_dims": {"wL": wL, "hL": hL, "scale": scale},
            "tile_level_rect": {"u0": u0, "v0": v0, "u1": u1, "v1": v1},
            "full_res_roi": {"x": x, "y": y, "w": w, "h": h},
            "scene_bounds": {"x0": sx0, "y0": sy0, "x1": sx1, "y1": sy1},
            "zoom": zoom,
            "tile_px_nominal": self._info.tile_size,
            "origin": [self._info.origin_x, self._info.origin_y],
            "image_wh": [self._info.width, self._info.height],
        }
