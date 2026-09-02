import { useEffect, useRef } from "react";
import maplibregl, { type GeoJSONSource } from "maplibre-gl";
import type { JobView } from "@/lib/schema";

type FeatureCollection = {
  type: "FeatureCollection";
  features: Array<{
    type: "Feature";
    properties: Record<string, never>;
    geometry: { type: "Polygon"; coordinates: number[][][] };
  }>;
};

const EMPTY: FeatureCollection = { type: "FeatureCollection", features: [] };
const AOI_LAYERS = ["aoi-glow", "aoi-fill", "aoi-line"];

function boundsToFeature(bounds: number[]): FeatureCollection["features"][number] {
  const [minx, miny, maxx, maxy] = bounds;
  return {
    type: "Feature",
    properties: {},
    geometry: {
      type: "Polygon",
      coordinates: [[[minx, miny], [maxx, miny], [maxx, maxy], [minx, maxy], [minx, miny]]],
    },
  };
}

export function EvidenceMap({
  job,
  footprintOn,
  onCursor,
  onZoom,
}: {
  job: JobView | null;
  footprintOn: boolean;
  onCursor: (pos: { lng: number; lat: number } | null) => void;
  onZoom: (zoom: number) => void;
}) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const onCursorRef = useRef(onCursor);
  const onZoomRef = useRef(onZoom);
  onCursorRef.current = onCursor;
  onZoomRef.current = onZoom;

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
            paint: { "fill-color": "#f0842a", "fill-opacity": 0.16 },
          },
          {
            id: "aoi-line",
            type: "line",
            source: "footprint",
            paint: { "line-color": "#ffb056", "line-width": 2, "line-opacity": 0.95 },
          },
        ],
      },
      center: [78.96, 21.77],
      zoom: 4.2,
      attributionControl: { compact: true },
    });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    map.on("mousemove", (e) => onCursorRef.current({ lng: e.lngLat.lng, lat: e.lngLat.lat }));
    map.on("mouseout", () => onCursorRef.current(null));
    map.on("zoom", () => onZoomRef.current(map.getZoom()));
    map.on("load", () => onZoomRef.current(map.getZoom()));
    mapRef.current = map;
    return () => {
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
    const features: FeatureCollection["features"] = [];
    for (const asset of job?.assets ?? []) {
      const b = asset.bounds_wgs84;
      if (b && b.length === 4) features.push(boundsToFeature(b));
    }
    const data: FeatureCollection = { type: "FeatureCollection", features };
    const apply = () => {
      const source = map.getSource("footprint") as GeoJSONSource | undefined;
      source?.setData(data);
      const box = job?.assets.find((a) => a.bounds_wgs84)?.bounds_wgs84;
      if (box && box.length === 4) {
        map.fitBounds(
          [
            [box[0], box[1]],
            [box[2], box[3]],
          ],
          { padding: 64, duration: 700, maxZoom: 11 },
        );
      }
    };
    if (map.isStyleLoaded()) apply();
    else map.once("load", apply);
  }, [job]);

  return <div ref={containerRef} className="h-full w-full" />;
}
