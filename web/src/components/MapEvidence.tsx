import { Aperture, CircleDashed, Focus, GitCompare, Radio } from "lucide-react";
import maplibregl, { type GeoJSONSource } from "maplibre-gl";
import { useEffect, useRef, useState, type ReactNode } from "react";

import { Checkbox } from "@/components/ui/checkbox";
import { LAYER_LABELS } from "@/lib/constants";
import { registerMapFit } from "@/lib/map-registry";
import type { BBox, LayerId, OverlayCollection } from "@/lib/types";
import { formatLngLat } from "@/lib/utils";

type Props = {
  bounds: BBox;
  opticalUrl: string | null;
  sarUrl: string | null;
  compareUrl: string | null;
  overlays?: OverlayCollection;
  layers: Record<LayerId, boolean>;
  onLayer: (id: LayerId, on: boolean) => void;
  hasSar: boolean;
  instanceId: string;
};

const EMPTY: OverlayCollection = { type: "FeatureCollection", features: [] };

const LAYER_ICONS: Record<LayerId, ReactNode> = {
  optical: <Aperture className="size-3" />,
  sar: <Radio className="size-3" />,
  change: <GitCompare className="size-3" />,
  uncertain: <CircleDashed className="size-3" />,
};

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
  compareUrl,
  overlays,
  layers,
  onLayer,
  hasSar,
  instanceId,
}: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const [ready, setReady] = useState(false);
  const [cursor, setCursor] = useState<{ lng: number; lat: number } | null>(null);
  const [opacity, setOpacity] = useState(0.9);
  const [split, setSplit] = useState(50);

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
          { id: "bg", type: "background", paint: { "background-color": "#1A1E22" } },
          {
            id: "change-fill",
            type: "fill",
            source: "overlays",
            filter: ["==", ["get", "kind"], "change"],
            paint: { "fill-color": "#5E8F8A", "fill-opacity": 0.32 },
          },
          {
            id: "change-line",
            type: "line",
            source: "overlays",
            filter: ["==", ["get", "kind"], "change"],
            paint: { "line-color": "#5E8F8A", "line-width": 1.4 },
          },
          {
            id: "uncertain-fill",
            type: "fill",
            source: "overlays",
            filter: ["==", ["get", "kind"], "uncertain"],
            paint: { "fill-color": "#8B959E", "fill-opacity": 0.18 },
          },
          {
            id: "uncertain-line",
            type: "line",
            source: "overlays",
            filter: ["==", ["get", "kind"], "uncertain"],
            paint: { "line-color": "#8B959E", "line-width": 1.2, "line-dasharray": [2, 2] },
          },
        ],
      },
      bounds: [
        [bounds[0], bounds[1]],
        [bounds[2], bounds[3]],
      ],
      fitBoundsOptions: { padding: 16, maxZoom: 15 },
      attributionControl: false,
      scrollZoom: false,
      dragRotate: false,
      pitchWithRotate: false,
    });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false, visualizePitch: false }), "top-right");
    map.on("load", () => setReady(true));
    map.on("mousemove", (e) => setCursor({ lng: e.lngLat.lng, lat: e.lngLat.lat }));
    map.on("mouseout", () => setCursor(null));
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
      applyRaster("optical", opticalUrl, opacity);
      applyRaster("sar", sarUrl, Math.min(0.75, opacity));
    };
    if (map.isStyleLoaded()) apply();
    else map.once("load", apply);
  }, [opticalUrl, sarUrl, bounds, opacity]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const apply = () => {
      setVis(map, "optical", layers.optical);
      setVis(map, "sar", layers.sar);
      setVis(map, "change-fill", layers.change);
      setVis(map, "change-line", layers.change);
      setVis(map, "uncertain-fill", layers.uncertain);
      setVis(map, "uncertain-line", layers.uncertain);
    };
    if (map.isStyleLoaded()) apply();
    else map.once("load", apply);
  }, [layers]);

  return (
    <div className="relative mt-4 overflow-hidden rounded-xl border border-hairline" style={{ height: 480 }}>
      {!ready ? <div className="sq-shimmer pointer-events-none absolute inset-0 z-[1] bg-surface" /> : null}
      <div ref={containerRef} className="h-full w-full" />
      {compareUrl ? (
        <>
          <div
            className="pointer-events-none absolute inset-0 z-[4] overflow-hidden"
            style={{ clipPath: `inset(0 ${100 - split}% 0 0)` }}
          >
            <img src={compareUrl} alt="T2" className="h-full w-full object-cover" />
          </div>
          <div className="pointer-events-none absolute inset-y-0 z-[5] w-px bg-primary" style={{ left: `${split}%` }} />
          <div className="absolute bottom-3 left-1/2 z-10 flex -translate-x-1/2 items-center gap-2 rounded-md border border-hairline bg-surface/95 px-2 py-1 font-mono text-[10px] text-mute">
            T1
            <input
              type="range"
              min={4}
              max={96}
              value={split}
              onChange={(e) => setSplit(Number(e.target.value))}
              className="h-1 w-28 cursor-ew-resize accent-primary"
              aria-label="Compare T1 and T2"
            />
            T2
          </div>
        </>
      ) : null}
      <div className="absolute top-3 left-3 z-10 rounded-lg border border-hairline bg-surface/95 p-2.5">
        <ul className="flex flex-col gap-1.5">
          {LAYER_LABELS.map((layer) => {
            const disabled = layer.id === "sar" && !hasSar;
            return (
              <li key={layer.id} className="flex items-center gap-2">
                <Checkbox
                  checked={layers[layer.id]}
                  disabled={disabled}
                  onCheckedChange={(v) => onLayer(layer.id, v === true)}
                  id={`map-${instanceId}-${layer.id}`}
                />
                <span className="text-mute">{LAYER_ICONS[layer.id]}</span>
                <label htmlFor={`map-${instanceId}-${layer.id}`} className="text-[11px] text-ink">
                  {layer.label}
                </label>
              </li>
            );
          })}
        </ul>
        <div className="mt-2 flex items-center gap-2">
          <input
            type="range"
            min={0.2}
            max={1}
            step={0.05}
            value={opacity}
            onChange={(e) => setOpacity(Number(e.target.value))}
            className="w-full accent-primary"
            aria-label="Raster opacity"
          />
        </div>
        <button
          type="button"
          onClick={fit}
          className="text-mute hover:text-ink mt-2 inline-flex w-full items-center justify-center gap-1.5 rounded-md border border-hairline py-1 text-[11px]"
        >
          <Focus className="size-3" />
          Fit
        </button>
      </div>
      {cursor ? (
        <div className="font-mono pointer-events-none absolute bottom-3 left-3 z-10 rounded-md border border-hairline bg-surface/95 px-2 py-1 text-[10px] text-mute">
          {formatLngLat(cursor.lng, cursor.lat)}
        </div>
      ) : null}
    </div>
  );
}
