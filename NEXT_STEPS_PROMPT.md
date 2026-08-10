# OpenCode — Complete Spec Hunter: Remaining Work

> Read this entire file first, then execute in order.
> **CORRECTION:** No separate Spec Hunter PWA needed. USB uploads directly to Electronic ERP's Firebase.

---

## Architecture (Corrected)

```
USB Collector (Python)
    │  POST JSON (+ API key)
    ▼
Firebase Function  ←  inside Electronic ERP's functions/
    │
    ├── Firestore → products collection → variants[].individualItems[]
    │                (laptops stored as individual serial-tracked items)
    │
    ├── Firebase Storage → photos/{laptopId}/*
    │
    └── Electronic ERP UI reads/writes from same Firestore
         (inventory view, POS with serial picker, after-sales lookup)
```

The Electronic ERP **is the UI**. No separate PWA needed.

---

## Overview: 2 Phases

| Phase | Location | What | Time |
|-------|----------|------|------|
| **1** | `spec-hunter-usb/` | Finish USB: test collectors, add Firebase Function target | 1-2 hr |
| **2** | `Electronic ERP/` | Add Firebase Function for USB ingest + test UI pages + finalize schema | 3-5 hr |

---

## Phase 1: Finish USB Collector

**Location:** `/home/voz/spec-hunter-usb/`

### Step 1.1 — Add dependencies

Edit `requirements.txt` to add:
```
requests>=2.31.0
pyyaml>=6.0
```

Install:
```bash
pip install -r requirements.txt
```

### Step 1.2 — Test each collector on THIS laptop

```bash
cd /home/voz/spec-hunter-usb
python3 collector/identity.py
python3 collector/cpu.py
python3 collector/ram.py
python3 collector/storage.py
python3 collector/battery.py
python3 collector/display.py
python3 collector/network.py
python3 collector/camera.py
```

Each should output valid JSON. Fix any that return empty or error.

### Step 1.3 — Test full pipeline

```bash
python3 collector/main.py
```

Will fail to upload (no endpoint yet) — should save to `/tmp/last_upload.json`. Verify.

### Step 1.4 — Git push

```bash
cd /home/voz/spec-hunter-usb
git init
git remote add origin https://github.com/bhonepyisone/spec-hunter-usb.git
git add .
git commit -m "Add: complete USB collector with all 11 modules"
git push -u origin main
```

---

## Phase 2: Electronic ERP — Accept USB Data + Test UI

**Location:** `/home/voz/Downloads/BPS-backup/code/Electronic ERP/`

### Step 2.1 — Add remaining fields to types.ts

Open `types.ts` and add these 5 fields inside `individualItems[]` (after `storage` line):
```typescript
ramSpeed?: string;       // e.g. "4800MHz"
storage2?: string;        // Second drive model
storageHealth?: number;   // Primary drive SMART health %
storageHealth2?: number;  // Secondary drive SMART health %
powerOnHours?: number;    // Power-on hours from SMART
```

### Step 2.2 — Add Firebase Function for USB ingest

In `functions/src/index.ts`, add an endpoint:

```typescript
export const uploadLaptop = functions.https.onRequest({ cors: true }, async (req, res) => {
  // 1. Validate x-api-key header matches env variable
  // 2. Parse USB payload JSON
  // 3. Create a new product + variant + individualItems[] in Firestore
  // 4. Return { laptopId, url }
});
```

The function should:
- Read API key from environment variable (not hardcoded)
- Accept the full USB JSON format (identity, cpu, ram, storage, storage2, battery, display, network, camera)
- Find or create a product matching brand+model
- Create a variant with `trackSerials: true`
- Add one `individualItems[]` entry per laptop
- Set `grade`, `buyPrice`, `sellPrice`, `batteryHealth`, `serialNumber`, etc. from USB data
- Auto-generate barcode from serial number

### Step 2.3 — Update CSV import to handle individual items

Edit `utils/productImport.ts`:
- Accept new optional columns: `grade`, `buyPrice`, `individualSerialNumber`, `individualBatteryHealth`, `individualGrade`
- If present → populate `individualItems[]` array
- If absent → import as normal grouped stock (backward compatible)

### Step 2.4 — Update JSON import script

Edit `scripts/manage-firestore-data.mjs`:
- Accept `individualItems[]` in the import data
- Auto-populate `trackSerials: true` and `availableItems` when individualItems present

### Step 2.5 — Create test suite UI page in Electronic ERP

This is the interactive test page — added as a new route/page in the Electronic ERP (not a separate app).

Find where the Electronic ERP defines its routes/pages. Add a new page:

| Route | What it does |
|-------|-------------|
| `/test/[laptopId]` | Runs interactive tests one by one on the laptop |

The test page should:
1. Look up the laptop by variant ID (from URL param)
2. Walk through tests in sequence (auto tests first, then manual)
3. Save results back to Firestore → `individualItems[].keyboardTest`, etc.
4. After all tests done, redirect to grade view

```typescript
// Test sequence:
const TEST_ORDER = [
  // Auto tests (browser runs these, operator just confirms)
  { id: 'camera', label: 'Camera', type: 'auto' },
  { id: 'speaker', label: 'Speaker', type: 'auto' },
  { id: 'microphone', label: 'Microphone', type: 'auto' },
  { id: 'touchpad', label: 'Touchpad', type: 'auto' },
  { id: 'wifi', label: 'WiFi', type: 'auto' },
  // Manual tests (operator must interact)
  { id: 'keyboard', label: 'Keyboard', type: 'manual' },
  { id: 'display', label: 'LCD Display', type: 'manual' },
  { id: 'usb', label: 'USB Ports', type: 'manual' },
  // Body assessment
  { id: 'photos', label: 'Body Photos', type: 'photo' },
  { id: 'condition', label: 'Body Condition', type: 'select' },
  // Pricing
  { id: 'buyPrice', label: 'Buy Price', type: 'input' },
];
```

Each test component can be built right inside the ERP's component tree — no separate app needed.

### Step 2.6 — Add grading + pricing logic

Inside the ERP (not a separate lib), add grading logic that runs after all tests are complete:

- Read battery health, storage health, test results, body condition from the laptop's data
- Calculate grade using the same formula (battery ≥85%=A+, ≥75%=A, etc.)
- Apply penalties for test failures, poor body condition
- Suggest sell price = buyPrice × grade multiplier
- Save grade + sell price back to `individualItems[]`

### Step 2.7 — Update POS for serial selection

Edit POS component:
- When adding a serial-tracked variant to cart, show a serial picker dialog
- Display available individual items: serial, grade, battery, sell price
- On checkout, record which serial(s) were sold → update `individualItems[].sold = true`

### Step 2.8 — Add serial search + inventory serial panel

- In inventory view, add "Search by Serial" input
- For serial-tracked variants, show clickable "N units" indicator → opens detail panel
- In after-sales view, add serial lookup → find sale → find customer

---

## CRITICAL RULES

1. **DO NOT auto-commit** — user reviews and commits manually
2. **No separate PWA** — everything lives inside Electronic ERP
3. **Keep grouped stock working** — accessories/chargers unaffected
4. **Dark theme only** — bg #121317 in ERP
5. **Mobile-first** — test at 375px
6. **DO NOT change** customer module, financials, marketplace sync, HR
