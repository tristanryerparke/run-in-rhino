import asyncio

from run_in_rhino.server import RunContext, main

rc = RunContext(env={"mf": "mf1000"})


reason, data = asyncio.run(main(context=rc))
print("Server stopped because:", reason)
print("Rhino data:", data)
