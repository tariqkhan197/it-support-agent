"""
Known error-code knowledge base.

A small, curated lookup of common, well-documented error codes so the OCR
diagnosis pipeline can give an immediately accurate answer without relying
on the LLM to recall (and potentially hallucinate) specific code meanings.
Codes not found here are still passed to the specialist agent, which
reasons about them using general knowledge and any retrieved KB context.
"""

KNOWN_ERROR_CODES: dict[str, dict] = {
    # ---- BSOD stop codes ----
    "CRITICAL_PROCESS_DIED": {
        "code_type": "bsod_stop_code",
        "description": "A critical Windows system process terminated unexpectedly.",
        "causes": [
            "Corrupted system files",
            "Recent driver update conflict",
            "Malware interference with a system process",
            "Failing RAM",
        ],
    },
    "IRQL_NOT_LESS_OR_EQUAL": {
        "code_type": "bsod_stop_code",
        "description": "A driver attempted to access memory at an invalid interrupt request level.",
        "causes": ["Faulty or outdated driver (often network or graphics)", "Failing RAM", "Incompatible hardware"],
    },
    "PAGE_FAULT_IN_NONPAGED_AREA": {
        "code_type": "bsod_stop_code",
        "description": "Requested data was not found in memory, usually pointing to hardware or driver issues.",
        "causes": ["Failing RAM", "Corrupted system files", "Faulty driver", "Disk errors"],
    },
    "DPC_WATCHDOG_VIOLATION": {
        "code_type": "bsod_stop_code",
        "description": "A routine took too long to complete a system task.",
        "causes": ["Outdated storage/chipset driver", "SSD firmware issue", "Faulty SATA cable"],
    },
    "UNMOUNTABLE_BOOT_VOLUME": {
        "code_type": "bsod_stop_code",
        "description": "Windows cannot access the boot volume.",
        "causes": ["Disk corruption", "Failing hard drive/SSD", "Corrupted boot configuration"],
    },

    # ---- Windows hex error codes ----
    "0X80070005": {
        "code_type": "windows_hex",
        "description": "Access denied — insufficient permissions for the requested operation.",
        "causes": ["User account lacks admin rights", "File/folder permission misconfiguration", "Antivirus blocking access"],
    },
    "0X8007000D": {
        "code_type": "windows_hex",
        "description": "The data is invalid — often seen during Windows Update.",
        "causes": ["Corrupted Windows Update cache", "Corrupted system files"],
    },
    "0X80070422": {
        "code_type": "windows_hex",
        "description": "A required service is disabled.",
        "causes": ["Windows Update service disabled", "Background Intelligent Transfer Service (BITS) disabled"],
    },
    "0X000000EF": {
        "code_type": "windows_hex",
        "description": "Critical system process failed to start (bug check 0xEF).",
        "causes": ["Corrupted system files", "Failed Windows update", "Driver conflict"],
    },

    # ---- VPN error codes ----
    "ERROR 809": {
        "code_type": "vpn_error",
        "description": "The network connection between your computer and the VPN server could not be established (commonly a blocked port).",
        "causes": ["Firewall/router blocking UDP ports 500/4500", "ISP blocking VPN passthrough", "Public Wi-Fi restricting VPN protocols"],
    },
    "ERROR 691": {
        "code_type": "vpn_error",
        "description": "Authentication failed — the username or password was rejected by the remote server.",
        "causes": ["Incorrect credentials", "Expired password", "Account locked out"],
    },
    "ERROR 800": {
        "code_type": "vpn_error",
        "description": "Unable to establish the VPN connection.",
        "causes": ["Incorrect VPN server address", "Server unreachable", "Network connectivity issue"],
    },

    # ---- Printer error codes ----
    "ERROR 0X00000709": {
        "code_type": "printer_error",
        "description": "Windows could not set the default printer / printer connection issue.",
        "causes": ["Print spooler service stopped", "Corrupted printer driver", "Network printer unreachable"],
    },
}


def lookup_error_code(code: str) -> dict | None:
    """Case-insensitive lookup, normalizing whitespace/formatting differences from OCR."""
    normalized = code.strip().upper().replace("  ", " ")
    return KNOWN_ERROR_CODES.get(normalized)
