"""SBPL command tokenizer - parses raw byte streams into command objects."""

from dataclasses import dataclass, field
from typing import Optional
import re

ESC = 0x1B
STX = 0x02
ETX = 0x03


@dataclass
class SBPLCommand:
    """Represents a single parsed SBPL command."""
    command: str  # e.g., "A", "Z", "H", "V", "XB", etc.
    params: str = ""  # raw parameter string
    raw: bytes = b""  # raw bytes of this command


@dataclass
class SBPLJob:
    """Represents a complete print job (<A> to <Z>)."""
    commands: list = field(default_factory=list)
    raw_data: bytes = b""
    quantity: int = 1


# Multi-character commands sorted longest-first so we match greedily
MULTI_CHAR_COMMANDS = sorted([
    "XU", "XS", "XM", "XB", "XL",
    "WB", "WL",
    "OA", "OB",
    "BC", "BG", "BI", "BP", "BF", "BD", "BT", "BW",
    "FW",
    "GP", "GM",
    "WD",
    "PS", "PR",
    "ID", "WK",
    "NUL",
    "A1", "A3",
    "CS",
    "PG",
    "FC",
    "2S",
    "PO",
    "TG",
    "IG",
    "PH",
    "PM",
    "RF",
    "KC",
    "YE",
    "AX",
    "AR",
    "EP",
    "WT", "WP", "WA",
    "RD",
    "$=",
    "~A", "~B",
    "#E",
], key=len, reverse=True)

SINGLE_CHAR_COMMANDS = set("AZQHVPLEBDGFCMSUJqe%$(&/0@*")


def tokenize_sbpl(data: bytes) -> list:
    """Tokenize raw SBPL data into a list of SBPLCommand objects."""
    commands = []
    pos = 0
    length = len(data)

    while pos < length:
        byte = data[pos]

        # Skip STX/ETX framing
        if byte == STX or byte == ETX:
            pos += 1
            continue

        # ESC sequence - start of a command
        if byte == ESC:
            pos += 1
            if pos >= length:
                break

            cmd, params, new_pos = _parse_command(data, pos)
            if cmd:
                commands.append(SBPLCommand(
                    command=cmd,
                    params=params,
                    raw=data[pos - 1:new_pos],
                ))
            pos = new_pos
            continue

        # Skip any non-ESC bytes (could be CR/LF or other control chars)
        pos += 1

    return commands


def _parse_command(data: bytes, pos: int) -> tuple:
    """Parse a command starting at pos (after ESC byte).

    Returns (command_name, params_string, new_position).
    """
    length = len(data)

    # Try multi-character commands first (longest match)
    for mc in MULTI_CHAR_COMMANDS:
        mc_bytes = mc.encode('ascii')
        end = pos + len(mc_bytes)
        if end <= length and data[pos:end] == mc_bytes:
            param_start = end
            params, new_pos = _extract_params(data, param_start, mc)
            return mc, params, new_pos

    # Single character command
    if pos < length:
        ch = chr(data[pos])
        if ch in SINGLE_CHAR_COMMANDS:
            param_start = pos + 1
            params, new_pos = _extract_params(data, param_start, ch)
            return ch, params, new_pos

    # Unknown - skip
    return None, "", pos + 1


def _extract_params(data: bytes, pos: int, cmd: str) -> tuple:
    """Extract parameters for a command until the next ESC, STX, ETX, or end.

    Returns (params_string, new_position).
    """
    length = len(data)
    start = pos

    # Commands with no parameters
    if cmd in ("A", "Z", "PS", "PR", "&", "/", "0", "J"):
        return "", pos

    # For font commands, everything until next ESC/STX/ETX is the data
    while pos < length:
        byte = data[pos]
        if byte == ESC or byte == STX or byte == ETX:
            break
        # CR (0x0D) can be part of auto line feed data, so we include it
        pos += 1

    try:
        params = data[start:pos].decode('ascii', errors='replace')
    except Exception:
        params = data[start:pos].decode('latin-1', errors='replace')

    return params, pos


def extract_jobs(data: bytes) -> list:
    """Extract complete print jobs from raw data.

    Each job is an <A>...<Z> block. Returns list of SBPLJob objects.
    """
    commands = tokenize_sbpl(data)
    jobs = []
    current_commands = []
    in_job = False

    for cmd in commands:
        if cmd.command == "A":
            in_job = True
            current_commands = [cmd]
        elif cmd.command == "Z":
            if in_job:
                current_commands.append(cmd)
                job = SBPLJob(commands=current_commands, raw_data=data)
                # Extract quantity from Q command
                for c in current_commands:
                    if c.command == "Q":
                        try:
                            job.quantity = int(c.params.strip())
                        except ValueError:
                            job.quantity = 1
                jobs.append(job)
                current_commands = []
                in_job = False
        elif in_job:
            current_commands.append(cmd)

    return jobs
