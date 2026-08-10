# Brand-Specific dmidecode Reference — Spec Hunter USB

Source: Hardware testing across multiple brands. Updated as new quirks found.

## Dell

| Field | Command | Notes |
|-------|---------|-------|
| Serial | `dmidecode -s system-serial-number` | 7-char service tag. Some models return chassis-tag instead. |
| Model | `dmidecode -s system-product-name` | e.g. "Latitude 5420" |
| Example output | `dmidecode -s system-serial-number` → `G8H9K12` |

**Edge case**: Some Dell Precision models put the serial in `dmidecode -s chassis-serial-number`.

## Lenovo

| Field | Command | Notes |
|-------|---------|-------|
| Serial | `dmidecode -s system-serial-number` | Returns MTM + serial separated by hyphen. Format: `20XJS0M100-PF3XYZ12` |
| Model | `dmidecode -s system-product-name` | e.g. "ThinkPad T14 Gen 2" |
| MTM split | Left of last `-` is machine type, right is serial | Parse: `machine_type = "20XJS0M100"`, `serial = "PF3XYZ12"` |

**Edge case**: Some ThinkPads store serial in baseboard (`dmidecode -s baseboard-serial-number`).

## HP

| Field | Command | Notes |
|-------|---------|-------|
| Serial | `dmidecode -s system-serial-number` | 10-char alphanumeric. |
| Model | `dmidecode -s system-product-name` | e.g. "HP EliteBook 840 G8" |
| Common pattern | e.g. `5CG2010XYZ` | First 3 chars = factory code, next 3 = year+week |

**Edge case**: Some HP models return "Not Specified". Fall back to UUID or chassis serial.

## Microsoft Surface

| Field | Command | Notes |
|-------|---------|-------|
| Serial | N/A | `dmidecode` returns empty or garbage. Surface serial is in UEFI/registry only. |
| Model | `dmidecode -s system-product-name` | Usually works: "Surface Pro 7" |
| Fallback | Return "N/A (Surface)" for serial | Log warning: "Surface detected, serial unavailable via dmidecode" |

## Unknown / Unbranded

| Field | Command | Notes |
|-------|---------|-------|
| Serial | `dmidecode -s system-serial-number` | Return raw value. May be "To be filled by O.E.M." |
| Brand | `dmidecode -s system-manufacturer` | Return raw value |

**Common garbage values**: "System Manufacturer", "System Product Name", "To be filled by O.E.M.", "Not Specified", "Default string"

## Unit Testing

When testing brand router, use mock dmidecode output:
```python
MOCK_DMI = {
    "dell": {"manufacturer": "Dell Inc.", "serial": "G8H9K12"},
    "lenovo": {"manufacturer": "LENOVO", "serial": "20XJS0M100-PF3XYZ12"},
    "hp": {"manufacturer": "HP", "serial": "5CG2010XYZ"},
    "surface": {"manufacturer": "Microsoft Corporation", "serial": ""},
}
```
