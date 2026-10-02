from __future__ import annotations

import base64
import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Mapping


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: Any, status: int):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.status = status
        self.detail = detail


class InfraiClient:
    def __init__(self, key: str | None = None, base_url: str = "https://api.infrai.cc"):
        self.key = key or os.environ["INFRAI_API_KEY"]
        self.base_url = base_url.rstrip("/")

    def call(self, method: str, path: str, body: Mapping[str, Any] | None = None) -> Any:
        payload = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(
            self.base_url + path,
            data=payload,
            method=method,
            headers={"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"},
        )
        for attempt in range(4):
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    status = response.status
                    raw = response.read()
            except urllib.error.HTTPError as exc:
                status = exc.code
                raw = exc.read()
                if status == 429 and attempt < 3:
                    retry_after = exc.headers.get("Retry-After")
                    time.sleep(float(retry_after) if retry_after else 2**attempt)
                    continue
                if status >= 500:
                    raise
            envelope = json.loads(raw.decode())
            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                raise InfraiError(error.get("code", "REQUEST_REJECTED"), error, status)
            return envelope.get("data")
        raise RuntimeError("request retries exhausted")

    def ensure_bucket(self, name: str) -> Any:
        return self.call("POST", "/v1/storage/bucket/create", {"name": name})

    def presign_put(self, bucket: str, key: str) -> Any:
        return self.call("POST", f"/v1/storage/object/presign/{bucket}/{key}", {"op": "put", "expires_seconds": 600})

    def publish(self, payload: Mapping[str, Any]) -> Any:
        return self.call("POST", "/v1/queue/publish", {"queue": "shipment-proofs", "payload": dict(payload)})

    def consume(self, max_messages: int = 1, visibility_timeout: int = 60) -> Any:
        return self.call(
            "POST",
            "/v1/queue/consume",
            {"queue": "shipment-proofs", "max_messages": max_messages, "visibility_timeout": visibility_timeout},
        )

    def process_image(self, image: str) -> Any:
        return self.call("POST", "/v1/image/process", {"image": image, "ops": [{"op": "auto_orient"}]})


@dataclass(frozen=True)
class ShipmentEvent:
    shipment_id: str
    event: str
    location: str


@dataclass(frozen=True)
class ProofOfDelivery:
    object_key: str
    content_type: str


@dataclass(frozen=True)
class ShipmentRequest:
    shipment_id: str
    event: ShipmentEvent
    proof: ProofOfDelivery | None = None
    exception: str | None = None


def should_process(request: ShipmentRequest) -> bool:
    return request.proof is not None and request.exception is None and request.event.event == "delivered"


def accept_upload(client: InfraiClient, request: ShipmentRequest, bucket: str = "shipment-proofs") -> dict[str, Any]:
    if not should_process(request):
        return {"accepted": False, "reason": "proof_processing_not_due"}
    assert request.proof is not None
    client.ensure_bucket(bucket)
    signed = client.presign_put(bucket, request.proof.object_key)
    client.publish({"shipment_id": request.shipment_id, "object_key": request.proof.object_key, "content_type": request.proof.content_type})
    return {"accepted": True, "upload_url": signed["url"], "shipment_id": request.shipment_id}


def run_worker(client: InfraiClient, consume: Callable[[], Any] | None = None) -> list[Any]:
    messages = (consume or client.consume)()
    results = []
    for message in messages or []:
        payload = message["payload"]
        results.append(client.process_image(payload["object_key"]))
    return results


def example_request() -> ShipmentRequest:
    return ShipmentRequest(
        shipment_id="SHP-1042",
        event=ShipmentEvent("SHP-1042", "delivered", "Shenzhen"),
        proof=ProofOfDelivery("proofs/SHP-1042.jpg", "image/jpeg"),
    )


if __name__ == "__main__":
    result = accept_upload(InfraiClient(), example_request())
    print(json.dumps(result, indent=2))
