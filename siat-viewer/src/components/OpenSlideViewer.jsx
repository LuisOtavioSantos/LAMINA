import React, { useEffect, useRef, useState } from "react";
import OpenSeadragon from "openseadragon";

export default function OpenSlideViewer() {
  const ref = useRef(null);
  const [err, setErr] = useState(null);

  useEffect(() => {
    let viewer;
    async function boot() {
      try {
        const res = await fetch("http://127.0.0.1:5000/osd/dzi");
        if (!res.ok) throw new Error("OpenSlide não disponível para este arquivo.");
        const dziUrl = "http://127.0.0.1:5000/osd/dzi";

        viewer = OpenSeadragon({
          id: ref.current.id,
          prefixUrl: "/openseadragon/images/",
          crossOriginPolicy: "Anonymous",
          showNavigator: true,
          tileSources: dziUrl,
        });
      } catch (e) {
        setErr(e.message);
      }
    }
    if (ref.current) boot();
    return () => viewer && viewer.destroy();
  }, []);

  if (err) return <div style={{ color: "salmon", padding: 16 }}>OpenSlide erro: {err}</div>;
  return <div id="osd-openslide" ref={ref} style={{ width: "100%", height: "100vh", background: "black" }} />;
}
