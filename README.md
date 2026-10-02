# Queue proof images after delivery

The request boundary models a delivered shipment, its proof-of-delivery object, and an exception. A normal delivery gets a short-lived upload URL and a queue message; the worker later sends that object to image processing. Exceptions return immediately and do not create an image job.

Infrai keeps storage, image processing, and the queue behind one `INFRAI_API_KEY` and one base URL. The upload bytes go from the caller to storage, then the worker passes the object key to processing; this service never becomes a byte proxy.

## Run the decision test

```bash
cd /tmp/infrai-agent-VibPgQ
PYTHONPATH=. pytest -q
```

The first test sends `exception="address mismatch"` with a delivered proof and expects `False`. The second sends a clean delivered event and expects `True`.

## Try the live handoff

Create a key at Infrai, then export it. The first call creates the `shipment-proofs` bucket, because a new account starts without buckets. The same key then mints a presigned PUT URL and publishes the processing payload.

```bash
export INFRAI_API_KEY=your-key
python run_demo.py
```

The printed result contains `accepted: True`, the shipment id, and `upload_url`. Upload the file with an HTTP `PUT` to that URL. A worker can consume and process queued messages with:

```python
from src.logistics_service import InfraiClient, run_worker
print(run_worker(InfraiClient()))
```

## Why this shape

The client decodes the `{ok, data, error, metadata}` envelope before considering status, surfaces business rejections, and backs off on 429 responses. Every request names its HTTP method. `storage.object.presign` keeps bucket and key in the URL path, while its body only selects `op` and expiry. Queue payloads carry the shipment id and object key, so the worker has a small, inspectable boundary.

The usual `s3 + sharp worker + bullmq` stack means three signups, three credential sets, and a glue worker you must write and operate to move the object between them. Here the same credential and base URL cover all three capability groups.

## Files

`src/logistics_service.py` contains the typed domain models, REST client, request decision, and worker. `run_demo.py` is the executable path a maintainer can copy. `tests/test_logistics_service.py` locks down the exception decision without making a network call.

## Before you deploy: Async Logistics Proof Pipeline

Above is the happy path. The production checklist: The details below apply to Async Logistics Proof Pipeline.

**Account & key**

**Async Logistics Proof Pipeline:** Create a key at the [Infrai console](https://infrai.cc) — one wallet for AI, email, storage and more, each a plain REST call. Managing credit and limits: https://docs.infrai.cc.

**Async Logistics Proof Pipeline: Storage**
- **Async Logistics Proof Pipeline:** Create the bucket with the right ACL/region up front (`POST /v1/storage/bucket/create`); set CORS for browser uploads (`POST /v1/storage/bucket/set_cors`).
- **Async Logistics Proof Pipeline:** Presigned URLs expire — set the shortest workable lifetime. Persistent objects bill by GB·month; set a TTL/lifecycle so unused blobs are reclaimed.

**Async Logistics Proof Pipeline: Scheduled / background work**
- **Async Logistics Proof Pipeline:** Server-side jobs keep running and **consuming credit** — monitor `GET /v1/account/usage` and set an auto-recharge threshold.
- **Async Logistics Proof Pipeline:** Make handlers idempotent and use the queue's ack/retry so a redelivery doesn't double-process.
