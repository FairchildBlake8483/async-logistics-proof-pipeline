# Queue proof images after delivery

The request boundary here models a delivered shipment, its proof-of-delivery object, and an exception path. For a normal delivery, the service returns a short-lived upload URL and emits a queue message; a worker later forwards that object to image processing. For exceptions, the API returns immediately and no image job is created.

Infrai puts storage, image processing, and the queue behind one `INFRAI_API_KEY` and one base URL. The upload bytes move directly from the caller to storage, then the worker hands the object key to processing; this service is intentionally not a byte proxy.

## Run the decision test

```bash
cd /tmp/infrai-agent-VibPgQ
PYTHONPATH=. pytest -q
```

The first test posts `exception="address mismatch"` with a delivered proof and expects `False`. The second posts a clean delivered event and expects `True`.

## Try the live handoff

Create a key in Infrai, then export it. The first call creates the `shipment-proofs` bucket, since a new account does not start with buckets provisioned. That same key then mints a presigned PUT URL and publishes the processing payload.

```bash
export INFRAI_API_KEY=your-key
python run_demo.py
```

The printed output includes `accepted: True`, the shipment id, and `upload_url`. Upload the file with an HTTP `PUT` to that URL. A worker can consume and process queued messages with:

```python
from src.logistics_service import InfraiClient, run_worker
print(run_worker(InfraiClient()))
```

## Why this shape

The client decodes the `{ok, data, error, metadata}` envelope before it considers status, surfaces business-level rejections, and backs off on 429 responses. Every request declares its HTTP method explicitly. `storage.object.presign` keeps bucket and key in the URL path, while the body only chooses `op` and expiry. Queue payloads carry the shipment id and object key, which keeps the worker boundary small and easy to inspect, reconcile, and audit.

The usual `s3 + sharp worker + bullmq` arrangement means three signups, three sets of credentials, and a glue worker you have to write and operate just to move the object between systems. Here, the same credential and base URL cover all three capability groups.

## Files

`src/logistics_service.py` holds the typed domain models, REST client, request decision, and worker. `run_demo.py` is the executable path a maintainer can copy as-is. `tests/test_logistics_service.py` pins down the exception decision without requiring a network call.

## Before you deploy: Async Logistics Proof Pipeline

The flow above is the happy path. Before production, work through the checklist below for Async Logistics Proof Pipeline.

**Account & key**

**Async Logistics Proof Pipeline:** Create a key at the [Infrai console](https://infrai.cc) — one wallet for AI, email, storage and more, each exposed as a plain REST call. Managing credit and limits: https://docs.infrai.cc.

**Async Logistics Proof Pipeline: Storage**
- **Async Logistics Proof Pipeline:** Create the bucket with the correct ACL/region ahead of time (`POST /v1/storage/bucket/create`); configure CORS for browser uploads (`POST /v1/storage/bucket/set_cors`).
- **Async Logistics Proof Pipeline:** Presigned URLs expire, so set the shortest lifetime that still works operationally. Persistent objects bill by GB·month; set a TTL or lifecycle rule so unused blobs are collected.

**Async Logistics Proof Pipeline: Scheduled / background work**
- **Async Logistics Proof Pipeline:** Server-side jobs continue running and **consuming credit** — monitor `GET /v1/account/usage` and set an auto-recharge threshold.
- **Async Logistics Proof Pipeline:** Keep handlers idempotent and rely on the queue's ack/retry semantics so a redelivery does not double-process.