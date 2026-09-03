import { forwardRef, useEffect, useImperativeHandle, useRef } from "react";
import maplibregl, { type GeoJSONSource } from "maplibre-gl";
import type { JobView } from "@/lib/schema";

type FeatureCollection = {
  type: "FeatureCollection";
  features: Array<{
    type: "Feature";
    properties: { tag?: string };
    geometry: { type: "Polygon"; coordinates: number[][][] };
  }>;
};

const EMPTY: FeatureCollection = { type: "FeatureCollection", features: [] };
const AOI_LAYERS = ["aoi-glow", "aoi-fill", "aoi-line"];
const RASTER_LAYER = "scene-raster";
const RASTER_SOURCE = "scene";

function boundsToFeature(bounds: number[], tag: string): FeatureCollection["features"][number] {
  const [minx, miny, maxx, maxy] = bounds;
  return {
    type: "Feature",
    properties: { tag },
    geometry: {
      type: "Polygon",
      coordinates: [[[minx, miny], [maxx, miny], [maxx, maxy], [minx, maxy], [minx, miny]]],
    },
  };
}

function imageCoords(bounds: number[]): [[number, number], [number, number], [number, number], [number, number]] {
  const [west, south, east, north] = bounds;
  return [
    [west, north],
    [east, north],
    [east, south],
    [west, south],
  ];
}

function sceneTag(index: number, total: number) {
  if (total < 2) return "SCN";
  return index === 0 ? "T1" : "T2";
}

export type EvidenceMapHandle = {
  fit: () => void;
};

export const EvidenceMap = forwardRef<
  EvidenceMapHandle,
  {
    job: JobView | null;
    footprintOn: boolean;
    rasterOn: boolean;
    rasterOpacity: number;
    rasterUrl: string | null;
    onCursor: (pos: { lng: number; lat: number } | null) => void;
    onZoom: (zoom: number) => void;
  }
>(function EvidenceMap({ job, footprintOn, rasterOn, rasterOpacity, rasterUrl, onCursor, onZoom }, ref) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const markersRef = useRef<maplibregl.Marker[]>([]);
  const boundsRef = useRef<number[] | null>(null);
  const jobRef = useRef(job);
  const onCursorRef = useRef(onCursor);
  const onZoomRef = useRef(onZoom);
  jobRef.current = job;
  onCursorRef.current = onCursor;
  onZoomRef.current = onZoom;

  const boundsKey = (job?.assets ?? [])
    .map((a) => (a.bounds_wgs84 ?? []).join(","))
    .join("|");

  const fit = () => {
    const map = mapRef.current;
    const box = boundsRef.current;
    if (!map || !box) return;
    map.fitBounds(
      [
        [box[0], box[1]],
        [box[2], box[3]],
      ],
      { padding: 72, duration: 650, maxZoom: 12 },
    );
  };

  useImperativeHandle(ref, () => ({ fit }), []);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: {
        version: 8,
        sources: {
          carto: {
            type: "raster",
            tiles: ["https://basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png"],
            tileSize: 256,
            attribution: "© CARTO © OSM",
          },
          footprint: { type: "geojson", data: EMPTY },
        },
        layers: [
          { id: "carto", type: "raster", source: "carto" },
          {
            id: "aoi-glow",
            type: "line",
            source: "footprint",
            paint: { "line-color": "#f0842a", "line-width": 10, "line-opacity": 0.18, "line-blur": 6 },
          },
          {
            id: "aoi-fill",
            type: "fill",
            source: "footprint",
            paint: { "fill-color": "#f0842a", "fill-opacity": 0.12 },
          },
          {
            id: "aoi-line",
            type: "line",
            source: "footprint",
            paint: { "line-color": "#ffb056", "line-width": 1.6, "line-opacity": 0.95 },
          },
        ],
      },
      center: [78.96, 21.77],
      zoom: 4.2,
      attributionControl: { compact: true },
    });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    map.addControl(new maplibregl.ScaleControl({ maxWidth: 112, unit: "metric" }), "bottom-right");
    map.on("mousemove", (e) => onCursorRef.current({ lng: e.lngLat.lng, lat: e.lngLat.lat }));
    map.on("mouseout", () => onCursorRef.current(null));
    map.on("zoom", () => onZoomRef.current(map.getZoom()));
    map.on("load", () => onZoomRef.current(map.getZoom()));
    mapRef.current = map;
    return () => {
      for (const m of markersRef.current) m.remove();
      markersRef.current = [];
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const vis = footprintOn ? "visible" : "none";
    const applyVis = () => {
      for (const id of AOI_LAYERS) {
        if (map.getLayer(id)) map.setLayoutProperty(id, "visibility", vis);
      }
    };
    if (map.isStyleLoaded()) applyVis();
    else map.once("load", applyVis);
  }, [footprintOn]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const assets = jobRef.current?.assets ?? [];
    const features: FeatureCollection["features"] = [];
    for (const [i, asset] of assets.entries()) {
      const b = asset.bounds_wgs84;
      if (b && b.length === 4) features.push(boundsToFeature(b, sceneTag(i, assets.length)));
    }
    const data: FeatureCollection = { type: "FeatureCollection", features };
    const box = assets.find((a) => a.bounds_wgs84 && a.bounds_wgs84.length === 4)?.bounds_wgs84 ?? null;
    boundsRef.current = box;
    const apply = () => {
      const source = map.getSource("footprint") as GeoJSONSource | undefined;
      source?.setData(data);
      for (const m of markersRef.current) m.remove();
      markersRef.current = [];
      for (const [i, asset] of assets.entries()) {
        const b = asset.bounds_wgs84;
        if (!b || b.length !== 4) continue;
        const el = document.createElement("div");
        el.className = "sq-aoi-tag";
        el.textContent = sceneTag(i, assets.length);
        const marker = new maplibregl.Marker({ element: el, anchor: "bottom" })
          .setLngLat([(b[0] + b[2]) / 2, b[3]])
          .addTo(map);
        markersRef.current.push(marker);
      }
      if (box) {
        map.fitBounds(
          [
            [box[0], box[1]],
            [box[2], box[3]],
          ],
          { padding: 72, duration: 700, maxZoom: 11 },
        );
      }
    };
    if (map.isStyleLoaded()) apply();
    else map.once("load", apply);
  }, [boundsKey]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const box = boundsRef.current;
    const apply = () => {
      if (map.getLayer(RASTER_LAYER)) map.removeLayer(RASTER_LAYER);
      if (map.getSource(RASTER_SOURCE)) map.removeSource(RASTER_SOURCE);
      if (!rasterUrl || !box || box.length !== 4) return;
      map.addSource(RASTER_SOURCE, {
        type: "image",
        url: rasterUrl,
        coordinates: imageCoords(box),
      });
      map.addLayer(
        {
          id: RASTER_LAYER,
          type: "raster",
          source: RASTER_SOURCE,
          paint: { "raster-opacity": rasterOpacity, "raster-fade-duration": 0 },
        },
        "aoi-glow",
      );
      map.setLayoutProperty(RASTER_LAYER, "visibility", rasterOn ? "visible" : "none");
    };
    if (map.isStyleLoaded()) apply();
    else map.once("load", apply);
  }, [rasterUrl, rasterOn, boundsKey]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map?.getLayer(RASTER_LAYER)) return;
    map.setPaintProperty(RASTER_LAYER, "raster-opacity", rasterOpacity);
    map.setLayoutProperty(RASTER_LAYER, "visibility", rasterOn ? "visible" : "none");
  }, [rasterOpacity, rasterOn]);

  return <div ref={containerRef} className="h-full w-full" />;
});
