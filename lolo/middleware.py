class RequestLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        print("\n=== Incoming Request ===")
        print(f"Path: {request.path}")
        print(f"Method: {request.method}")
        print("Headers:")
        for key, value in request.headers.items():
            print(f"  {key}: {value}")

        response = self.get_response(request)

        print("\n=== Outgoing Response ===")
        print(f"Status: {response.status_code}")
        print("Headers:")
        for key, value in response.items():
            print(f"  {key}: {value}")
        print("========================\n")
        return response