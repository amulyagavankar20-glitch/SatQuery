import { useNavigate } from "@tanstack/react-router";
import { ArrowRight, Upload } from "lucide-react";
import maplibregl from "maplibre-gl";
import { useEffect, useRef, useState } from "react";

import { AppHeader } from "@/components/AppHeader";
import { DemoThumb } from "@/components/DemoThumb";
import { Footer } from "@/components/Footer";
import { Grain } from "@/components/Grain";
import { Button } from "@/components/ui/button";
import { DEMOS, type DemoScene } from "@/lib/demos";
import {
  bboxFromCorners,
  bboxPolygon,
  bestSceneForBox,
  cropScenePng,
  sceneUnderPoint,
} from "@/lib/geo";
import type { DemoId } from "@/lib/types";
import { cn } from "@/lib/utils";
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

const EMPTY_BOX = bboxPolygon([0, 0, 0, 0]);

export function ExplorePage() {
  const { loadDemo, attachFiles, dragging, onDragEnter, onDragLeave, onDrop, toast } = useConsole();
  const navigate = useNavigate();
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const selectModeRef = useRef(false);
  const dragStartRef = useRef<{ lng: number; lat: number } | null>(null);
  const openFullRef = useRef<(id: DemoId) => void>(() => {});
  const sendCropRef = useRef<(box: ReturnType<typeof bboxFromCorners>) => Promise<void>>(async () => {});
  const [selected, setSelected] = useState<DemoId>("coastal");
  const [selectMode, setSelectMode] = useState(false);
  const demo = DEMOS.find((d) => d.id === selected) ?? DEMOS[1]!;

  selectModeRef.current = selectMode;

  const openFull = (id: DemoId) => {
    loadDemo(id);
    void navigate({ to: "/console", search: { scene: id } });
  };

  const sendCrop = async (box: ReturnType<typeof bboxFromCorners>) => {
    const match = bestSceneForBox(DEMOS, box);
    if (!match) {
      toast("No scene in that box", "bad");
      return;
    }
    setSelectMode(false);
    if (match.coverage >= 0.8) {
      openFull(match.demo.id);
      return;
    }
    try {
      const file = await cropScenePng(match.demo, match.hit);
      if (!file) {
        toast("Could not crop that portion", "bad");
        return;
      }
      attachFiles([file], match.hit);
      void navigate({ to: "/console" });
    } catch {
      toast("Could not crop that portion", "bad");
    }
  };

  openFullRef.current = openFull;
  sendCropRef.current = sendCrop;

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
          box: { type: "geojson", data: EMPTY_BOX },
        },
        layers: [
          { id: "gray", type: "raster", source: "gray", paint: { "raster-opacity": 0.55 } },
          {
            id: "box-fill",
            type: "fill",
            source: "box",
            paint: { "fill-color": "#5E8F8A", "fill-opacity": 0.16 },
          },
          {
            id: "box-line",
            type: "line",
            source: "box",
            paint: { "line-color": "#5E8F8A", "line-width": 1 },
          },
        ],
      },
      attributionControl: false,
      dragRotate: false,
      pitchWithRotate: false,
    });
    mapRef.current = map;

    const onPick = (id: DemoId) => setSelected(id);

    map.on("load", () => {
      for (const scene of DEMOS) {
        const bounds = scene.slots[0]?.bounds;
        if (!bounds) continue;
        const src = `scene-${scene.id}`;
        map.addSource(src, { type: "image", url: scene.thumb, coordinates: imageCoords(bounds) });
        map.addLayer(
          {
            id: src,
            type: "raster",
            source: src,
            paint: { "raster-opacity": 0.92, "raster-fade-duration": 0 },
          },
          "box-fill",
        );
        map.addSource(`box-${scene.id}`, {
          type: "geojson",
          data: bboxPolygon(bounds),
        });
        map.addLayer(
          {
            id: `line-${scene.id}`,
            type: "line",
            source: `box-${scene.id}`,
            paint: { "line-color": "#5E8F8A", "line-width": 1.2, "line-opacity": 0.55 },
          },
          "box-fill",
        );
        const el = document.createElement("button");
        el.type = "button";
        el.className = "sq-explore-pin";
        el.textContent = scene.title;
        el.addEventListener("click", (ev) => {
          ev.stopPropagation();
          onPick(scene.id);
        });
        el.addEventListener("dblclick", (ev) => {
          ev.stopPropagation();
          openFullRef.current(scene.id);
        });
        new maplibregl.Marker({ element: el, anchor: "bottom" })
          .setLngLat([(bounds[0] + bounds[2]) / 2, bounds[3]])
          .addTo(map);
      }
      const lons = DEMOS.map((s) => s.slots[0]!.bounds[0]).concat(DEMOS.map((s) => s.slots[0]!.bounds[2]));
      const lats = DEMOS.map((s) => s.slots[0]!.bounds[1]).concat(DEMOS.map((s) => s.slots[0]!.bounds[3]));
      const wide = (containerRef.current?.clientWidth ?? 640) >= 640;
      map.fitBounds(
        [
          [Math.min(...lons), Math.min(...lats)],
          [Math.max(...lons), Math.max(...lats)],
        ],
        {
          padding: { top: 64, left: 40, bottom: wide ? 64 : 150, right: wide ? 340 : 28 },
          maxZoom: 10,
          duration: 0,
        },
      );
    });

    map.on("click", (e) => {
      if (selectModeRef.current) return;
      const hit = sceneUnderPoint(DEMOS, e.lngLat.lng, e.lngLat.lat);
      if (hit) setSelected(hit.id);
    });

    map.on("dblclick", (e) => {
      if (selectModeRef.current) return;
      const hit = sceneUnderPoint(DEMOS, e.lngLat.lng, e.lngLat.lat);
      if (hit) {
        e.preventDefault();
        openFullRef.current(hit.id);
      }
    });

    map.on("mousedown", (e) => {
      if (!selectModeRef.current || e.originalEvent.button !== 0) return;
      e.preventDefault();
      map.dragPan.disable();
      dragStartRef.current = { lng: e.lngLat.lng, lat: e.lngLat.lat };
    });

    map.on("mousemove", (e) => {
      const start = dragStartRef.current;
      if (!selectModeRef.current || !start) return;
      const box = bboxFromCorners(start, e.lngLat);
      const src = map.getSource("box") as maplibregl.GeoJSONSource | undefined;
      src?.setData(bboxPolygon(box));
    });

    const finishDrag = (e: maplibregl.MapMouseEvent) => {
      const start = dragStartRef.current;
      dragStartRef.current = null;
      map.dragPan.enable();
      const src = map.getSource("box") as maplibregl.GeoJSONSource | undefined;
      src?.setData(EMPTY_BOX);
      if (!selectModeRef.current || !start) return;
      const box = bboxFromCorners(start, e.lngLat);
      const tiny = box[2] - box[0] < 0.002 && box[3] - box[1] < 0.002;
      if (tiny) {
        const hit = sceneUnderPoint(DEMOS, e.lngLat.lng, e.lngLat.lat);
        if (hit) setSelected(hit.id);
        return;
      }
      void sendCropRef.current(box);
    };

    map.on("mouseup", finishDrag);
    map.on("mouseleave", () => {
      if (!dragStartRef.current) return;
      dragStartRef.current = null;
      map.dragPan.enable();
      const src = map.getSource("box") as maplibregl.GeoJSONSource | undefined;
      src?.setData(EMPTY_BOX);
    });

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
    map.dragPan.enable();
    if (selectMode) map.doubleClickZoom.disable();
    else map.doubleClickZoom.enable();
    map.getCanvas().style.cursor = selectMode ? "crosshair" : "";
    if (!selectMode) {
      dragStartRef.current = null;
      const src = map.getSource("box") as maplibregl.GeoJSONSource | undefined;
      src?.setData(EMPTY_BOX);
    }
  }, [selectMode]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map?.isStyleLoaded()) return;
    for (const scene of DEMOS) {
      const id = `line-${scene.id}`;
      if (map.getLayer(id)) {
        map.setPaintProperty(id, "line-width", scene.id === selected ? 2.2 : 1.2);
        map.setPaintProperty(id, "line-opacity", scene.id === selected ? 1 : 0.5);
      }
    }
  }, [selected]);

  return (
    <div
      className="sq-console-wash relative flex h-dvh flex-col"
      onDragEnter={(e) => {
        e.preventDefault();
        onDragEnter();
      }}
      onDragOver={(e) => e.preventDefault()}
      onDragLeave={() => onDragLeave()}
      onDrop={(e) => {
        e.preventDefault();
        onDrop(Array.from(e.dataTransfer.files));
        void navigate({ to: "/console" });
      }}
    >
      <Grain />
      <AppHeader />
      <div className="relative min-h-0 flex-1">
        <div ref={containerRef} className="h-full w-full" />
        <button
          type="button"
          onClick={() => setSelectMode((on) => !on)}
          className={cn(
            "sq-glass absolute top-3 left-3 z-10 px-3 py-1.5 font-mono text-[11px] tracking-wide",
            selectMode ? "text-primary" : "text-mute hover:text-ink",
          )}
        >
          {selectMode ? "Drawing portion" : "Select portion"}
        </button>
        <aside className="sq-glass absolute top-3 right-3 z-10 hidden w-[min(320px,calc(100%-2rem))] flex-col overflow-hidden rounded-xl sm:bottom-3 sm:flex">
          <SceneCard demo={demo} onAsk={() => openFull(demo.id)} />
          <ul className="sq-scroll border-t border-hairline p-2">
            {DEMOS.map((scene) => (
              <li key={scene.id}>
                <button
                  type="button"
                  onClick={() => setSelected(scene.id)}
                  onDoubleClick={() => openFull(scene.id)}
                  className={cn(
                    "flex w-full items-center gap-2.5 rounded-lg px-2 py-2 text-left",
                    scene.id === selected ? "bg-raised" : "hover:bg-raised/50",
                  )}
                >
                  <DemoThumb demo={scene} className="size-9 shrink-0 rounded-md" />
                  <span className="min-w-0">
                    <span className="block truncate text-[13px] text-ink">{scene.title}</span>
                    <span className="block truncate font-mono text-[11px] text-mute">{scene.place}</span>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </aside>
        <div className="sq-glass absolute inset-x-3 bottom-3 z-10 p-3 sm:hidden">
          <MobileCard demo={demo} onAsk={() => openFull(demo.id)} onPick={setSelected} />
        </div>
      </div>
      <Footer hint="Select a scene, or draw a portion to send a PNG. Drop a GeoTIFF onto the map." />
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
  const slot = demo.slots[0]!;
  return (
    <div className="p-3">
      <DemoThumb demo={demo} className="h-36 w-full rounded-lg" />
      <h1 className="mt-3 text-[15px] font-medium text-ink">{demo.title}</h1>
      <p className="mt-1 font-mono text-[11px] text-mute">
        {demo.slots.map((s) => s.sensor).filter((v, i, a) => a.indexOf(v) === i).join(" · ")} · {demo.gsd}
      </p>
      <p className="mt-1 text-[12px] text-mute">{demo.place}</p>
      <p className="mt-2 text-[13px] leading-relaxed text-mute">{demo.blurb}</p>
      <ul className="mt-2 flex flex-col gap-0.5">
        {demo.queries.map((q) => (
          <li key={q} className="font-mono text-[10px] leading-snug text-mute">
            {q}
          </li>
        ))}
      </ul>
      <p className="mt-2 font-mono text-[10px] text-mute">{slot.bounds.map((n) => n.toFixed(3)).join(", ")}</p>
      <Button type="button" className="mt-4 w-full" onClick={onAsk}>
        Open in console
        <ArrowRight className="size-4" />
      </Button>
    </div>
  );
}

function MobileCard({
  demo,
  onAsk,
  onPick,
}: {
  demo: DemoScene;
  onAsk: () => void;
  onPick: (id: DemoId) => void;
}) {
  return (
    <div>
      <div className="flex gap-1.5">
        {DEMOS.map((scene) => (
          <button
            key={scene.id}
            type="button"
            onClick={() => onPick(scene.id)}
            className={cn(
              "rounded-md px-2 py-1 font-mono text-[11px]",
              scene.id === demo.id ? "bg-primary/15 text-primary" : "text-mute",
            )}
          >
            {scene.title}
          </button>
        ))}
      </div>
      <div className="mt-2 flex items-center gap-3">
        <DemoThumb demo={demo} className="size-12 shrink-0 rounded-md" />
        <div className="min-w-0 flex-1">
          <p className="truncate text-[13px] text-ink">{demo.title}</p>
          <p className="truncate font-mono text-[11px] text-mute">{demo.gsd}</p>
        </div>
        <Button type="button" size="sm" onClick={onAsk}>
          Open
        </Button>
      </div>
    </div>
  );
}
