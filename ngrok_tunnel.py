from pyngrok import ngrok
import time

# Start ngrok
http_tunnel = ngrok.connect(5000, "http")
public_url = http_tunnel.public_url

print("\n=== Ngrok Tunnel gestartet ===")
print(f"\nÖffentliche URL: {public_url}")
print("\nVerwenden Sie diese URLs in den Facebook App-Einstellungen:")
print(f"Datenschutzerklärung URL: {public_url}/privacy-policy")
print(f"Nutzungsbedingungen URL: {public_url}/terms")
print("\nDrücken Sie Ctrl+C zum Beenden")

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\nBeende ngrok...")
    ngrok.kill()
