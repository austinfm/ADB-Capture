import sys


def prompt_device_selection(
    devices: list[dict], label: str = "Select device"
) -> dict | None:
    """Displays a numbered device menu and returns the user's selection."""
    print(f"\n[{label}] Multiple devices available:")
    for i, d in enumerate(devices, 1):
        entry = f"  {i}. {d['ip']}"
        if d.get("model"):
            entry += f"  ({d['model']})"
        print(entry)
    print()
    try:
        raw = input(f"Enter number (1-{len(devices)}): ").strip()
        idx = int(raw) - 1
        if 0 <= idx < len(devices):
            return devices[idx]
    except (ValueError, KeyboardInterrupt):
        pass
    return None


def show_onboarding_guide():
    """Displays step-by-step instructions to set up USB debugging and pairing."""
    print("\n" + "=" * 55)
    print("  WIRELESS SETUP - USB DISCOVERY")
    print("=" * 55 + "\n")
    print("We'll pair your phone over WiFi using ADB.")
    print("This takes about 30 seconds on the first run.\n")

    print("--- STEP 1: Enable Developer Options (skip if done) ---")
    print("  1. Open Settings on your phone")
    print("  2. Go to 'About Phone'")
    print("  3. Tap 'Build Number' 7 times rapidly")
    print("     You'll see: 'You are now a developer!'\n")
    print("(If you already have Developer Options, press Enter to continue to Step 2.)")
    try:
        input("Press Enter to continue...")
    except KeyboardInterrupt:
        print("\nExiting.")
        sys.exit(0)

    print("\n--- STEP 2: Enable USB Debugging ---")
    print("  1. Go to Settings > Developer Options")
    print("  2. Toggle 'USB Debugging' to ON\n")
    try:
        input("Press Enter to continue...")
    except KeyboardInterrupt:
        print("\nExiting.")
        sys.exit(0)

    print("\n--- STEP 3: Connect via USB ---")
    print("  1. Plug your phone into this computer with a USB cable")
    print("     (use a data cable, not a charge-only cable)")
    print("  2. On the phone, tap ALLOW when asked about USB Debugging")
    print("     Tip: check 'Always allow from this computer' to skip this next time\n")
    try:
        input("Press Enter once you see 'Allow USB Debugging' on your phone...")
    except KeyboardInterrupt:
        print("\nExiting.")
        sys.exit(0)
    print()
