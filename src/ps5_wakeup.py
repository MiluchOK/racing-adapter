#!/usr/bin/env python3
"""
PS5 Wake-up Script

Wakes up a PS5 console from Rest Mode using the Device Discovery Protocol.

Configuration:
  Set PS5_HOST and PS5_CREDENTIAL environment variables, or edit the config below.

Requirements:
- PS5 must be in Rest Mode (not fully powered off)
- PS5 must have Remote Play enabled and linked
"""

import os
import socket
import sys
import time

# =============================================================================
# CONFIGURATION - Edit these values or set environment variables
# =============================================================================
PS5_HOST = os.environ.get("PS5_HOST", "10.0.0.215")
PS5_CREDENTIAL = os.environ.get("PS5_CREDENTIAL", "xzc")
# =============================================================================

DDP_PORT = 9302  # PS5 DDP port
DDP_VERSION = "00030010"


def create_wakeup_message(credential: str) -> bytes:
    """Create a DDP wakeup message."""
    msg = "WAKEUP * HTTP/1.1\n"
    msg += "client-type:vr\n"
    msg += "auth-type:C\n"
    msg += "model:w\n"
    msg += "app-type:r\n"
    msg += f"user-credential:{credential}\n"
    msg += f"device-discovery-protocol-version:{DDP_VERSION}\n"
    return msg.encode("utf-8")


def create_search_message() -> bytes:
    """Create a DDP search message."""
    msg = "SRCH * HTTP/1.1\n"
    msg += f"device-discovery-protocol-version:{DDP_VERSION}\n"
    return msg.encode("utf-8")


def get_status(host: str) -> str:
    """Check if PS5 is on or in standby."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(2.0)
        sock.sendto(create_search_message(), (host, DDP_PORT))

        data, _ = sock.recvfrom(4096)
        sock.close()

        text = data.decode("utf-8")
        if "200" in text:
            return "on"
        elif "620" in text:
            return "standby"
        return "unknown"
    except socket.timeout:
        return "unreachable"
    except Exception as e:
        return f"error: {e}"


def wakeup(host: str, credential: str) -> bool:
    """Send wakeup command to PS5."""
    print(f"Waking up PS5 at {host}...")

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(5.0)

        wakeup_msg = create_wakeup_message(credential)

        # Send wakeup multiple times
        for _ in range(5):
            sock.sendto(wakeup_msg, (host, DDP_PORT))
            time.sleep(0.3)

        print("Wakeup command sent!")

        # Wait for PS5 to turn on
        print("Waiting for PS5...")
        for _ in range(15):
            time.sleep(2)
            status = get_status(host)
            if status == "on":
                print("PS5 is now ON!")
                sock.close()
                return True

        sock.close()
        print("PS5 did not respond. It may still be turning on.")
        return False

    except Exception as e:
        print(f"Error: {e}")
        return False


def main():
    if not PS5_HOST:
        print("Error: PS5_HOST not configured")
        print("Edit src/ps5_wakeup.py or set PS5_HOST environment variable")
        sys.exit(1)

    if not PS5_CREDENTIAL:
        print("Error: PS5_CREDENTIAL not configured")
        print("\nTo get your credential:")
        print("1. Install PS Remote Play and link it with your PS5")
        print("2. Find credential in:")
        print("   macOS: ~/Library/Application Support/PS Remote Play/")
        print("   Windows: %AppData%/Local/PS Remote Play/")
        print("3. Set PS5_CREDENTIAL environment variable or edit this script")
        sys.exit(1)

    # Check current status
    print(f"Checking PS5 at {PS5_HOST}...")
    status = get_status(PS5_HOST)

    if status == "on":
        print("PS5 is already on!")
        return
    elif status == "standby":
        print("PS5 is in standby mode")
    elif status == "unreachable":
        print("PS5 not responding (may be off or wrong IP)")
        print("Attempting wakeup anyway...")
    else:
        print(f"Status: {status}")

    wakeup(PS5_HOST, PS5_CREDENTIAL)


if __name__ == "__main__":
    main()
