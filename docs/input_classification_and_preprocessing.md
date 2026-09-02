# Stage 3 — Input Classifier & Input-Type-Aware Preprocessing Pipeline

**Project:** SIH26167 — SatQuery AI  
**Document type:** Technical Module Specification & Implementation Report  
**Status:** Completed & Verified (Stage 3 Baseline)  

---

## 1. Overview & Architectural Role

Stage 3 implements the **Input Classifier** and **Input-Type-Aware Preprocessing Subsystem** for SatQuery AI.

### Key Architectural Separation: Input Configuration vs. User Intent
* **Input Configuration (Stage 3)** describes the physical and temporal nature of the uploaded satellite rasters (e.g. `SINGLE_OPTICAL`, `SINGLE_SAR`, `BI_TEMPORAL`, `OPTICAL_SAR`).
* **User Intent / Task (Later Stage)** describes the analytical question posed by the user (e.g. `SINGLE_VQA`, `CHANGE_VQA`, `GROUNDING`, `OPTICAL_SAR_FUSION`).
* The Input Classifier is **deterministic** and metadata-driven. It does not use an LLM or load multi-GB rasters into memory to determine the input class.

---

## 2. Input Classification Rules

| Input Class | Conditions Required |
|---|---|
| `SINGLE_OPTICAL` | Exactly 1 input asset with `modality = OPTICAL` (e.g. Sentinel-2, Cartosat-2S). |
| `SINGLE_SAR` | Exactly 1 input asset with `modality = SAR` (e.g. Sentinel-1, RISAT). |
| `BI_TEMPORAL` | Exactly 2 assets of the same modality (optical or SAR) with different acquisition timestamps and verified spatial overlap ($\ge 10\%$ IoU/mutual coverage). |
| `OPTICAL_SAR` | Exactly 2 assets (1 Optical + 1 SAR) with verified spatial overlap ($\ge 10\%$). Dimensions, CRS, and resolutions may differ. |

### Refusal & Controlled Validation Conditions
The classifier safely refuses invalid inputs without throwing unhandled exceptions:
* **Empty Asset List**: Refused (`No input assets provided`).
* **Excessive Assets**: $> 2$ assets refused (`Unsupported asset count`).
* **Identical Timestamp Pair**: 2 images with identical acquisition dates refused for bitemporal comparison.
* **Missing Dates**: Bitemporal pair with missing timestamp metadata refused.
* **Insufficient Overlap**: Multi-image pairs with disjoint or $< 10\%$ intersection refused.
* **Unsupported Modality**: Unrecognized sensor modalities safely refused.

---

## 3. Preprocessing Branches & Dispatcher

Following classification, `PreprocessingDispatcher` routes assets strictly to their modality-specific branch:

```
                    ┌─ SINGLE_OPTICAL ─► OpticalPreprocessor (RGB composite, percentile stretch, tiles)
                    │
                    ├─ SINGLE_SAR ─────► SARPreprocessor (dB conversion, speckle filter, tiles; NO cloud mask)
InputClassification ┤
                    ├─ BI_TEMPORAL ────► BitemporalPreprocessor (Intersection alignment, paired synchronized tiles)
                    │
                    └─ OPTICAL_SAR ────► OpticalSARPreprocessor (Cross-modal grid match, independent calibration, joint tiles)
```

### Branch Execution Details:
1. **`SINGLE_OPTICAL`**:
   - Band selection (RGB / panchromatic duplicate).
   - Percentile contrast normalization ([0, 255] uint8).
   - Full composite generated at `data/jobs/{id}/processed/composite_optical_{name}.png/.tif`.
   - Model-ready square tiles ($256 \times 256$ default) in `data/jobs/{id}/tiles/`.
2. **`SINGLE_SAR`**:
   - Logarithmic radiometric calibration: $\text{dB} = 10 \cdot \log_{10}(\text{intensity} + 10^{-6})$.
   - Spatial box / Lee speckle reduction filter.
   - Grayscale / false-color normalization.
   - Full composite in `processed/` and tiles in `tiles/`.
3. **`BI_TEMPORAL`**:
   - Computes mutual geographic bounding box intersection.
   - Resamples and co-registers T1 and T2 onto the exact same reference grid.
   - Applies consistent radiometric normalization across timestamps.
   - Slices synchronized tile pairs: **Tile $i$ of T1 and Tile $i$ of T2 cover the exact same geographic footprint**.
   - Preserves `TilePair` records with linked tile IDs.
4. **`OPTICAL_SAR`**:
   - Computes cross-modal spatial overlap.
   - Reprojects and resamples SAR to match the Optical spatial grid over the intersection.
   - Applies optical preprocessing to Optical, and SAR dB calibration/speckle filtering to SAR.
   - Slices synchronized cross-modal tile pairs into `tiles/optical/` and `tiles/sar/`.

---

## 4. Preservation of Spatial Information

Every generated tile maintains a `TileReference` object with:
* Native CRS and Affine transform.
* Native bounding box: `[min_x, min_y, max_x, max_y]`.
* WGS84 bounding box: `[min_lon, min_lat, max_lon, max_lat]`.
* WKT polygon representation.
* Source asset ID and acquisition timestamp.
* Paired tile ID link for bitemporal / cross-modal pairs.

---

## 5. In-Memory Session & Audit Trace Integration

* During execution, state is managed in-memory via `SessionContext` (`backend/session.py`).
* Audit traces recorded at every lifecycle milestone:
  * `INPUT_ANALYZED`
  * `INPUT_CLASSIFIED`
  * `PREPROCESS_START`
  * `PREPROCESS_STEP`
  * `PREPROCESS_COMPLETE`
  * `PREPROCESS_FAILED`

---

## 6. Test Verification Summary

The test suite in `test_input_classification_and_preprocessing.py` verified 13 distinct automated test cases:
1. `SINGLE_OPTICAL` single asset classification: **PASS**
2. `SINGLE_SAR` single asset classification: **PASS**
3. `BI_TEMPORAL` pair classification: **PASS**
4. `OPTICAL_SAR` cross-modal pair classification: **PASS**
5. Identical acquisition timestamp refusal: **PASS**
6. Disjoint footprint spatial refusal: **PASS**
7. Unsupported modality refusal: **PASS**
8. Missing acquisition date refusal: **PASS**
9. Optical preprocessing pipeline & tile spatial mapping: **PASS**
10. SAR preprocessing & speckle filter execution (no cloud mask): **PASS**
11. Bitemporal paired geographic alignment & synchronized tiling: **PASS**
12. Optical + SAR cross-modal alignment & joint tiling: **PASS**
13. In-memory session & audit trace logging: **PASS**
