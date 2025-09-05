# server\openslide_api\services\pyczi_tiles.py
import logging
from dataclasses import dataclass
from io import BytesIO
from math import ceil, log2
from typing import Dict, Tuple, Any

import numpy as np
from PIL import Image
from pylibCZIrw import czi as pyczi

logger = logging.getLogger("pyczi")
logger.setLevel(logging.INFO)


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
        
        
        KX = "X" if "X" in rect else ("x" if "x" in rect else None)
        KY = "Y" if "Y" in rect else ("y" if "y" in rect else None)
        if KX and KY:
            x0, x1 = rect[KX]
            y0, y1 = rect[KY]
            return int(x0), int(y0), int(x1 - x0), int(y1 - y0)
    raise ValueError(f"Não sei desfazer o rect: {type(rect)} -> {rect}")


class PyCziDZ:
    """
    Gera tiles DeepZoom on-the-fly a partir de CZI via pylibCZIrw.
    **Importante**: o ROI por nível é calculado no espaço "reduzido" e mapeado ao full-res.
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
        max_level = int(ceil(log2(max_dim)))  # níveis 0..max_level
        logger.info("[PyCziDZ] tile_size=%d | max_dim=%d | max_level=%d", tile_size, max_dim, max_level)

        self._info = CziInfo(
            width=w, height=h,
            tile_size=tile_size,
            max_level=max_level,
            scene=scene,
            origin_x=x, origin_y=y,
        )

    @property
    def info_dict(self) -> Dict:
        i = self._info
        return dict(width=i.width, height=i.height, tileSize=i.tile_size, maxLevel=i.max_level, scene=i.scene)

    def _scale_at_level(self, level: int) -> int:
        return 2 ** (self._info.max_level - level)

    def _level_dims(self, level: int) -> Tuple[int, int, int]:
        """
        Retorna (scale, width_L, height_L) onde width_L/height_L são dimensões na
        resolução do nível (após dividir pelo 'scale').
        """
        scale = self._scale_at_level(level)
        wL = int(ceil(self._info.width  / float(scale)))
        hL = int(ceil(self._info.height / float(scale)))
        return scale, wL, hL

    def _tile_roi_fullres(self, level: int, col: int, row: int) -> Tuple[int, int, int, int, float]:
        """
        Calcula ROI no full-res a partir do retângulo do tile no espaço do nível.
        - No nível L, a imagem tem (wL x hL).
        - O tile (col,row) cobre [u0:u1]x[v0:v1] em coords do nível.
        - Mapeamos (u,v) -> (x,y) no full-res multiplicando por 'scale'.
        """
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

        logger.debug(
            "[ROI] L=%d col=%d row=%d | scale=%d | levelWH=(%d,%d) | u0v0=(%d,%d) u1v1=(%d,%d) | full=(%d,%d,%d,%d) | zoom=%.8f",
            level, col, row, scale, wL, hL, u0, v0, u1, v1, x, y, w, h, zoom
        )
        return int(x), int(y), int(w), int(h), zoom

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
            return self._empty_tile()

        with pyczi.open_czi(self.path) as czidoc:
            arr = czidoc.read(
                roi=(x, y, w, h),
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
            logger.debug("[tile] shape=%s dtype=%s (min/max indisponível)", arr.shape, arr.dtype)

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
        return {
            "level": level, "col": col, "row": row,
            "level_dims": {"wL": wL, "hL": hL, "scale": scale},
            "tile_level_rect": {"u0": u0, "v0": v0, "u1": u1, "v1": v1},
            "full_res_roi": {"x": x, "y": y, "w": w, "h": h},
            "zoom": zoom,
            "tile_px_nominal": self._info.tile_size,
            "origin": [self._info.origin_x, self._info.origin_y],
            "image_wh": [self._info.width, self._info.height],
        }
