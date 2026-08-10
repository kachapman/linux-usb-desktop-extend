#!/bin/bash

# ============================================
# WAYLAND EXTENDED DISPLAY SETUP
# GNOME Desktop Sharing → Extend Mode
# Xiaomi Tablet via ADB Reverse Tunnel
# ============================================

RDP_PORT=3389
POLL_INTERVAL=2

echo "=========================================="
echo "WAYLAND EXTENDED DISPLAY SETUP"
echo "Extends existing GNOME session to tablet"
echo "=========================================="
echo ""

# Step 1: Wait for Tablet USB Connection
echo "[1/4] Waiting for tablet USB connection..."
while true; do
    TABLET_SERIAL=$(adb devices 2>/dev/null | grep -v "List of devices" \
                    | grep -v "^$" | grep -v "daemon" | awk '{print $1}' | head -1)
    
    if [ -n "$TABLET_SERIAL" ]; then
        echo "   ✓ Tablet detected: $TABLET_SERIAL"
        break
    fi
    sleep $POLL_INTERVAL
done

# Step 2: DISABLE Remote Login (system service) — it conflicts!
echo "[2/4] Disabling Remote Login (system-level)..."
sudo grdctl --system rdp disable 2>/dev/null || true
sudo systemctl stop gnome-remote-desktop.service 2>/dev/null || true
sudo systemctl disable gnome-remote-desktop.service 2>/dev/null || true

# Step 3: ENABLE Desktop Sharing (user-level) with EXTEND mode
echo "[3/4] Configuring Desktop Sharing in EXTEND mode..."

# Enable RDP at user level
grdctl rdp enable

# Disable view-only (allows control from tablet)
grdctl rdp disable-view-only

# THIS IS THE KEY SETTING — creates a virtual extended monitor
# in the existing Wayland session, NOT a new session
gsettings set org.gnome.desktop.remote-desktop.rdp screen-share-mode 'extend'

# Set credentials
grdctl rdp set-credentials "tablet" "UprightSubwayGogglesZucchiniAsparagus"

# Restart the user service to pick up changes
systemctl --user daemon-reload
systemctl --user restart gnome-remote-desktop

# Verify configuration
sleep 2
if grdctl status | grep -q "Status: enabled" && \
   grdctl status | grep -q "View-only: no"; then
    echo "   ✓ RDP enabled, view-only disabled"
else
    echo "   ✗ RDP configuration failed"
    grdctl status
    exit 1
fi

# Verify extend mode is set
EXTEND_MODE=$(gsettings get org.gnome.desktop.remote-desktop.rdp screen-share-mode)
echo "   ✓ Screen share mode: $EXTEND_MODE"

# Verify port is listening
if ss -tlnp | grep -q ":$RDP_PORT"; then
    echo "   ✓ Port $RDP_PORT is listening"
else
    echo "   ✗ Port $RDP_PORT is NOT listening"
    exit 1
fi

# Step 4: Set Up ADB Reverse Tunnel
echo "[4/4] Setting up ADB reverse tunnel..."
adb reverse tcp:$RDP_PORT tcp:$RDP_PORT

if ! adb reverse --list 2>/dev/null | grep -q "tcp:$RDP_PORT"; then
    echo "   ✗ Failed to establish tunnel"
    exit 1
fi

echo "   ✓ Tunnel established: tablet 127.0.0.1:$RDP_PORT → laptop :$RDP_PORT"

echo ""
echo "=========================================="
echo "✅ SETUP COMPLETE - EXTENDED DISPLAY READY"
echo "=========================================="
echo ""
echo "📱 On Your Xiaomi Tablet:"
echo "   PC Name:  127.0.0.1"
echo "   Port:     3389"
echo "   Username: tablet"
echo "   Password: UprightSubwayGogglesZucchiniAsparagus"
echo ""
echo "   Accept the certificate warning on first connect."
echo ""
echo "💡 The tablet will show an EXTENDED portion of"
echo "   your existing desktop. Drag windows between"
echo "   laptop screen and tablet freely."
echo ""
echo "⚠️  Keep this terminal open to maintain the tunnel."
echo "   Press Ctrl+C to disconnect."
echo "=========================================="
echo ""

# Keep tunnel alive
wait
