# Creality K1 API

A Python package to communicate with the Creality K1 3D printer.

## Installation

```bash
pip install creality_k1_api
```

## Usage

```python
import asyncio
from creality_k1_api import CrealityK1Client

async def main():
    client = CrealityK1Client("192.168.1.100", 9999)
    await client.connect()

    # Your code here

    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
```
