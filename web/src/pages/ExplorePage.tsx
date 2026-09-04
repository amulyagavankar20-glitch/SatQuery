import { Link, useNavigate } from "@tanstack/react-router";
import { ArrowRight, Upload } from "lucide-react";
import maplibregl from "maplibre-gl";
import { useEffect, useRef, useState } from "react";

import { AppHeader } from "@/components/AppHeader";
import { Footer } from "@/components/Footer";
import { Button } from "@/components/ui/button";
import { DEMOS, type DemoScene } from "@/lib/demos";
import type { DemoId } from "@/lib/types";
import { useConsole } from "@/state/console";

function imageCoords(bounds: number[]): [[number, number], [number, number], [number, number], [number, number]] {
  const [west, south, east, north] = bounds;
  return [
    [west, north],
    [east, north],
    [east, south],
    [west, south],
  ];
}

export function ExplorePage() {
  const { loadDemo, dragging, onDragEnter, onDragLeave, onDrop } = useConsole();
  const navigate = useNavigate();
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const [selected, setSelected] = useState<DemoId>("coastal");
  const demo = DEMOS.find((d) => d.id === selected) ?? DEMOS[1];

  const ask = (id: DemoId) => {
    loadDemo(id);
    void navigate({ to: "/" });
  };

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: {
        version: 8,
        sources: {
          gray: {
            type: "raster",
            tiles: [
              "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}",
            ],
            tileSize: 256,
            attribution: "© Esri",
          },
        },
        layers: [{ id: "gray", type: "raster", source: "gray", paint: { "raster-opacity": 0.7 } }],
      },
      attributionControl: false,
      dragRotate: false,
      pitchWithRotate: false,
    });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    mapRef.current = map;

    const onPick = (id: DemoId) => setSelected(id);

    map.on("load", () => {
      for (const scene of DEMOS) {
        const bounds = scene.slots[0]?.bounds;
        if (!bounds) continue;
        const src = `scene-${scene.id}`;
        map.addSource(src, { type: "image", url: scene.thumb, coordinates: imageCoords(bounds) });
        map.addLayer({
          id: src,
          type: "raster",
          source: src,
          paint: { "raster-opacity": 0.92, "raster-fade-duration": 0 },
        });
        map.addSource(`box-${scene.id}`, {
          type: "geojson",
          data: {
            type: "Feature",
            properties: { id: scene.id },
            geometry: {
              type: "Polygon",
              coordinates: [[
                [bounds[0], bounds[1]],
                [bounds[2], bounds[1]],
                [bounds[2], bounds[3]],
                [bounds[0], bounds[3]],
                [bounds[0], bounds[1]],
              ]],
            },
          },
        });
        map.addLayer({
          id: `line-${scene.id}`,
          type: "line",
          source: `box-${scene.id}`,
          paint: { "line-color": "#5E8F8A", "line-width": 1.4, "line-opacity": 0.85 },
        });
        const el = document.createElement("button");
        el.type = "button";
        el.className = "sq-explore-pin";
        el.textContent = scene.title;
        el.addEventListener("click", () => onPick(scene.id));
        new maplibregl.Marker({ element: el, anchor: "bottom" })
          .setLngLat([(bounds[0] + bounds[2]) / 2, bounds[3]])
          .addTo(map);
      }
      const all = DEMOS.flatMap((s) => s.slots[0]?.bounds ?? []);
      if (all.length >= 4) {
        const lons = DEMOS.map((s) => s.slots[0]!.bounds[0]).concat(DEMOS.map((s) => s.slots[0]!.bounds[2]));
        const lats = DEMOS.map((s) => s.slots[0]!.bounds[1]).concat(DEMOS.map((s) => s.slots[0]!.bounds[3]));
        map.fitBounds(
          [
            [Math.min(...lons), Math.min(...lats)],
            [Math.max(...lons), Math.max(...lats)],
          ],
          { padding: { top: 72, left: 72, bottom: 72, right: 360 }, maxZoom: 10, duration: 0 },
        );
      }
    });

    const ro = new ResizeObserver(() => map.resize());
    ro.observe(containerRef.current);
    return () => {
      ro.disconnect();
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map?.isStyleLoaded()) return;
    for (const scene of DEMOS) {
      const id = `line-${scene.id}`;
      if (map.getLayer(id)) {
        map.setPaintProperty(id, "line-width", scene.id === selected ? 2.2 : 1.2);
        map.setPaintProperty(id, "line-opacity", scene.id === selected ? 1 : 0.55);
      }
    }
  }, [selected]);

  return (
    <div
      className="relative flex h-dvh flex-col bg-background"
      onDragEnter={(e) => {
        e.preventDefault();
        onDragEnter();
      }}
      onDragOver={(e) => e.preventDefault()}
      onDragLeave={() => onDragLeave()}
      onDrop={(e) => {
        e.preventDefault();
        onDrop(Array.from(e.dataTransfer.files));
        void navigate({ to: "/" });
      }}
    >
      <AppHeader />
      <div className="relative min-h-0 flex-1">
        <div ref={containerRef} className="h-full w-full" />
        <aside className="absolute top-3 right-3 bottom-3 z-10 flex w-[min(320px,calc(100%-2rem))] flex-col overflow-hidden rounded-xl border border-hairline bg-[#1A1E22]">
          <SceneCard demo={demo} onAsk={() => ask(demo.id)} />
          <ul className="sq-scroll border-t border-hairline p-2">
            {DEMOS.map((scene) => (
              <li key={scene.id}>
                <button
                  type="button"
                  onClick={() => setSelected(scene.id)}
                  className={`flex w-full items-center gap-2.5 rounded-lg px-2 py-2 text-left ${
                    scene.id === selected ? "bg-raised" : "hover:bg-raised/50"
                  }`}
                >
                  <img src={scene.thumb} alt="" className="size-9 rounded-md object-cover" />
                  <span className="min-w-0">
                    <span className="block truncate text-[13px] text-ink">{scene.title}</span>
                    <span className="block truncate text-[11px] text-mute">{scene.place}</span>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </aside>
      </div>
      <Footer hint="Drop a GeoTIFF or PNG onto the map to analyse it." />
      {dragging ? (
        <div className="sq-enter pointer-events-none absolute inset-0 z-50 grid place-items-center bg-background/80">
          <div className="flex items-center gap-3 rounded-xl border border-primary px-8 py-6 text-[15px] text-primary">
            <Upload className="size-5" />
            Drop to analyse in the console
          </div>
        </div>
      ) : null}
    </div>
  );
}

function SceneCard({ demo, onAsk }: { demo: DemoScene; onAsk: () => void }) {
  return (
    <div className="p-3">
      <img src={demo.thumb} alt="" className="h-36 w-full rounded-lg object-cover" />
      <h1 className="mt-3 text-[15px] font-medium text-ink">{demo.title}</h1>
      <p className="mt-1 text-[12px] text-mute">{demo.place}</p>
      <p className="mt-2 text-[13px] leading-relaxed text-mute">{demo.blurb}</p>
      <Button type="button" className="mt-4 w-full" onClick={onAsk}>
        Ask this scene
        <ArrowRight className="size-4" />
      </Button>
      <Link to="/" className="text-mute mt-2 block text-center text-[12px] hover:text-ink">
        Back to console
      </Link>
    </div>
  );
}
