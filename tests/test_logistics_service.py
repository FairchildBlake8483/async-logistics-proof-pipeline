from src.logistics_service import ProofOfDelivery, ShipmentEvent, ShipmentRequest, should_process


def test_exception_stops_image_job_even_when_proof_exists() -> None:
    request = ShipmentRequest(
        shipment_id="SHP-7",
        event=ShipmentEvent("SHP-7", "delivered", "Ningbo"),
        proof=ProofOfDelivery("proofs/SHP-7.jpg", "image/jpeg"),
        exception="address mismatch",
    )
    assert should_process(request) is False


def test_delivered_proof_is_queued() -> None:
    request = ShipmentRequest(
        shipment_id="SHP-8",
        event=ShipmentEvent("SHP-8", "delivered", "Ningbo"),
        proof=ProofOfDelivery("proofs/SHP-8.jpg", "image/jpeg"),
    )
    assert should_process(request) is True
