"""WebSocket communication for Creality K1."""
import asyncio
import websockets
import json
import logging
import time
from typing import Callable
from urllib.parse import urlparse

_LOGGER = logging.getLogger(__name__)

# WebSocket-related constants
MSG_TYPE_HEARTBEAT = "heart_beat"  # Heartbeat message
HEARTBEAT_INTERVAL = 5  # Seconds
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
        self._pending_timelapse_futures = []

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

            # Check for timelapse video list
            video_list = self._find_elapse_video_list(data)
            if video_list is not None:
                parsed_videos = self._parse_timelapse_list(video_list)
                # Resolve any pending futures
                while self._pending_timelapse_futures:
                    fut = self._pending_timelapse_futures.pop(0)
                    if not fut.done():
                        fut.set_result(parsed_videos)
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

    def _find_elapse_video_list(self, data: dict) -> list | None:
        """Recursively search for elapseVideoList key in data."""
        if "elapseVideoList" in data:
            return data["elapseVideoList"]
        if "result" in data and isinstance(data["result"], dict):
            if "elapseVideoList" in data["result"]:
                return data["result"]["elapseVideoList"]
        return None

    def _parse_timelapse_list(self, video_list: list) -> list[dict]:
        """Parse the raw video list and generate download URLs."""
        try:
            parsed_url = urlparse(self.url)
            host = parsed_url.hostname
            if not host:
                host = self.url.split("://")[-1].split(":")[0]
        except Exception:
            host = "localhost"

        import re
        from datetime import datetime, timezone

        video_urls = []
        for video in video_list:
            if not isinstance(video, dict):
                continue
            filename = video.get("videoname")
            gcode = video.get("gcodename")
            if filename:
                url = f"http://{host}/downloads/video/{filename}"
                item = {"gcode": gcode, "url": url}

                # Attempt to extract start timestamp from filename prefix (Unix timestamp)
                match = re.match(r"^(\d+)", filename)
                if match:
                    try:
                        ts = int(match.group(1))
                        item["timestamp"] = ts
                        # Convert to UTC ISO-8601 string
                        dt = datetime.fromtimestamp(ts, timezone.utc)
                        item["start_time"] = dt.isoformat()
                    except Exception:
                        pass
                
                video_urls.append(item)
        return video_urls

    async def request_timelapses(self) -> None:
        """Send a request to the printer to get the list of timelapses (response via callback)."""
        await self.send_message({
            "method": "get",
            "params": {
                "reqGcodeFile": 1,
                "reqGcodeList": 1,
                "reqHistory": 1,
                "reqElapseVideoList": 1,
                "reqPrintObjects": 1,
                "reqMaterialBoxsInfo": 1,
                "boxsInfo": 1,
                "reqMaterials": 1,
                "boxConfig": {}
            }
        })

    async def get_timelapses(self, timeout: float = WS_OPERATION_TIMEOUT) -> list[dict]:
        """Get the list of timelapse videos from the printer."""
        if not self.is_connected:
            await self.connect()
            if not self.is_connected:
                _LOGGER.warning("Could not connect to printer to fetch timelapses")
                return []

        future = asyncio.get_running_loop().create_future()
        self._pending_timelapse_futures.append(future)

        try:
            await self.request_timelapses()
            video_list = await asyncio.wait_for(future, timeout=timeout)
            return video_list
        except asyncio.TimeoutError:
            _LOGGER.warning("Timeout waiting for timelapse list response")
            return []
        except Exception as e:
            _LOGGER.exception("Error fetching timelapse list: %s", e)
            return []
        finally:
            if future in self._pending_timelapse_futures:
                self._pending_timelapse_futures.remove(future)
