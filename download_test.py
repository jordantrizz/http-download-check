import argparse
import time
import socket
import ssl
import sys
import asyncio
from urllib.parse import urlparse
from curl_cffi import requests, CurlHttpVersion, CurlError
from curl_cffi.requests import AsyncSession
from rich.progress import (
    Progress,
    TextColumn,
    BarColumn,
    TaskProgressColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
    DownloadColumn,
)
from rich.console import Console

console = Console()

def get_base_url(url):
    """Extracts hostname and path to construct http/https variants."""
    parsed = urlparse(url)
    if not parsed.scheme:
        url = "https://" + url
        parsed = urlparse(url)
    
    hostname = parsed.hostname
    path = parsed.path if parsed.path else "/"
    return hostname, path

def check_server_capabilities(hostname):
    console.print(f"\n[bold blue]--- Checking Capabilities for {hostname} ---[/bold blue]")
    
    capabilities = {
        'http': False,
        'https': False,
        'h1_tls': False,
        'h2_tls': False,
        'h3_tls': False
    }

    # 1. Check HTTP (Port 80)
    try:
        with socket.create_connection((hostname, 80), timeout=5):
            capabilities['http'] = True
            console.print("[green]HTTP (Port 80): Open[/green]")
    except Exception:
        console.print("[red]HTTP (Port 80): Closed/Unreachable[/red]")

    # 2. Check HTTPS (Port 443) and ALPN
    try:
        context = ssl.create_default_context()
        context.set_alpn_protocols(['h2', 'http/1.1'])
        with socket.create_connection((hostname, 443), timeout=5) as sock:
            with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                capabilities['https'] = True
                alpn = ssock.selected_alpn_protocol()
                console.print(f"[green]HTTPS (Port 443): Open. Negotiated ALPN: {alpn}[/green]")
                
                if alpn == 'http/1.1':
                    capabilities['h1_tls'] = True
                elif alpn == 'h2':
                    capabilities['h2_tls'] = True
                    capabilities['h1_tls'] = True # H2 implies H1 fallback usually
    except Exception as e:
        console.print(f"[red]HTTPS (Port 443): Failed ({e})[/red]")

    # 3. Check HTTP/3 (Alt-Svc)
    if capabilities['https']:
        try:
            # We use a quick HEAD request to check headers
            url = f"https://{hostname}"
            r = requests.head(url, timeout=5, impersonate="chrome")
            alt_svc = r.headers.get("Alt-Svc")
            if alt_svc and ("h3" in alt_svc or "quic" in alt_svc):
                console.print(f"[green]HTTP/3: Advertised in Alt-Svc ({alt_svc})[/green]")
                capabilities['h3_tls'] = True
            else:
                console.print("[yellow]HTTP/3: Not advertised in Alt-Svc[/yellow]")
        except Exception as e:
            console.print(f"[red]HTTP/3 Check Failed: {e}[/red]")

    return capabilities

async def download_task(session: AsyncSession, url: str, version_name: str, curl_version: CurlHttpVersion, progress: Progress, task_id: int, allow_redirects: bool):
    """
    Downloads a file asynchronously and updates the specific rich progress task.
    """
    try:
        # stream=True is crucial for large files to avoid loading them into RAM
        # impersonate="chrome" helps avoid some bot protections and ensures modern TLS
        response = await session.get(url, http_version=curl_version, stream=True, impersonate="chrome", timeout=300, allow_redirects=allow_redirects)
            
        if 300 <= response.status_code < 400:
            progress.console.print(f"[yellow]{version_name}: Redirected to {response.headers.get('Location')}[/yellow]")
            progress.remove_task(task_id)
            return

        if response.status_code != 200:
            progress.console.print(f"[red]Failed {version_name}: Status {response.status_code}[/red]")
            progress.remove_task(task_id)
            return

        # Get total size from headers if available
        total_length = int(response.headers.get("Content-Length", 0))
        
        # Update the task with the total size so rich can calculate percentage
        progress.update(task_id, total=total_length)
        progress.start_task(task_id)
        
        # Use aiter_content for async iteration
        async for chunk in response.aiter_content(chunk_size=8192):
            # advance adds to the current progress
            progress.update(task_id, advance=len(chunk))
                
    except CurlError as e:
        progress.console.print(f"[red]CurlError {version_name}: {e}[/red]")
    except Exception as e:
        progress.console.print(f"[red]Error {version_name}: {e}[/red]")

async def run_concurrent_tests(tests_to_run):
    # Configure the layout of the progress bars
    with Progress(
        TextColumn("[bold blue]{task.fields[version_name]}", justify="right"),
        BarColumn(bar_width=None),
        "[progress.percentage]{task.percentage:>3.1f}%",
        "•",
        DownloadColumn(),
        "•",
        TransferSpeedColumn(),
        "•",
        TimeRemainingColumn(),
        console=console
    ) as progress:
        
        async with AsyncSession() as session:
            tasks = []
            
            for url, name, version, allow_redirects in tests_to_run:
                # Add a task for this specific URL
                task_id = progress.add_task(
                    "download", 
                    version_name=name, 
                    start=False # Start only when connection is established
                )
                
                # Create the coroutine but don't await it yet
                tasks.append(
                    download_task(session, url, name, version, progress, task_id, allow_redirects)
                )
            
            # Run all downloads concurrently
            await asyncio.gather(*tasks)

def main():
    parser = argparse.ArgumentParser(description="HTTP Download Tester (H1, H2, H3)")
    parser.add_argument("url", help="The URL or hostname to test")
    args = parser.parse_args()
    
    hostname, path = get_base_url(args.url)
    
    # Step 1: Pre-check
    caps = check_server_capabilities(hostname)
    
    console.print("\n[bold]--- Starting Concurrent Download Tests ---[/bold]")
    
    # Define tests
    # Format: (Scheme, Protocol Name, Curl Version, Allow Redirects)
    tests_to_run = []

    # HTTP Plaintext
    if caps['http']:
        tests_to_run.append((f"http://{hostname}{path}", "HTTP/1.1 (Plain)", CurlHttpVersion.V1_1, False))

    # HTTPS
    if caps['https']:
        # HTTP/1.1 over TLS
        if caps['h1_tls']:
            tests_to_run.append((f"https://{hostname}{path}", "HTTP/1.1 (TLS)", CurlHttpVersion.V1_1, True))
        
        # HTTP/2 over TLS
        if caps['h2_tls']:
            tests_to_run.append((f"https://{hostname}{path}", "HTTP/2 (TLS)", CurlHttpVersion.V2_0, True))
        
        # HTTP/3 (QUIC)
        if caps['h3_tls']:
            tests_to_run.append((f"https://{hostname}{path}", "HTTP/3 (QUIC)", CurlHttpVersion.V3, True))

    if not tests_to_run:
        console.print("[red]No valid protocols/schemes detected to test.[/red]")
        return

    # Run async loop
    try:
        asyncio.run(run_concurrent_tests(tests_to_run))
    except KeyboardInterrupt:
        console.print("\n[yellow]Tests cancelled by user.[/yellow]")

if __name__ == "__main__":
    main()
