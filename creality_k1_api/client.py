"""WebSocket communication for Creality K1."""
import asyncio
import websockets
import json
import logging
import time
from typing import Callable

_LOGGER = logging.getLogger(__name__)

# WebSocket-relaterade konstanter
MSG_TYPE_HEARTBEAT = "heart_beat"  # Hjärtslagsmeddelande
HEARTBEAT_INTERVAL = 5  # Sekunder
WS_OPERATION_TIMEOUT = 10 # seconds

class CrealityK1Client:
    """Handles WebSocket communication with the Creality K1."""

    def __init__(
        self,
        url: str,
        new_data_callback: Callable[[dict], None],
        ) -> None:
        """Initialize the WebSocket client."""
        self.url = url
        self.new_data_callback = new_data_callback
        self.ws = None
        self.heartbeat_task = None
        self.receive_task = None
        self._is_connected = False
        self._connect_task = None
        self._is_disconnecting = False

    @property
    def is_connected(self) -> bool:
        return self._is_connected and self.ws is not None

    async def connect(self) -> None:
        """Attempts to establish a WebSocket connection."""
        if not self._is_disconnecting:
            if self._connect_task and not self._connect_task.done():
                # Already trying to connect
                _LOGGER.debug("Connection attempt already in progress.")
                return
            self._connect_task = asyncio.create_task(self._do_connect())
            await self._connect_task

    async def _do_connect(self) -> None:
        try:
            self.ws = await asyncio.wait_for(websockets.connect(self.url, ping_interval=None, ping_timeout=None), timeout=WS_OPERATION_TIMEOUT)
            self._is_connected = True
            _LOGGER.info("Connected to %s", self.url)
            self.heartbeat_task = asyncio.create_task(self.send_heartbeat())
            self.receive_task = asyncio.create_task(self.receive_messages())
        except OSError as e: # Network errors, e.g., Connection Refused
            # This is the usual exception if the printer is powered off
            # so don't flood the logs unless debugging is turned on
            self._is_connected = False
            _LOGGER.debug("Failed to connect to WebSocket: %s", e)
        except (
            websockets.exceptions.ConnectionClosed,
            websockets.exceptions.InvalidURI,
            asyncio.TimeoutError
        ) as e:
            self._is_connected = False
            _LOGGER.warning("Failed to connect to WebSocket: %s", e)
        except Exception as e:
            self._is_connected = False
            _LOGGER.exception("Unhandled error during WebSocket connection: %s", e)

    async def send_heartbeat(self) -> None:
        """Send a heartbeat message to the server periodically."""
        try:
            while self.is_connected:
                await self.send_message({"ModeCode": MSG_TYPE_HEARTBEAT, "msg": time.time()})
                await asyncio.sleep(HEARTBEAT_INTERVAL)
        except asyncio.CancelledError:
            pass  # Expected upon disconnect
        except Exception as e:
            _LOGGER.error("Error sending heartbeat: %s", e)
            await self.disconnect()

    async def receive_messages(self) -> None:
        try:
            while self.is_connected:
                try:
                    message = await asyncio.wait_for(self.ws.recv(), timeout=WS_OPERATION_TIMEOUT)
                    if message is None:
                        _LOGGER.warning("Received None message from server")
                        break  # Break the loop to disconnect
                    await self.handle_message(message)
                except websockets.exceptions.ConnectionClosedOK:
                    _LOGGER.debug("Connection closed by server")
                    break  # Break the loop to disconnect
                except asyncio.TimeoutError:
                    _LOGGER.warning("Timeout receiving message")
                    break  # Break the loop to disconnect
                except Exception as e:
                    _LOGGER.error("Error receiving message: %s", e)
                    break  # Break the loop to disconnect
        except asyncio.CancelledError:
            pass  # Expected upon disconnect
        finally:
            await self.disconnect()

    async def handle_message(self, message: str | bytes) -> None:
        """Process a received message."""
        if isinstance(message, bytes):
            try:
                message = message.decode("utf-8")
            except UnicodeDecodeError:
                _LOGGER.warning("Received invalid UTF-8 bytes message")
                return

        # Log RAW data in DEBUG-mode
        _LOGGER.debug("Raw message received: %s", message)
        if message.strip().lower() == "ok":
            _LOGGER.debug("Received 'ok' acknowledgment.")
            # We don't need to do anything more so we stop here
            return
        # If not "ok", try it as JSON
        try:
            data = json.loads(message)
            _LOGGER.debug("Received Parsed JSON: %s", data)
            # Check if it is HEARTBEAT message
            if data.get("ModeCode") == MSG_TYPE_HEARTBEAT:
                _LOGGER.debug("Received heartbeat response")
                # We don't need to do anything with this data
                return
            # If it is JSON and not heartbeat, process the new data using callback
            self.new_data_callback(data)
        except json.JSONDecodeError:
            # Log if it is not JSON and not "ok" message
            _LOGGER.warning("Invalid JSON received (and not 'ok'): %s", message)
        except Exception as e:
            _LOGGER.error("Error handling non-JSON message '%s': %s", message, e)

    async def send_message(self, message: dict) -> None:
        """Send a message to the WebSocket server."""
        try:
            if self.is_connected:
                payload = json.dumps(message)
                await asyncio.wait_for(self.ws.send(payload), timeout=WS_OPERATION_TIMEOUT)
                _LOGGER.debug("Sent: %s", message)
            else:
                _LOGGER.warning("WebSocket connection is not active, could not send message")
        except Exception as e:
            _LOGGER.error("Error sending message: %s", e)
            await self.disconnect()

    async def disconnect(self) -> None:
        """Close the WebSocket connection and cleanup."""
        if not self._is_disconnecting:
            self._is_disconnecting = True
            
            current_task = asyncio.current_task()
            
            # Make sure system is not trying to connect
            if self._connect_task and not self._connect_task.done() and self._connect_task is not current_task:
                self._connect_task.cancel()
            self._connect_task = None
            
            self._is_connected = False
            
            if self.heartbeat_task and not self.heartbeat_task.done() and self.heartbeat_task is not current_task:
                self.heartbeat_task.cancel()
            self.heartbeat_task = None
            
            if self.receive_task and not self.receive_task.done() and self.receive_task is not current_task:
                self.receive_task.cancel()
            self.receive_task = None
            
            if self.ws:
                try:
                    # Attempt to close cleanly, with a timeout
                    await asyncio.wait_for(self.ws.close(), timeout=WS_OPERATION_TIMEOUT)
                except asyncio.TimeoutError:
                    _LOGGER.warning("Timeout during WebSocket close. Connection may not have closed cleanly.")
                except Exception as e:
                    _LOGGER.warning("Error during WebSocket close: %s", e)
                finally:
                    self.ws = None
            _LOGGER.info("WebSocket connection closed.")
            self._is_disconnecting = False
