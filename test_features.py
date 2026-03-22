"""Test all Clarity features."""

import httpx
import json
import sys

base_url = 'http://localhost:8000'

print('='*70)
print('  CLARITY FEATURE TEST')
print('='*70)

results = []

# Test 1: Health check
print('\n✅ TEST 1: Health Endpoint')
try:
    r = httpx.get(f'{base_url}/api/v1/health', timeout=5)
    print(f'   Status: {r.status_code}')
    print(f'   Response: {r.json()}')
    results.append(('Health', r.status_code == 200))
except Exception as e:
    print(f'   ❌ FAILED: {e}')
    results.append(('Health', False))

# Test 2: Dashboard loads
print('\n✅ TEST 2: Dashboard')
try:
    r = httpx.get(f'{base_url}/', timeout=5)
    print(f'   Status: {r.status_code}')
    print(f'   Size: {len(r.content)} bytes')
    if 'html' in r.text.lower() or r.status_code == 200:
        print('   ✅ Dashboard loads')
        results.append(('Dashboard', True))
    else:
        print('   ❌ Dashboard response unclear')
        results.append(('Dashboard', False))
except Exception as e:
    print(f'   ❌ FAILED: {e}')
    results.append(('Dashboard', False))

# Test 3: List reports
print('\n✅ TEST 3: List Reports')
try:
    r = httpx.get(f'{base_url}/api/v1/reports', timeout=5)
    print(f'   Status: {r.status_code}')
    data = r.json()
    count = data.get('count', 0)
    print(f'   Reports count: {count}')
    results.append(('List Reports', r.status_code == 200))
except Exception as e:
    print(f'   ⚠️  {e}')
    results.append(('List Reports', False))

# Test 4: Verify endpoint (test)
print('\n✅ TEST 4: Verify Endpoint')
test_payload = {
    'messages': [{'role': 'user', 'content': 'Say hello'}],
    'system': 'You are helpful',
    'model': 'claude-sonnet-4-20250514',
    'temperature': 0.7,
}
try:
    r = httpx.post(f'{base_url}/api/v1/verify', json=test_payload, timeout=30)
    print(f'   Status: {r.status_code}')
    if r.status_code == 200:
        data = r.json()
        print(f'   ✅ Verification worked')
        if 'trust_report' in data:
            report = data['trust_report']
            score = report.get('overall_score', 'N/A')
            risk = report.get('overall_risk', 'N/A')
            print(f'   Overall score: {score}/100')
            print(f'   Risk level: {risk}')
        results.append(('Verify', True))
    else:
        print(f'   Error: {r.text[:200]}')
        results.append(('Verify', False))
except httpx.ReadTimeout:
    print(f'   ⏱️  Request timeout (might be processing)')
    results.append(('Verify', None))
except Exception as e:
    error_msg = str(e)[:100]
    print(f'   ⚠️  {error_msg}')
    results.append(('Verify', False))

# Summary
print('\n' + '='*70)
print('  TEST SUMMARY')
print('='*70)
for test_name, passed in results:
    status = '✅ PASS' if passed else ('⏱️ TIMEOUT' if passed is None else '❌ FAIL')
    print(f'  {test_name:.<30} {status}')

total_pass = sum(1 for _, p in results if p is True)
print(f'\n  Overall: {total_pass}/{len(results)} tests passed')
print('='*70)
