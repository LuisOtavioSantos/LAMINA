import React, { useEffect, useLayoutEffect, useRef, useState } from "react";
import OpenSeadragon from "openseadragon";

export default function CzirwViewer() {
  const wrapperRef = useRef(null);
  const canvasRef  = useRef(null);
  const [err, setErr] = useState(null);
  const [readySize, setReadySize] = useState(false);

  useLayoutEffect(() => {
    const el = wrapperRef.current;
    if (!el) return;
    const check = () => {
      const r = el.getBoundingClientRect();
      const ok = r.width > 50 && r.height > 50;
      setReadySize(ok);
      if (!ok) {
        console.warn("[OSD] wrapper sem tamanho visível:", r);
      }
    };
    check();
    // re-checa quando a janela muda
    const ro = new ResizeObserver(check);
    ro.observe(el);
    window.addEventListener("load", check);
    return () => { ro.disconnect(); window.removeEventListener("load", check); };
  }, []);

  useEffect(() => {
    if (!readySize || !canvasRef.current) return;
    let v;
    (async () => {
      try {
        const r = await fetch("http://127.0.0.1:5000/czirw/info");
        if (!r.ok) throw new Error("Falha em /czirw/info");
        const { width, height, tileSize, maxLevel } = await r.json();
        console.log("CZIrw info:", { width, height, tileSize, maxLevel });

        v = OpenSeadragon({
          element: canvasRef.current,                 // elemento com tamanho > 0
          prefixUrl: "https://openseadragon.github.io/openseadragon/images/",
          crossOriginPolicy: "Anonymous",
          showNavigator: true,
          debugMode: false,
          imageLoaderLimit: 8,
          timeout: 60000,
          visibilityRatio: 1.0,
          immediateRender: true,
          minZoomImageRatio: 0.05,
          maxZoomPixelRatio: 2,
          tileSources: {
            width, height,
            tileSize,
            tileOverlap: 0,
            minLevel: 0,
            maxLevel,
            getTileUrl(level, x, y) {
              return `http://127.0.0.1:5000/czirw/tile/${level}/${x}_${y}.jpeg`;
            },
          },
        });

        v.addHandler("open", () => {
          const item = v.world.getItemAt(0);
          // garante que aparece
          if (item) v.viewport.fitBounds(item.getBounds(), true);
        });

        v.addHandler("tile-load-failed", (e) => {
          const url = typeof e.tile.getUrl === "function" ? e.tile.getUrl() : e.tile.url;
          console.warn("tile fail:", url);
        });
      } catch (e) {
        setErr(e.message);
      }
    })();

    return () => v && v.destroy();
  }, [readySize]);

  if (err) return <div style={{ color: "salmon", padding: 16 }}>CZIrw erro: {err}</div>;

  return (
    <div
      ref={wrapperRef}
      style={{
        position: "absolute", inset: 0,
        minHeight: 300,
        background: "#111",
      }}
    >
      <div
        ref={canvasRef}
        // OSD precisa de área positiva
        style={{ position: "absolute", inset: 0 }}
      />
    </div>
  );
}
