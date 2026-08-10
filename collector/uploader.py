#!/usr/bin/env python3
"""Upload collected JSON payload to the configured API endpoint.

Supports:
- Configurable endpoint URL + API key (from config.yaml)
- Retry logic with exponential backoff (max 3 attempts)
- Local save on failure
- HTTP 401 = immediate failure (wrong key)
"""

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests
import yaml

logger = logging.getLogger("collector.uploader")

MAX_RETRIES = 3
RETRY_DELAYS = [2, 5, 10]  # seconds


@dataclass
class EndpointConfig:
    url: str
    api_key: str


@dataclass
class WiFiConfig:
    ssid: str
    password: str


@dataclass
class Config:
    endpoint: EndpointConfig
    wifi: WiFiConfig


def load_config(path: str) -> Config:
    """Load config.yaml and return Config dataclass."""
    with open(path) as f:
        data = yaml.safe_load(f)

    return Config(
        endpoint=EndpointConfig(
            url=data.get("endpoint", {}).get("url", ""),
            api_key=data.get("endpoint", {}).get("api_key", ""),
        ),
        wifi=WiFiConfig(
            ssid=data.get("wifi", {}).get("ssid", ""),
            password=data.get("wifi", {}).get("password", ""),
        ),
    )


class AuthError(Exception):
    """Raised on HTTP 401 — invalid API key."""


class ValidationError(Exception):
    """Raised on HTTP 422 — invalid payload."""


class UploadError(Exception):
    """Raised after all retries exhausted."""


def upload(payload: dict, config: Config) -> dict:
    """POST payload to API endpoint with retry logic.

    Args:
        payload: The assembled JSON payload dict.
        config: Config with endpoint URL and API key.

    Returns:
        dict with 'laptopId' and 'url' keys on success.

    Raises:
        AuthError: Invalid API key (401).
        ValidationError: Invalid payload (422).
        UploadError: All retries failed.
    """
    headers = {
        "Content-Type": "application/json",
        "x-api-key": config.endpoint.api_key,
    }

    for attempt in range(MAX_RETRIES):
        try:
            logger.info(f"Upload attempt {attempt + 1}/{MAX_RETRIES} → {config.endpoint.url}")
            resp = requests.post(
                config.endpoint.url,
                json=payload,
                headers=headers,
                timeout=15,
            )

            if resp.status_code == 200:
                data = resp.json()
                logger.info(f"Upload success: laptopId={data.get('laptopId')}")
                return data

            elif resp.status_code == 401:
                raise AuthError("Invalid API key — check config.yaml")

            elif resp.status_code == 422:
                details = resp.json().get("details", "Unknown validation error")
                raise ValidationError(f"Validation failed: {details}")

            else:
                logger.warning(f"Upload attempt {attempt + 1}: HTTP {resp.status_code}")

        except requests.ConnectionError as e:
            logger.warning(f"Upload attempt {attempt + 1}: Connection failed — {e}")
        except requests.Timeout as e:
            logger.warning(f"Upload attempt {attempt + 1}: Timeout — {e}")

        if attempt < MAX_RETRIES - 1:
            wait = RETRY_DELAYS[attempt]
            logger.info(f"Retrying in {wait}s...")
            time.sleep(wait)

    raise UploadError(f"Upload failed after {MAX_RETRIES} attempts")


def save_fallback(payload: dict, path: str = "/tmp/last_upload.json") -> None:
    """Save payload locally so data isn't lost on upload failure."""
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)
    logger.info(f"Payload saved to {path}")
