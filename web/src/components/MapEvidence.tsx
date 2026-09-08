import maplibregl, { type GeoJSONSource } from "maplibre-gl";
import { useEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from "react";

import { registerMapFit } from "@/lib/map-registry";
import type { BBox, LayerId, OverlayCollection } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useConsole } from "@/state/console";

type Props = {
  bounds: BBox;
  opticalUrl: string | null;
  sarUrl: string | null;
  wipeUrl: string | null;
  overlays?: OverlayCollection;
  layers: Record<LayerId, boolean>;
  hasSar: boolean;
  t1Date?: string | null;
  t2Date?: string | null;
  fill?: boolean;
};

const EMPTY: OverlayCollection = { type: "FeatureCollection", features: [] };

function imageCoords(bounds: BBox): [[number, number], [number, number], [number, number], [number, number]] {
  const [west, south, east, north] = bounds;
  return [
    [west, north],
    [east, north],
    [east, south],
    [west, south],
  ];
}

function setVis(map: maplibregl.Map, id: string, on: boolean) {
  if (map.getLayer(id)) map.setLayoutProperty(id, "visibility", on ? "visible" : "none");
}

export function MapEvidence({
  bounds,
  opticalUrl,
  sarUrl,
  wipeUrl,
  overlays,
  layers,
  hasSar,
  t1Date,
  t2Date,
  fill,
}: Props) {
  const { evidencePulse, setAnswerFocus } = useConsole();
  const boxRef = useRef<HTMLDivElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const [ready, setReady] = useState(false);
  const [split, setSplit] = useState(50);
  const [frame, setFrame] = useState<{ left: number; top: number; width: number; height: number } | null>(null);
  const frameRef = useRef(frame);
  frameRef.current = frame;

  const fit = () => {
    const map = mapRef.current;
    if (!map) return;
    map.fitBounds(
      [
        [bounds[0], bounds[1]],
        [bounds[2], bounds[3]],
      ],
      { padding: 16, maxZoom: 15, duration: 450 },
    );
  };

  useEffect(() => registerMapFit(fit), [bounds]);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: {
        version: 8,
        glyphs: "https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf",
        sources: {
          overlays: { type: "geojson", data: EMPTY },
        },
        layers: [
          { id: "bg", type: "background", paint: { "background-color": "#121417" } },
          {
            id: "change-fill",
            type: "fill",
            source: "overlays",
            filter: ["==", ["get", "kind"], "change"],
            paint: { "fill-color": "#5E8F8A", "fill-opacity": 0.22 },
          },
          {
            id: "change-line",
            type: "line",
            source: "overlays",
            filter: ["==", ["get", "kind"], "change"],
            paint: { "line-color": "#5E8F8A", "line-width": 1.5 },
          },
          {
            id: "uncertain-fill",
            type: "fill",
            source: "overlays",
            filter: ["==", ["get", "kind"], "uncertain"],
            paint: { "fill-color": "#5E8F8A", "fill-opacity": 0.1 },
          },
          {
            id: "uncertain-line",
            type: "line",
            source: "overlays",
            filter: ["==", ["get", "kind"], "uncertain"],
            paint: { "line-color": "#5E8F8A", "line-width": 1.5, "line-dasharray": [2, 2] },
          },
        ],
      },
      bounds: [
        [bounds[0], bounds[1]],
        [bounds[2], bounds[3]],
      ],
      fitBoundsOptions: { padding: 16, maxZoom: 15 },
      attributionControl: false,
      scrollZoom: true,
      dragRotate: false,
      pitchWithRotate: false,
    });
    map.on("load", () => {
      map.resize();
      setReady(true);
      const pulseAnswer = () => {
        setAnswerFocus(true);
        document.getElementById("sq-answer")?.scrollIntoView({ behavior: "smooth", block: "center" });
        document.getElementById("sq-trace")?.scrollIntoView({ behavior: "smooth", block: "nearest" });
      };
      map.on("click", "change-fill", pulseAnswer);
      map.on("click", "uncertain-fill", pulseAnswer);
      map.on("mouseenter", "change-fill", () => {
        map.getCanvas().style.cursor = "pointer";
      });
      map.on("mouseleave", "change-fill", () => {
        map.getCanvas().style.cursor = "";
      });
    });
    mapRef.current = map;

    const ro = new ResizeObserver(() => map.resize());
    ro.observe(containerRef.current);

    return () => {
      ro.disconnect();
      map.remove();
      mapRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const apply = () => {
      const src = map.getSource("overlays") as GeoJSONSource | undefined;
      src?.setData(overlays ?? EMPTY);
      map.fitBounds(
        [
          [bounds[0], bounds[1]],
          [bounds[2], bounds[3]],
        ],
        { padding: 16, maxZoom: 15, duration: 0 },
      );
    };
    if (map.isStyleLoaded()) apply();
    else map.once("load", apply);
  }, [overlays, bounds]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const applyRaster = (id: string, url: string | null, op: number) => {
      if (map.getLayer(id)) map.removeLayer(id);
      if (map.getSource(id)) map.removeSource(id);
      if (!url) return;
      map.addSource(id, { type: "image", url, coordinates: imageCoords(bounds) });
      map.addLayer(
        {
          id,
          type: "raster",
          source: id,
          paint: { "raster-opacity": op, "raster-fade-duration": 0 },
        },
        "change-fill",
      );
    };
    const apply = () => {
      applyRaster("optical", opticalUrl, 0.92);
      applyRaster("sar", sarUrl, 0.72);
      map.resize();
    };
    if (map.isStyleLoaded()) apply();
    else map.once("load", apply);
  }, [opticalUrl, sarUrl, bounds]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const apply = () => {
      setVis(map, "optical", layers.optical);
      setVis(map, "sar", layers.sar && hasSar);
      setVis(map, "change-fill", layers.change);
      setVis(map, "change-line", layers.change);
      setVis(map, "uncertain-fill", layers.uncertain);
      setVis(map, "uncertain-line", layers.uncertain);
    };
    if (map.isStyleLoaded()) apply();
    else map.once("load", apply);
  }, [layers, hasSar]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !wipeUrl || !ready) return;
    const update = () => {
      const [w, s, e, n] = bounds;
      const tl = map.project([w, n]);
      const br = map.project([e, s]);
      setFrame({ left: tl.x, top: tl.y, width: Math.max(1, br.x - tl.x), height: Math.max(1, br.y - tl.y) });
    };
    update();
    map.on("move", update);
    map.on("zoom", update);
    map.on("resize", update);
    return () => {
      map.off("move", update);
      map.off("zoom", update);
      map.off("resize", update);
    };
  }, [wipeUrl, bounds, ready]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map?.getLayer("change-line")) return;
    map.setPaintProperty("change-line", "line-width", evidencePulse ? 2.6 : 1.5);
    map.setPaintProperty("change-fill", "fill-opacity", evidencePulse ? 0.38 : 0.22);
    map.setPaintProperty("uncertain-line", "line-width", evidencePulse ? 2.4 : 1.5);
    map.setPaintProperty("uncertain-fill", "fill-opacity", evidencePulse ? 0.22 : 0.1);
  }, [evidencePulse]);

  const moveSplit = (clientX: number) => {
    const box = boxRef.current;
    const fr = frameRef.current;
    if (!box) return;
    const rect = box.getBoundingClientRect();
    if (fr) {
      const next = ((clientX - rect.left - fr.left) / fr.width) * 100;
      setSplit(Math.min(96, Math.max(4, next)));
      return;
    }
    const next = ((clientX - rect.left) / rect.width) * 100;
    setSplit(Math.min(96, Math.max(4, next)));
  };

  const onHandlePointer = (e: ReactPointerEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.currentTarget.setPointerCapture(e.pointerId);
    moveSplit(e.clientX);
  };

  return (
    <div
      ref={boxRef}
      className={cn("relative overflow-hidden", fill ? "h-full min-h-0" : "mt-4 h-[480px] rounded-xl border border-hairline")}
    >
      {!ready ? <div className="sq-shimmer pointer-events-none absolute inset-0 z-[1] bg-surface" /> : null}
      <div ref={containerRef} className="h-full w-full" />
      {wipeUrl && frame ? (
        <>
          <div
            className="pointer-events-none absolute z-[4] overflow-hidden"
            style={{
              left: frame.left,
              top: frame.top,
              width: frame.width,
              height: frame.height,
              clipPath: `inset(0 0 0 ${split}%)`,
            }}
          >
            <img src={wipeUrl} alt="" className="h-full w-full object-fill" />
          </div>
          <p
            className="pointer-events-none absolute z-[7] font-mono text-[10px] text-mute tabular-nums"
            style={{
              top: frame.top + frame.height - 22,
              right: `calc(100% - ${frame.left + (split / 100) * frame.width}px + 10px)`,
            }}
          >
            T1{t1Date ? `: ${t1Date}` : ""}
          </p>
          <p
            className="pointer-events-none absolute z-[7] font-mono text-[10px] text-mute tabular-nums"
            style={{
              top: frame.top + frame.height - 22,
              left: frame.left + (split / 100) * frame.width + 10,
            }}
          >
            T2{t2Date ? `: ${t2Date}` : ""}
          </p>
          <div
            className="absolute z-[6] w-4 -translate-x-1/2 cursor-ew-resize touch-none select-none"
            style={{
              left: frame.left + (split / 100) * frame.width,
              top: frame.top,
              height: frame.height,
            }}
            onPointerDown={onHandlePointer}
            onPointerMove={(e) => {
              if (!e.currentTarget.hasPointerCapture(e.pointerId)) return;
              moveSplit(e.clientX);
            }}
            role="slider"
            aria-label="T1 T2 wipe"
            aria-valuemin={4}
            aria-valuemax={96}
            aria-valuenow={Math.round(split)}
            tabIndex={0}
            onKeyDown={(e) => {
              if (e.key === "ArrowLeft") setSplit((s) => Math.max(4, s - 2));
              if (e.key === "ArrowRight") setSplit((s) => Math.min(96, s + 2));
            }}
          >
            <div className="absolute inset-y-0 left-1/2 w-px -translate-x-1/2 bg-primary/70 shadow-[0_0_8px_rgba(94,143,138,0.5)]" />
            <div className="sq-glass absolute top-1/2 left-1/2 flex h-7 w-4 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full border border-primary/40 bg-surface/90 shadow-[0_2px_10px_rgba(0,0,0,0.5),0_0_8px_rgba(94,143,138,0.3)] transition-transform duration-150 hover:scale-110">
              <div className="flex gap-0.5">
                <span className="h-2.5 w-0.5 rounded-full bg-primary/80" />
                <span className="h-2.5 w-0.5 rounded-full bg-primary/80" />
              </div>
            </div>
          </div>
        </>
      ) : null}
    </div>
  );
}
