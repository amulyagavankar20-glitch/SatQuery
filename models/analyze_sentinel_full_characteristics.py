import os
import glob
import json
import torch
import rasterio
import numpy as np
from PIL import Image

DATASET_DIR = "/Users/dhanyahariya/Downloads/satnav/sentinel_dataset 6.01.03 PM"


def analyze_sample_characteristics(sample_dir):
    meta_path = os.path.join(sample_dir, "metadata.json")
    metadata = {}
    if os.path.exists(meta_path):
        with open(meta_path) as f:
            try:
                metadata = json.load(f)
            except Exception:
                pass

    city = metadata.get("city", os.path.basename(sample_dir))
    sample_id = metadata.get("sample_id", os.path.basename(sample_dir))
    lat = metadata.get("latitude", "N/A")
    lon = metadata.get("longitude", "N/A")

    s1_t1_path = os.path.join(sample_dir, "S1_T1.tif")
    s1_t2_path = os.path.join(sample_dir, "S1_T2.tif")
    s2_t1_path = os.path.join(sample_dir, "S2_T1.tif")
    s2_t2_path = os.path.join(sample_dir, "S2_T2.tif")

    results = {
        "sample_id": sample_id,
        "city": city,
        "coords": f"({lat}, {lon})",
        "has_sar": os.path.exists(s1_t1_path),
        "has_optical": os.path.exists(s2_t1_path),
        "urban_pct": 0.0,
        "vegetation_pct": 0.0,
        "water_pct": 0.0,
        "barren_pct": 0.0,
        "sar_mean_vv_db": None,
        "sar_mean_vh_db": None,
        "mean_ndvi": None,
        "mean_ndwi": None,
        "building_density": "Low",
        "primary_objects": [],
        "temporal_change": None
    }

    # 1. Analyze Sentinel-1 SAR Radar Backscatter
    if os.path.exists(s1_t1_path):
        with rasterio.open(s1_t1_path) as src:
            s1_data = src.read()
            vv = s1_data[0]
            vh = s1_data[1] if s1_data.shape[0] > 1 else s1_data[0]

            vv_db = 10 * np.log10(np.clip(vv, 1e-5, None))
            vh_db = 10 * np.log10(np.clip(vh, 1e-5, None))

            results["sar_mean_vv_db"] = round(float(np.mean(vv_db)), 2)
            results["sar_mean_vh_db"] = round(float(np.mean(vh_db)), 2)

            # High backscatter VV > -7 dB indicates high-density concrete buildings / double-bounce
            high_scatter_pct = np.sum(vv_db > -7.0) / vv_db.size * 100
            if high_scatter_pct > 35:
                results["building_density"] = "High (Dense Commercial / High-Rise Concrete)"
            elif high_scatter_pct > 15:
                results["building_density"] = "Medium (Residential / Mixed Infrastructure)"
            else:
                results["building_density"] = "Low (Suburban / Dispersed Settlements)"

    # 2. Analyze Sentinel-2 Multi-spectral Optical
    if os.path.exists(s2_t1_path):
        with rasterio.open(s2_t1_path) as src:
            s2_data = src.read().astype(np.float32)
            b02, b03, b04, b08 = s2_data[0], s2_data[1], s2_data[2], s2_data[3]

            ndvi = (b08 - b04) / (b08 + b04 + 1e-6)
            ndwi = (b03 - b08) / (b03 + b08 + 1e-6)

            water_mask = (ndwi > 0.0) | ((b08 < 0.07) & (b03 > b08))
            veg_mask = (ndvi >= 0.20) & (~water_mask)
            urban_mask = (ndvi < 0.20) & (~water_mask) & (b04 >= 0.08)
            barren_mask = (~water_mask) & (~veg_mask) & (~urban_mask)

            tot = float(ndvi.size)
            results["urban_pct"] = round(float(np.sum(urban_mask) / tot * 100), 1)
            results["vegetation_pct"] = round(float(np.sum(veg_mask) / tot * 100), 1)
            results["water_pct"] = round(float(np.sum(water_mask) / tot * 100), 1)
            results["barren_pct"] = round(float(np.sum(barren_mask) / tot * 100), 1)
            results["mean_ndvi"] = round(float(np.mean(ndvi)), 2)
            results["mean_ndwi"] = round(float(np.mean(ndwi)), 2)
    elif os.path.exists(s1_t1_path):
        # Fallback when only S1 is present
        tot = float(vv_db.size)
        urban_mask = (vv_db > -8.0)
        water_mask = (vv_db < -18.0) & (vh_db < -24.0)
        veg_mask = (~urban_mask) & (~water_mask)

        results["urban_pct"] = round(float(np.sum(urban_mask) / tot * 100), 1)
        results["water_pct"] = round(float(np.sum(water_mask) / tot * 100), 1)
        results["vegetation_pct"] = round(float(np.sum(veg_mask) / tot * 100), 1)

    # 3. Identify Primary Objects & Infrastructure
    objects = []
    if results["urban_pct"] > 40:
        objects.append("Dense Urban Core (Commercial & Residential Buildings, Road Grid)")
    elif results["urban_pct"] > 15:
        objects.append("Suburban Built-up (Low-to-Mid Rise Buildings, Arterial Roads)")

    if results["vegetation_pct"] > 50:
        objects.append("Extensive Tree Canopy / Green Corridors / Agricultural Zones")
    elif results["vegetation_pct"] > 15:
        objects.append("Urban Parks & Green Vegetation Patches")

    if results["water_pct"] > 5:
        objects.append("Open Water Bodies (River Channels, Estuaries, Coastal Water / Harbors)")
    elif results["water_pct"] > 0.5:
        objects.append("Lakes / Canals / Water Reservoirs")

    if results["sar_mean_vv_db"] and results["sar_mean_vv_db"] > -6.0:
        objects.append("Heavy Structural Infrastructure (Concrete Flyovers, Railway/Transport Corridors)")

    results["primary_objects"] = objects

    # 4. Temporal Dynamics
    if os.path.exists(s1_t1_path) and os.path.exists(s1_t2_path):
        with rasterio.open(s1_t1_path) as s1, rasterio.open(s1_t2_path) as s2:
            d1 = s1.read(1)
            d2 = s2.read(1)
            diff_db = np.abs(10 * np.log10(np.clip(d2, 1e-5, None)) - 10 * np.log10(np.clip(d1, 1e-5, None)))
            change_pct = np.sum(diff_db > 3.0) / diff_db.size * 100
            results["temporal_change"] = f"{change_pct:.1f}% area experienced >3dB radar backscatter change"

    return results


def main():
    samples = sorted(glob.glob(os.path.join(DATASET_DIR, "*/*")))
    all_results = [analyze_sample_characteristics(s) for s in samples]

    print("=" * 100)
    print("🛰️  FULL OBJECT, BUILDING & LAND-COVER CHARACTERISTICS OF SENTINEL DATASET")
    print("=" * 100)

    print(f"{'Sample':<8} | {'City':<15} | {'Urban / Buildings':<18} | {'Vegetation':<12} | {'Water':<8} | {'Radar VV':<10} | {'Building Density'}")
    print("-" * 100)
    for r in all_results:
        vv_str = f"{r['sar_mean_vv_db']:.1f} dB" if r['sar_mean_vv_db'] is not None else "N/A"
        print(f"{r['sample_id']:<8} | {r['city']:<15} | {r['urban_pct']:>5.1f}%             | {r['vegetation_pct']:>5.1f}%      | {r['water_pct']:>4.1f}%   | {vv_str:<10} | {r['building_density']}")

    print("\n" + "=" * 100)
    print("📍 DETAILED OBJECTS & FEATURES BY CITY SCENE:")
    print("=" * 100)

    for r in all_results:
        print(f"\n🏙️  [{r['sample_id']} - {r['city']}] Coordinates: {r['coords']}")
        print(f"   • Urban & Buildings : {r['urban_pct']}%")
        print(f"   • Green Vegetation  : {r['vegetation_pct']}%")
        print(f"   • Water Features    : {r['water_pct']}%")
        print(f"   • Radar Mean (VV/VH): {r['sar_mean_vv_db']} dB / {r['sar_mean_vh_db']} dB")
        print(f"   • Detected Objects  :")
        for obj in r['primary_objects']:
            print(f"      - {obj}")
        if r['temporal_change']:
            print(f"   • Temporal Dynamics : {r['temporal_change']}")


if __name__ == "__main__":
    main()
