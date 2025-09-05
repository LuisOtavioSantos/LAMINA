# server\openslide_api\services\openslide_tiles.py
import io
from PIL import Image
from openslide import OpenSlide
from openslide.deepzoom import DeepZoomGenerator

class OpenSlideDZ:
    def __init__(self, path: str, tile_size: int = 256, overlap: int = 0, limit_bounds: bool = True):
        self._slide = OpenSlide(path)  # pode levantar UnsupportedFormat
        self._dz = DeepZoomGenerator(self._slide, tile_size=tile_size, overlap=overlap, limit_bounds=limit_bounds)

    def dzi_xml(self, imgfmt: str = "jpeg") -> str:
        return self._dz.get_dzi(imgfmt)

    def tile_jpeg(self, level: int, col: int, row: int) -> io.BytesIO:
        img = self._dz.get_tile(level, (col, row))
        if img.mode != "RGB":
            img = img.convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=90)
        buf.seek(0)
        return buf
