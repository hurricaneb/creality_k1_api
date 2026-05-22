# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.0.3] - 2026-05-22

### Added
- Asynchronous `get_timelapses()` and `request_timelapses()` to fetch the list of recorded timelapse videos from the printer.
- Automatic extraction of the print start time (Unix timestamp and UTC ISO-8601 string) from the timelapse filename prefix.
- Robust hostname parsing from the WebSocket URL to generate clean HTTP download links for the timelapses.
- Project rule `.project_rules.md` to keep all code comments and output text strictly in English.

### Changed
- Translated all Swedish code comments in `client.py` to English for open-source consistency.
- Corrected and updated package usage examples in `README.md`.

## [0.0.2] - 2026-04-20

### Added
- `test_api.py` script to easily test and demonstrate the WebSocket API against a real printer.

### Changed
- Refactored `client.py` logging to use Python's recommended lazy string formatting instead of f-strings.
- Updated the default port in `test_api.py` to `9999` based on real world testing.

### Fixed
- Fixed an issue in `client.py` where tasks would incorrectly cancel themselves during the disconnect sequence, which prevented the WebSocket from closing cleanly.
- Fixed an unhandled `CancelledError` and `TimeoutError` in `receive_messages` and `send_heartbeat` which previously resulted in noisy log outputs.
- Added support for receiving `bytes` payloads in `handle_message` to prevent decode errors if the WebSocket server sends binary data.

## [0.0.1] - Initial Release

### Added
- Initial WebSocket client implementation (`CrealityK1Client`).
- Basic unit tests for the client (`tests/test_client.py`).
