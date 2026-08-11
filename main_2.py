import asyncio

from server_2 import main

reason, data = asyncio.run(main())
print("Server stopped because:", reason)
print("Rhino data:", data)