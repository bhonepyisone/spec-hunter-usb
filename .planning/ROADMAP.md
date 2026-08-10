# Spec Hunter USB — Roadmap

## Milestones

### Phase 1 — Collectors (Current)
**Goal:** Every collector returns correct JSON with working fallbacks.

| Step | What | Depends On |
|------|------|------------|
| 1.1 | 9 collectors: identity, cpu, ram, storage, battery, display, network, camera, uploader | Nothing |
| 1.2 | pytest suite passes (`pytest tests/`) | 1.1 |
| 1.3 | Real-hardware verification of each collector | 1.2 |
| 1.4 | Offline test — VM with no battery/display → graceful N/A | 1.3 |

### Phase 2 — Upload Path
**Goal:** Payload reaches Electronic ERP as a serial-tracked laptop row.

| Step | What | Depends On |
|------|------|------------|
| 2.1 | `config.yaml` endpoint + api_key wired through uploader | 1.1 |
| 2.2 | ERP `uploadLaptop` Firebase Function (x-api-key auth → products/variants/individualItems) | 2.1 |
| 2.3 | E2E: POST sample JSON → row appears in ERP inventory | 2.2 |

### Phase 3 — ISO + Ship
**Goal:** Bootable USB that collects + uploads + powers off.

| Step | What | Depends On |
|------|------|------------|
| 3.1 | `build-iso.sh` produces a bootable `.iso` | 1.1 |
| 3.2 | Boot-on-laptop smoke: WiFi connect → collect → upload → poweroff | 3.1 |
| 3.3 | DoD 1–18 verification on real laptops (Dell/Lenovo/HP/Surface serial router) | 3.2 |