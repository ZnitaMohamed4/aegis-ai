#!/bin/bash
# ============================================================
# Aegis Instance Recreation Script
# ============================================================
# Cleanly deletes the old Baileys session and creates a fresh
# instance, fixing the "device_removed" session corruption.
# ============================================================

API_URL="http://localhost:5002"
API_KEY="df68549f73b6ab16c4275a5cd83d3251afd192466b97e8e2e982fbe6d96a7b74"
INSTANCE_NAME="aegis_parent_0e0d4828"

echo "════════════════════════════════════════════════════════════"
echo "  🔄 AEGIS Instance Recreation"
echo "════════════════════════════════════════════════════════════"

# Step 1: Log out cleanly (tells WhatsApp to deregister the device)
echo ""
echo "📱 Step 1/4: Logging out instance..."
LOGOUT=$(curl -s -X DELETE "$API_URL/instance/logout/$INSTANCE_NAME" \
  -H "apikey: $API_KEY")
echo "   Result: $LOGOUT"
sleep 2

# Step 2: Delete the instance (clears all local session data, keys, etc.)
echo ""
echo "🗑️  Step 2/4: Deleting instance..."
DELETE=$(curl -s -X DELETE "$API_URL/instance/delete/$INSTANCE_NAME" \
  -H "apikey: $API_KEY")
echo "   Result: $DELETE"
sleep 3

# Step 3: Create fresh instance
echo ""
echo "🆕 Step 3/5: Creating fresh instance..."
CREATE=$(curl -s -X POST "$API_URL/instance/create" \
  -H "apikey: $API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"instanceName\": \"$INSTANCE_NAME\",
    \"integration\": \"WHATSAPP-BAILEYS\",
    \"qrcode\": true
  }")
echo "   Result: $CREATE"
sleep 2

# Step 4: Set Webhook (Evolution v2 requires setting webhooks via a separate endpoint)
echo ""
echo "🔗 Step 4/5: Setting Webhook..."
WEBHOOK=$(curl -s -X POST "$API_URL/webhook/set/$INSTANCE_NAME" \
  -H "apikey: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "webhook": {
      "enabled": true,
      "url": "http://localhost:8000/api/v1/webhook/messages/",
      "events": ["MESSAGES_UPSERT"]
    }
  }')
echo "   Result: $WEBHOOK"
sleep 1

# Step 5: Get QR code for scanning
echo ""
echo "📸 Step 5/5: Fetching QR code..."
QR=$(curl -s "$API_URL/instance/connect/$INSTANCE_NAME" \
  -H "apikey: $API_KEY")

# Check if the response has a QR code base64 string
QR_BASE64=$(echo "$QR" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('base64',''))" 2>/dev/null)

if [ -n "$QR_BASE64" ] && [ "$QR_BASE64" != "" ]; then
    HTML_PATH="/home/muhammed/Desktop/aegis-ai/qr.html"
    echo "<html><body style='text-align:center; font-family:sans-serif; background:#f0f0f0; padding-top:50px;'><h2>AEGIS WhatsApp Authentication</h2><p>Scan this QR code with your phone (Linked Devices):</p><img src=\"$QR_BASE64\" style='border: 1px solid #ccc; border-radius: 10px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); padding: 20px; background: white;' /></body></html>" > "$HTML_PATH"
    
    echo ""
    echo "════════════════════════════════════════════════════════════"
    echo "  ✅ QR CODE READY — SCAN THIS WITH WHATSAPP"
    echo "════════════════════════════════════════════════════════════"
    echo ""
    echo "  We saved the QR code to an HTML file for easy viewing!"
    echo "  👉 Double-click or open this file in your browser:"
    echo "     $HTML_PATH"
    echo ""
    echo "════════════════════════════════════════════════════════════"
else
    echo "  ⚠️  Could not extract QR base64. Ensure the instance was created properly."
    echo "  Response was: $QR"
fi

echo ""
echo "⏳ After scanning, wait 30 seconds for the sync to complete."
echo "   Then check connection state:"
echo "   curl -s $API_URL/instance/connectionState/$INSTANCE_NAME -H 'apikey: $API_KEY'"
echo ""
echo "   Then test archive with a threat message!"
echo ""
