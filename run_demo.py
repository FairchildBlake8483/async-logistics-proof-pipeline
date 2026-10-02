from src.logistics_service import InfraiClient, accept_upload, example_request


if __name__ == "__main__":
    print(accept_upload(InfraiClient(), example_request()))
