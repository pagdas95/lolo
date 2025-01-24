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
            
        # Add these lines to see more details
        print("\nRequest Body:")
        try:
            print(request.body.decode('utf-8'))
        except:
            print("Could not decode body")
        
        print("\nRequest COOKIES:")
        print(request.COOKIES)

        response = self.get_response(request)

        print("\n=== Outgoing Response ===")
        print(f"Status: {response.status_code}")
        print("Headers:")
        for key, value in response.items():
            print(f"  {key}: {value}")
        
        # Add this to see response content
        try:
            print("\nResponse Content:")
            print(response.content.decode('utf-8'))
        except:
            print("Could not decode response content")
            
        print("========================\n")
        return response