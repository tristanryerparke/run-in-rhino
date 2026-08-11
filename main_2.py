import asyncio

from server_2 import main, RunContext

rc = RunContext(env={"mf":"mf1000"})


reason, data = asyncio.run(main(context=rc))
print("Server stopped because:", reason)
print("Rhino data:", data)