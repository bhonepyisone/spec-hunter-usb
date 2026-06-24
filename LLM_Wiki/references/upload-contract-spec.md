# USB → API Upload Contract — Validation Spec

> Defines the JSON contract between the USB boot collector and the web app's Firebase Function.
> Source of truth for: required fields, optional fields, default values, error handling.

---

## 1. Endpoint

```
POST {configurable_endpoint_url}
Content-Type: application/json
x-api-key: {shared_secret}
```

Default endpoint (during development): `http://localhost:5001/<project>/us-central1/uploadLaptop`
Production endpoint: `https://us-central1-<project>.cloudfunctions.net/uploadLaptop`

---

## 2. Request Body — Complete Schema

### Top-Level Structure

| Field | Type | Required | Source | Notes |
|-------|------|----------|--------|-------|
| `identity` | object | ✅ Always | identity.py | Must have at minimum brand or serial |
| `cpu` | object | ✅ Always | cpu.py | Empty dict if collection fails |
| `ram` | object | ✅ Always | ram.py | Empty dict if collection fails |
| `storage` | object | ✅ Always | storage.py | Empty dict if collection fails |
| `battery` | object | ✅ Always | battery.py | Empty dict if no battery/collection fails |
| `display` | object | ✅ Always | display.py | Empty dict if collection fails |
| `network` | object | ✅ Always | network.py | Empty dict if collection fails |
| `camera` | object | ✅ Always | camera.py | Empty dict if collection fails |

### identity

| Field | Type | Required | Default | Fallback |
|-------|------|----------|---------|----------|
| `brand` | string | No | `"Unknown"` | dmidcode system-manufacturer → sysfs |
| `model` | string | No | `"Unknown"` | dmidcode system-product-name → sysfs |
| `serial_number` | string | No | `"N/A"` | Brand-specific parsing → empty string |
| `bios_version` | string | No | `"N/A"` | dmidecode bios-version |
| `manufacture_date` | string | No | `null` | dmidecode bios-release-date |
| `motherboard_model` | string | No | `"N/A"` | dmidecode baseboard-product-name |
| `uuid` | string | No | `"N/A"` | dmidecode system-uuid |
| `asset_tag` | string | No | `""` | dmidecode chassis-asset-tag |

### cpu

| Field | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| `name` | string | No | `"N/A"` | e.g. "Intel Core i5-1145G7" |
| `generation` | number | No | `null` | Extracted from CPU name. 11th gen → 11 |
| `cores` | number | No | `null` | Physical cores |
| `threads` | number | No | `null` | Logical processors |
| `base_clock` | number | No | `null` | GHz |
| `turbo_clock` | number | No | `null` | GHz |

### ram

| Field | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| `total_gb` | number | No | `null` | Total RAM in GB |
| `slot_count` | number | No | `null` | Physical slots on motherboard |
| `used_slots` | number | No | `null` | Occupied slots |
| `speed` | number | No | `null` | MHz |
| `ddr_type` | string | No | `"N/A"` | "DDR4", "DDR5", "LPDDR4x" |
| `manufacturer` | string | No | `"N/A"` | "Samsung", "SK Hynix", etc. |

### storage

| Field | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| `model` | string | No | `"N/A"` | e.g. "Samsung PM981" |
| `capacity_gb` | number | No | `null` | e.g. 512 |
| `interface` | string | No | `"N/A"` | "NVMe", "SATA", "unknown" |
| `health_pct` | number | No | `null` | 0-100 |
| `power_on_hours` | number | No | `null` | Total hours powered on |
| `power_cycles` | number | No | `null` | Total power cycles |
| `total_bytes_written` | number | No | `null` | In bytes |
| `remaining_life_pct` | number | No | `null` | NVMe-specific wear indicator |
| `temperature` | number | No | `null` | Celsius |
| `bad_sectors` | number | No | `null` | SATA-specific |
| `smart_status` | string | No | `"N/A"` | "PASS", "FAIL", "N/A" |

### battery

| Field | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| `design_capacity` | number | No | `null` | mAh or mWh |
| `current_capacity` | number | No | `null` | Current max capacity |
| `cycle_count` | number | No | `null` | Number of charge cycles |
| `health_pct` | number | No | `null` | current/design * 100 |
| `manufacturer` | string | No | `"N/A"` | e.g. "LGC", "Panasonic" |
| `serial` | string | No | `"N/A"` | Battery serial number |

### display

| Field | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| `resolution` | string | No | `"N/A"` | e.g. "1920x1080" |
| `refresh_rate` | number | No | `null` | e.g. 60, 120, 144 |
| `manufacturer` | string | No | `"N/A"` | e.g. "LG Display", "BOE" |
| `screen_size_inch` | number | No | `null` | e.g. 14.0 |
| `model` | string | No | `"N/A"` | Panel model number |

### network

| Field | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| `wifi_card` | string | No | `"N/A"` | e.g. "Intel Wi-Fi 6 AX201" |
| `bluetooth` | string | No | `"N/A"` | e.g. "Bluetooth 5.2" |
| `mac_address` | string | No | `"N/A"` | Primary MAC (WiFi or Ethernet) |
| `lan_adapter` | string | No | `"N/A"` | e.g. "Intel Ethernet I219-LM" |

### camera

| Field | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| `exists` | boolean | No | `false` | True if /dev/videoN detected |
| `device_path` | string | No | `""` | e.g. "/dev/video0" |
| `model` | string | No | `"N/A"` | From v4l2-ctl output |

---

## 3. API Response Format

### Success (HTTP 200)

```json
{
  "laptopId": "abc123xyz",
  "url": "https://spec-hunter.web.app/laptops/abc123xyz"
}
```

The USB tool prints this to the terminal screen.

### Validation Error (HTTP 422)

```json
{
  "error": "Validation failed",
  "details": {
    "identity.brand": "Must be a string"
  }
}
```

If the API receives invalid types (e.g. string where number expected), it returns 422.
The USB tool logs the error and retries (max 3 attempts).

### Auth Error (HTTP 401)

```json
{
  "error": "Invalid API key"
}
```

API key mismatch. USB tool logs the error and gives up (no retry — wrong endpoint or key).

### Server Error (HTTP 500)

```json
{
  "error": "Internal server error"
}
```

Firebase Function crashed. USB tool retries (max 3 attempts).

---

## 4. USB-Side Error Handling

### Retry Logic

```python
MAX_RETRIES = 3
RETRY_DELAYS = [2, 5, 10]  # seconds

def upload(payload: dict, config: Config) -> dict:
    """POST payload to API endpoint. Returns {laptopId, url} or raises."""
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.post(
                config.endpoint.url,
                json=payload,
                headers={"x-api-key": config.endpoint.api_key},
                timeout=15
            )
            if resp.status_code == 200:
                return resp.json()
            elif resp.status_code == 401:
                raise AuthError("Invalid API key — check config.yaml")
            elif resp.status_code == 422:
                raise ValidationError(f"Validation failed: {resp.json().get('details')}")
            else:
                logger.warning(f"Upload attempt {attempt+1}: HTTP {resp.status_code}")
        except (requests.ConnectionError, requests.Timeout) as e:
            logger.warning(f"Upload attempt {attempt+1}: {e}")

        if attempt < MAX_RETRIES - 1:
            time.sleep(RETRY_DELAYS[attempt])

    raise UploadError(f"Upload failed after {MAX_RETRIES} attempts")
```

### Failure Behavior

| Scenario | Behavior | Terminal Output |
|----------|----------|-----------------|
| Upload succeeds | Print laptop ID + URL, poweroff in 10s | `✅ Laptop ID: abc123 — https://...` |
| All retries fail | Log error, poweroff in 10s | `❌ Upload failed after 3 attempts. JSON saved to /tmp/last_upload.json` |
| Invalid API key (401) | Immediate failure, no retry | `❌ Invalid API key — check config.yaml` |
| No network | Retry 3x, fail | `❌ No network — upload unavailable` |

### Local Save on Failure

Failed uploads save to `/tmp/last_upload.json` so data isn't lost even if the USB tool can't upload. The JSON can be manually copied/pasted into the web app's JSON paste form.

---

## 5. API-Side Validation (Firebase Function)

```typescript
// functions/src/index.ts — validation logic

interface UploadBody {
  identity: Record<string, any>;
  cpu: Record<string, any>;
  ram: Record<string, any>;
  storage: Record<string, any>;
  battery: Record<string, any>;
  display: Record<string, any>;
  network: Record<string, any>;
  camera: Record<string, any>;
}

function validateBody(body: any): UploadBody {
  // All top-level sections default to {} if missing
  const sections = ['identity', 'cpu', 'ram', 'storage', 'battery', 'display', 'network', 'camera'];
  
  for (const section of sections) {
    if (typeof body[section] !== 'object' || body[section] === null) {
      body[section] = {};
    }
  }
  
  return body as UploadBody;
}

function applyDefaults(body: UploadBody): UploadBody {
  // Set default values for common fields
  if (!body.identity.brand) body.identity.brand = "Unknown";
  if (body.storage.health_pct === null) body.storage.health_pct = null;
  // ... additional defaults
  return body;
}
```

---

## 6. Testing the Contract

### Test Payload (Minimal)

```json
{
  "identity": { "brand": "Test", "serial_number": "TEST001" },
  "cpu": {},
  "ram": {},
  "storage": {},
  "battery": {},
  "display": {},
  "network": {},
  "camera": {}
}
```

### Test Payload (Full)

```json
{
  "identity": {
    "brand": "Dell",
    "model": "Latitude 5420",
    "serial_number": "ABC123",
    "bios_version": "1.14.0",
    "manufacture_date": "2022-03-15",
    "motherboard_model": "0H3R7G",
    "uuid": "4c4c4544-0050-4810-8033-b6c04f4c5532",
    "asset_tag": ""
  },
  "cpu": {
    "name": "Intel Core i5-1145G7",
    "generation": 11,
    "cores": 4,
    "threads": 8,
    "base_clock": 2.6,
    "turbo_clock": 4.4
  },
  "ram": {
    "total_gb": 16,
    "slot_count": 2,
    "used_slots": 2,
    "speed": 3200,
    "ddr_type": "DDR4",
    "manufacturer": "Samsung"
  },
  "storage": {
    "model": "Samsung PM981",
    "capacity_gb": 512,
    "interface": "NVMe",
    "health_pct": 96,
    "power_on_hours": 1742,
    "power_cycles": 386,
    "total_bytes_written": 5242880000,
    "remaining_life_pct": 96,
    "temperature": 35,
    "bad_sectors": 0,
    "smart_status": "PASS"
  },
  "battery": {
    "design_capacity": 45000,
    "current_capacity": 40050,
    "cycle_count": 336,
    "health_pct": 89,
    "manufacturer": "LGC",
    "serial": "BAT123"
  },
  "display": {
    "resolution": "1920x1080",
    "refresh_rate": 60,
    "manufacturer": "LG Display",
    "screen_size_inch": 14.0,
    "model": "LP140WF9-SPU1"
  },
  "network": {
    "wifi_card": "Intel Wi-Fi 6 AX201",
    "bluetooth": "Bluetooth 5.2",
    "mac_address": "00:1A:2B:3C:4D:5E",
    "lan_adapter": "Intel Ethernet Connection I219-LM"
  },
  "camera": {
    "exists": true,
    "device_path": "/dev/video0",
    "model": "Integrated Webcam"
  }
}
```
