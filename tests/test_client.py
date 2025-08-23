import asyncio
import unittest
from unittest.mock import patch, MagicMock, AsyncMock
import logging
import json

from creality_k1_api.client import CrealityK1Client, _LOGGER, MSG_TYPE_HEARTBEAT

# Disable logging for tests to keep output clean
_LOGGER.setLevel(logging.CRITICAL + 1)

class TestCrealityK1Client(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.mock_new_data_callback = MagicMock()
        self.client = CrealityK1Client("ws://localhost:9999", self.mock_new_data_callback)
        # An event that we can use to make mocks block indefinitely
        self.never_set_event = asyncio.Event()

    # --- Initialization and Connection Tests ---

    async def test_initialization(self):
        """Test that the client is initialized correctly."""
        self.assertEqual(self.client.url, "ws://localhost:9999")
        self.assertFalse(self.client.is_connected)
        self.assertIsNone(self.client.ws)

    @patch('creality_k1_api.client.websockets.connect', new_callable=AsyncMock)
    async def test_connect_success(self, mock_connect):
        """Test a successful connection."""
        mock_ws_connection = AsyncMock()
        mock_ws_connection.close = AsyncMock()
        # Make recv() wait forever, so the receive loop doesn't exit and disconnect.
        mock_ws_connection.recv.side_effect = self.never_set_event.wait
        mock_connect.return_value = mock_ws_connection

        await self.client.connect()

        self.assertTrue(self.client.is_connected)
        self.assertIsNotNone(self.client.ws)
        mock_connect.assert_awaited_once_with("ws://localhost:9999", ping_interval=None, ping_timeout=None)
        self.assertIsNotNone(self.client.heartbeat_task)
        self.assertIsNotNone(self.client.receive_task)

        await self.client.disconnect()
        self.assertFalse(self.client.is_connected)

    @patch('creality_k1_api.client.websockets.connect', new_callable=AsyncMock)
    async def test_connect_failure(self, mock_connect):
        """Test connection failure."""
        mock_connect.side_effect = OSError("Connection refused")

        await self.client.connect()

        self.assertFalse(self.client.is_connected)
        self.assertIsNone(self.client.ws)

    @patch('creality_k1_api.client.websockets.connect', new_callable=AsyncMock)
    async def test_disconnect(self, mock_connect):
        """Test disconnection."""
        mock_ws_connection = AsyncMock()
        mock_ws_connection.close = AsyncMock()
        # Make recv() wait forever.
        mock_ws_connection.recv.side_effect = self.never_set_event.wait
        mock_connect.return_value = mock_ws_connection

        await self.client.connect()
        self.assertTrue(self.client.is_connected)

        heartbeat_task = self.client.heartbeat_task
        receive_task = self.client.receive_task

        await self.client.disconnect()

        self.assertFalse(self.client.is_connected)
        self.assertIsNone(self.client.ws)
        mock_ws_connection.close.assert_awaited_once()

        # Give the event loop a chance to run the tasks so they can finish
        await asyncio.sleep(0)
        self.assertTrue(heartbeat_task.done())
        self.assertTrue(receive_task.done())

    async def test_disconnect_when_not_connected(self):
        """Test disconnecting when not connected should not raise an error."""
        await self.client.disconnect()
        self.assertFalse(self.client.is_connected)

    # --- Message Handling Tests ---

    @patch('creality_k1_api.client.websockets.connect', new_callable=AsyncMock)
    async def test_send_message_success(self, mock_connect):
        """Test sending a message successfully."""
        mock_ws_connection = AsyncMock()
        # Make recv() wait forever.
        mock_ws_connection.recv.side_effect = self.never_set_event.wait
        mock_connect.return_value = mock_ws_connection
        await self.client.connect()

        message_payload = {"test": "message"}
        await self.client.send_message(message_payload)

        # Use assert_any_await to ignore potential heartbeat messages
        mock_ws_connection.send.assert_any_await(json.dumps(message_payload))
        await self.client.disconnect()

    async def test_send_message_not_connected(self):
        """Test that sending a message fails when not connected."""
        message_payload = {"test": "message"}
        await self.client.send_message(message_payload)

    async def test_handle_json_message(self):
        """Test handling of a standard JSON message."""
        json_payload = '{"key": "value"}'
        await self.client.handle_message(json_payload)
        self.mock_new_data_callback.assert_called_once_with({"key": "value"})

    async def test_handle_ok_message(self):
        """Test that 'ok' messages are handled correctly."""
        await self.client.handle_message("ok")
        self.mock_new_data_callback.assert_not_called()

    async def test_handle_heartbeat_response(self):
        """Test that heartbeat responses are handled correctly."""
        heartbeat_response = f'{{"ModeCode": "{MSG_TYPE_HEARTBEAT}"}}'
        await self.client.handle_message(heartbeat_response)
        self.mock_new_data_callback.assert_not_called()

    async def test_handle_invalid_json(self):
        """Test that invalid JSON is handled gracefully."""
        await self.client.handle_message("this is not json")
        self.mock_new_data_callback.assert_not_called()

    @patch('creality_k1_api.client.websockets.connect', new_callable=AsyncMock)
    async def test_receive_messages_loop_handles_json(self, mock_connect):
        """Test the message receiving loop handles a JSON message."""
        mock_ws = AsyncMock()
        # Simulate receiving one message then getting cancelled
        mock_ws.recv.side_effect = ['{"data": "test"}', asyncio.CancelledError()]
        mock_connect.return_value = mock_ws

        await self.client.connect()
        # Give the receive task a moment to process the message
        await asyncio.sleep(0.01)

        self.mock_new_data_callback.assert_called_once_with({"data": "test"})

        await self.client.disconnect()


if __name__ == '__main__':
    unittest.main()
