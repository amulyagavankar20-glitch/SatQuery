import maplibregl, { type GeoJSONSource } from "maplibre-gl";
import { useEffect, useMemo, useRef, useState, type PointerEvent as ReactPointerEvent } from "react";

import { sanitizeBounds } from "@/lib/geo";
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
  const safe = sanitizeBounds(bounds);
  const [west, south, east, north] = safe;
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
  const [bw, bs, be, bn] = bounds;
  const safeBounds = useMemo(() => sanitizeBounds([bw, bs, be, bn]), [bw, bs, be, bn]);
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
        [safeBounds[0], safeBounds[1]],
        [safeBounds[2], safeBounds[3]],
      ],
      { padding: 16, maxZoom: 15, duration: 450 },
    );
  };

  useEffect(() => registerMapFit(fit), [safeBounds]);

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
            paint: {
              "fill-color": ["coalesce", ["get", "fill"], ["get", "color"], "#ff3838"],
              "fill-opacity": 0.45,
            },
          },
          {
            id: "change-line",
            type: "line",
            source: "overlays",
            filter: ["==", ["get", "kind"], "change"],
            paint: {
              "line-color": ["coalesce", ["get", "stroke"], ["get", "color"], "#ff3838"],
              "line-width": 2.5,
              "line-opacity": 1,
            },
          },
          {
            id: "grounding-fill",
            type: "fill",
            source: "overlays",
            filter: ["in", ["get", "kind"], ["literal", ["grounding", "sar_detection", "detection", "mask", "water_mask", "built_mask", "tree_mask", "grass_mask", "crop_mask", "bare_mask", "flood_mask", "vegetation_mask", "lulc"]]],
            paint: {
              "fill-color": ["coalesce", ["get", "fill"], ["get", "color"], "#00f0ff"],
              "fill-opacity": 0.32,
            },
          },
          {
            id: "grounding-line",
            type: "line",
            source: "overlays",
            filter: ["in", ["get", "kind"], ["literal", ["grounding", "sar_detection", "detection", "mask", "water_mask", "built_mask", "tree_mask", "grass_mask", "crop_mask", "bare_mask", "flood_mask", "vegetation_mask", "lulc"]]],
            paint: {
              "line-color": ["coalesce", ["get", "stroke"], ["get", "color"], "#00f0ff"],
              "line-width": 2.0,
            },
          },
          {
            id: "uncertain-fill",
            type: "fill",
            source: "overlays",
            filter: ["==", ["get", "kind"], "uncertain"],
            paint: { "fill-color": "#5E8F8A", "fill-opacity": 0.18 },
          },
          {
            id: "uncertain-line",
            type: "line",
            source: "overlays",
            filter: ["==", ["get", "kind"], "uncertain"],
            paint: { "line-color": "#5E8F8A", "line-width": 2, "line-dasharray": [2, 2], "line-opacity": 1 },
          },
          {
            id: "overlay-label-change",
            type: "symbol",
            source: "overlays",
            filter: ["==", ["get", "kind"], "change"],
            layout: {
              "text-field": ["coalesce", ["get", "label"], ["get", "class"]],
              "text-size": 11,
              "text-font": ["Open Sans Regular", "Arial Unicode MS Regular"],
              "text-max-width": 10,
              "text-padding": 8,
              "text-allow-overlap": false,
              "symbol-placement": "point",
            },
            paint: {
              "text-color": "#F0F3F5",
              "text-halo-color": "#121417",
              "text-halo-width": 1.2,
            },
          },
          {
            id: "overlay-label-uncertain",
            type: "symbol",
            source: "overlays",
            filter: ["==", ["get", "kind"], "uncertain"],
            layout: {
              "text-field": ["coalesce", ["get", "label"], ["get", "class"]],
              "text-size": 11,
              "text-font": ["Open Sans Regular", "Arial Unicode MS Regular"],
              "text-max-width": 10,
              "text-padding": 8,
              "text-allow-overlap": false,
              "symbol-placement": "point",
            },
            paint: {
              "text-color": "#F0F3F5",
              "text-halo-color": "#121417",
              "text-halo-width": 1.2,
            },
          },
        ],
      },
      bounds: [
        [safeBounds[0], safeBounds[1]],
        [safeBounds[2], safeBounds[3]],
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
      map.on("click", "grounding-fill", pulseAnswer);
      map.on("mouseenter", "change-fill", () => {
        map.getCanvas().style.cursor = "pointer";
      });
      map.on("mouseleave", "change-fill", () => {
        map.getCanvas().style.cursor = "";
      });
      map.on("mouseenter", "grounding-fill", () => {
        map.getCanvas().style.cursor = "pointer";
      });
      map.on("mouseleave", "grounding-fill", () => {
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
          [safeBounds[0], safeBounds[1]],
          [safeBounds[2], safeBounds[3]],
        ],
        { padding: 16, maxZoom: 15, duration: 0 },
      );
    };
    if (map.isStyleLoaded()) apply();
    else map.once("load", apply);
  }, [overlays, safeBounds]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const applyRaster = (id: string, url: string | null, op: number, isVis: boolean) => {
      const coords = imageCoords(safeBounds);

      if (!url) {
        if (map.getLayer(id)) map.removeLayer(id);
        if (map.getSource(id)) map.removeSource(id);
        return;
      }

      const existingSource = map.getSource(id) as maplibregl.ImageSource | undefined;
      if (existingSource && typeof existingSource.updateImage === "function") {
        try {
          existingSource.updateImage({ url, coordinates: coords });
          if (map.getLayer(id)) {
            map.setLayoutProperty(id, "visibility", isVis ? "visible" : "none");
            map.setPaintProperty(id, "raster-opacity", op);
          }
          return;
        } catch {
          /* fallback to recreate */
        }
      }

      if (map.getLayer(id)) map.removeLayer(id);
      if (map.getSource(id)) map.removeSource(id);

      try {
        map.addSource(id, { type: "image", url, coordinates: coords });
        const beforeLayer = map.getLayer("change-fill")
          ? "change-fill"
          : map.getLayer("grounding-fill")
            ? "grounding-fill"
            : undefined;
        map.addLayer(
          {
            id,
            type: "raster",
            source: id,
            layout: { visibility: isVis ? "visible" : "none" },
            paint: { "raster-opacity": op, "raster-fade-duration": 0 },
          },
          beforeLayer,
        );
      } catch {
        // ignore add error
      }
    };
    const apply = () => {
      applyRaster("optical", opticalUrl, 0.95, layers.optical);
      applyRaster("sar", sarUrl, 0.75, layers.sar && hasSar);
      map.fitBounds(
        [
          [safeBounds[0], safeBounds[1]],
          [safeBounds[2], safeBounds[3]],
        ],
        { padding: 16, maxZoom: 15, duration: 250 },
      );
      map.resize();
    };
    if (map.isStyleLoaded()) apply();
    else map.once("load", apply);
  }, [opticalUrl, sarUrl, safeBounds, layers.optical, layers.sar, hasSar]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const apply = () => {
      setVis(map, "optical", layers.optical);
      setVis(map, "sar", layers.sar && hasSar);
      setVis(map, "change-fill", layers.change);
      setVis(map, "change-line", layers.change);
      setVis(map, "grounding-fill", true);
      setVis(map, "grounding-line", true);
      setVis(map, "uncertain-fill", layers.uncertain);
      setVis(map, "uncertain-line", layers.uncertain);
      setVis(map, "overlay-label-change", layers.change);
      setVis(map, "overlay-label-uncertain", layers.uncertain);
    };
    if (map.isStyleLoaded()) apply();
    else map.once("load", apply);
  }, [layers, hasSar]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !wipeUrl || !ready) return;
    const update = () => {
      const [w, s, e, n] = safeBounds;
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
  }, [wipeUrl, safeBounds, ready]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map?.getLayer("change-line")) return;
    map.setPaintProperty("change-line", "line-width", evidencePulse ? 3.0 : 2.25);
    map.setPaintProperty("change-fill", "fill-opacity", evidencePulse ? 0.48 : 0.34);
    if (map.getLayer("grounding-line")) {
      map.setPaintProperty("grounding-line", "line-width", evidencePulse ? 3.0 : 2.0);
      map.setPaintProperty("grounding-fill", "fill-opacity", evidencePulse ? 0.35 : 0.18);
    }
    map.setPaintProperty("uncertain-line", "line-width", evidencePulse ? 2.8 : 2);
    map.setPaintProperty("uncertain-fill", "fill-opacity", evidencePulse ? 0.28 : 0.18);
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
            <div className="absolute inset-y-0 left-1/2 w-px -translate-x-1/2 bg-primary" />
            <div className="sq-glass absolute top-1/2 left-1/2 h-[8px] w-[24px] -translate-x-1/2 -translate-y-1/2 rounded-sm border border-white/10" />
          </div>
        </>
      ) : null}
    </div>
  );
}
