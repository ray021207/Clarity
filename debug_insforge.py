"""Debug InsForge API endpoint structure."""

from clarity.config import settings
import httpx

print("=" * 70)
print("  Debugging InsForge Endpoints")
print("=" * 70)

base_url = settings.insforge_url
api_key = settings.insforge_api_key

print(f"\n📍 Base URL: {base_url}")
print(f"🔑 API Key: {api_key[:20]}...")

headers = {
    "apikey": api_key,
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json",
}

# Test different endpoint patterns
endpoints_to_try = [
    f"{base_url}/rest/v1/trust_reports",
    f"{base_url}/postgrest/v1/trust_reports", 
    f"{base_url}/api/rest/v1/trust_reports",
    f"{base_url}/public/rest/v1/trust_reports",
]

for endpoint in endpoints_to_try:
    try:
        print(f"\n🔌 Testing: {endpoint}")
        response = httpx.get(endpoint, headers=headers, timeout=5)
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            print(f"   ✅ SUCCESS! This endpoint works")
        else:
            print(f"   Response: {response.text[:100]}")
    except Exception as e:
        print(f"   ❌ Error: {str(e)[:80]}")

print("\n" + "=" * 70)
print("  Check your InsForge dashboard for the correct API endpoint URL")
print("=" * 70)
print("\nInsForge PostgREST URL is usually shown in:")
print("  - Dashboard → Settings → API")
print("  - Or: Dashboard → Databases → Connection String")
print("\nThe PostgREST URL typically looks like:")
print("  https://your-project.region.insforge.app/rest/v1")
