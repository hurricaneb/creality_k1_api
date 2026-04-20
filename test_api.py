import asyncio
import logging
import sys

# Configure logging so we can see all debugging information (DEBUG)
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

from creality_k1_api.client import CrealityK1Client

def on_new_data(data):
    """This function is called every time new data is received from the printer."""
    print("\n--- NEW DATA FROM PRINTER ---")
    print(data)
    print("-----------------------------\n")

async def main():
    if len(sys.argv) != 2:
        print("Usage: python test_api.py <PRINTER_IP>")
        print("Example: python test_api.py 192.168.1.100")
        sys.exit(1)

    ip = sys.argv[1]
    
    # K1 often uses port 9999 or a standard port for WebSocket depending on firmware.
    # It might also be worth trying "ws://{ip}:8899" or a specific path like "/websocket".
    # We first try the most common port for Fluidd/Mainsail (Moonraker) if rooted,
    # or the standard Creality port.
    url = f"ws://{ip}:9999" 

    print(f"Trying to connect to printer at: {url}")
    
    # Create an instance of the client
    client = CrealityK1Client(
        url=url,
        new_data_callback=on_new_data
    )

    # Connect
    await client.connect()

    if not client.is_connected:
        print(f"Could not connect to {url}.")
        print("Try another port (e.g., 8899, 1111, 7125) if 9999 doesn't work.")
        sys.exit(1)

    print("\nConnected! Listening for data. Press Ctrl+C to abort.\n")

    try:
        # Keep the program alive to listen for messages
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("\nAborting...")
    finally:
        # Close the connection cleanly
        await client.disconnect()

if __name__ == "__main__":
    # Start our async main-loop
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
