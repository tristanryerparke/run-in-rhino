import asyncio
import unittest
from unittest import mock

import client
import run_in_rhino
import server


class EnvironmentUpgradeTests(unittest.IsolatedAsyncioTestCase):
    async def _receive_environment(self, environment):
        async def handle(reader, writer):
            await server._handshake(reader, writer, environment)
            writer.close()
            await writer.wait_closed()

        listener = await asyncio.start_server(handle, "127.0.0.1", 0)
        port = listener.sockets[0].getsockname()[1]
        original_port = client.PORT
        client.PORT = port
        try:
            return await asyncio.to_thread(client.receive_environment_sync)
        finally:
            client.PORT = original_port
            listener.close()
            await listener.wait_closed()

    async def test_upgrade_delivers_environment(self):
        environment = {"TACK_DEBUG": "1", "TACK_MODE": "preview"}

        received = await self._receive_environment(environment)

        self.assertEqual(received, environment)

    async def test_upgrade_without_environment_has_no_value(self):
        received = await self._receive_environment(None)

        self.assertIsNone(received)


class RhinoServerEnvironmentTests(unittest.TestCase):
    def test_no_environment_skips_the_environment_bootstrap(self):
        watcher = run_in_rhino.RhinoServer(environment={})

        with mock.patch.object(run_in_rhino.pipe, "run_rhino_script") as run_script:
            watcher.run_file("target.py")

        self.assertEqual(
            run_script.call_args_list,
            [
                mock.call(run_in_rhino._CLIENT_SCRIPT, pipe_path=None),
                mock.call("target.py", pipe_path=None),
            ],
        )

    def test_environment_bootstraps_once_before_the_target(self):
        watcher = run_in_rhino.RhinoServer(environment={"TACK_DEBUG": "1"})

        with mock.patch.object(run_in_rhino.pipe, "run_rhino_script") as run_script:
            watcher.run_file("first.py")
            watcher.run_file("second.py")

        self.assertEqual(
            run_script.call_args_list,
            [
                mock.call(run_in_rhino._CLIENT_SCRIPT, pipe_path=None),
                mock.call(run_in_rhino._ENVIRONMENT_SCRIPT, pipe_path=None),
                mock.call("first.py", pipe_path=None),
                mock.call("second.py", pipe_path=None),
            ],
        )


class EnvironmentValidationTests(unittest.TestCase):
    def test_empty_environment_disables_transport(self):
        self.assertIsNone(server.normalize_environment({}))

    def test_environment_requires_string_values(self):
        with self.assertRaises(TypeError):
            server.normalize_environment({"TACK_DEBUG": True})
