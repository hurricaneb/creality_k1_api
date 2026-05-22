# Creality K1 API

A Python package to communicate with the Creality K1 / K1 Max 3D printer over WebSocket.

## Installation

```bash
pip install creality_k1_api
```

## Usage

### Basic Connection

The client is asynchronous and handles connection management, heartbeats, and message processing. You must provide a callback function that will receive parsed JSON updates from the printer.

```python
import asyncio
from creality_k1_api import CrealityK1Client

def on_new_data(data: dict):
    # Handle incoming telemetry updates (temperature, status, progress, etc.)
    print("Received update:", list(data.keys()))

async def main():
    # K1 WebSocket uses port 9999 by default
    client = CrealityK1Client("ws://192.168.10.161:9999", on_new_data)
    
    await client.connect()
    
    # Listen to live updates for 10 seconds
    await asyncio.sleep(10)

    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
```

### Retrieving Timelapse Videos

You can fetch the list of recorded timelapse videos from the printer. The client dynamically parses the printer's hostname to construct complete HTTP download links, and extracts the print start time from the video filename.

```python
import asyncio
from creality_k1_api import CrealityK1Client

async def main():
    client = CrealityK1Client("ws://192.168.10.161:9999", lambda data: None)
    
    await client.connect()
    
    if client.is_connected:
        # Fetch the list of timelapses (with a 5-second timeout)
        videos = await client.get_timelapses(timeout=5.0)
        
        print(f"Found {len(videos)} timelapse videos:")
        for video in videos:
            print(f"Gcode:      {video['gcode']}")
            print(f"Download:   {video['url']}")
            print(f"Start Time: {video.get('start_time')} (UTC)")
            print("-" * 50)
            
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
```

Each timelapse item in the returned list contains:
* `gcode`: The name of the Gcode file that was printed (e.g. `Cover_PLA.gcode`).
* `url`: The full HTTP download URL for the `.mp4` video (e.g. `http://192.168.10.161/downloads/video/1764698892.mp4`).
* `timestamp`: The Unix timestamp when the print job started (extracted from the filename, e.g. `1764698892`).
* `start_time`: The ISO-8601 UTC formatted datetime representation of the start time (e.g. `2025-12-02T18:08:12+00:00`).
