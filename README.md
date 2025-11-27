# HTTP Download Check

A Python tool to test and compare download speeds across different HTTP protocols (HTTP/1.1, HTTP/2, and HTTP/3 QUIC) concurrently.

## Features

- **Protocol Support**: Tests HTTP/1.1 (Plain & TLS), HTTP/2, and HTTP/3 (QUIC).
- **Capability Detection**: Automatically detects server support for HTTP/2 (via ALPN) and HTTP/3 (via Alt-Svc headers).
- **Concurrent Testing**: Runs all supported protocol tests simultaneously to compare performance.
- **Live Dashboard**: Uses [Rich](https://github.com/Textualize/rich) to display live progress bars, download speeds, and time remaining.
- **Smart Handling**: 
  - Detects and reports redirects without following them for plain HTTP (to avoid skewing results).
  - Gracefully handles interruptions (Ctrl+C).

## Prerequisites

- Python 3.9+
- Linux/macOS (for the shell script)

## Installation & Usage

The included `run.sh` script handles virtual environment creation and dependency installation automatically.

1. **Clone the repository:**
   ```bash
   git clone https://github.com/jordantrizz/http-download-check.git
   cd http-download-check
   ```

2. **Run the test:**
   Make the script executable (first time only) and run it with a target URL:
   ```bash
   chmod +x run.sh
   ./run.sh https://example.com/large-file.zip
   ```

   The script will:
   - Create a `.venv` virtual environment (if missing).
   - Install dependencies (`curl_cffi`, `rich`).
   - Check server capabilities.
   - Start concurrent downloads.

## Example Output

```text
--- Checking Capabilities for www.example.com ---
HTTP (Port 80): Open
HTTPS (Port 443): Open. Negotiated ALPN: h2
HTTP/3: Advertised in Alt-Svc (h3=":443"; ma=86400)

--- Starting Concurrent Download Tests ---
HTTP/1.1 (Plain): Redirected to https://www.example.com/file.zip
HTTP/1.1 (TLS) ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 15% • 150/1000 MB • 12.5 MB/s • 0:01:10
  HTTP/2 (TLS) ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 20% • 200/1000 MB • 18.0 MB/s • 0:00:45
 HTTP/3 (QUIC) ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 22% • 220/1000 MB • 20.5 MB/s • 0:00:40
```

## Dependencies

- [curl_cffi](https://github.com/yifeikong/curl_cffi): For low-level curl bindings supporting HTTP/3 and impersonation.
- [rich](https://github.com/Textualize/rich): For the terminal UI and progress bars.
