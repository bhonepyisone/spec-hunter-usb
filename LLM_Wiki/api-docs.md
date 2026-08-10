# Spec Hunter USB — API Contract

## Upload Endpoint

The USB tool POSTs collected hardware data to a configurable REST API. The default target is the Firebase Function on the Spec Hunter web app.

### POST {endpoint_url}

**Headers:**
```
Content-Type: application/json
x-api-key: <from config.yaml>
```

**Request Body:**

All fields are optional — collectors return empty dicts on failure. The API handles defaults for missing fields.

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

**Response (200):**
```json
{
  "laptopId": "abc123xyz",
  "url": "https://spec-hunter.web.app/laptops/abc123xyz"
}
```

**Response (401):**
```json
{
  "error": "Invalid API key"
}
```

### uploader.py Configuration

```python
# config.yaml controls the endpoint
endpoint:
  url: "https://us-central1-<project>.cloudfunctions.net/uploadLaptop"
  api_key: "generated-shared-secret"

# The USB tool POSTs to ANY endpoint with the same contract.
# To target a different backend (JM505 ERP, existing POS):
#   Just change endpoint.url in config.yaml
```

### Retry Logic

```python
MAX_RETRIES = 3
RETRY_DELAYS = [2, 5, 10]  # seconds

for attempt in range(MAX_RETRIES):
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=15)
        if response.status_code == 200:
            print(f"Laptop ID: {response.json()['laptopId']}")
            break
    except requests.RequestException:
        if attempt < MAX_RETRIES - 1:
            time.sleep(RETRY_DELAYS[attempt])
        else:
            print("Upload failed after 3 attempts")
```
