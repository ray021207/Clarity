"""Test verify endpoint with agents."""

import httpx
import time

print('Testing verify endpoint with agents...')
base_url = 'http://localhost:8000'
test_payload = {
    'messages': [{'role': 'user', 'content': 'What is 2+2?'}],
    'system': 'You are helpful',
    'model': 'claude-sonnet-4-20250514',
    'temperature': 0.7,
}

try:
    print('Sending request...')
    r = httpx.post(f'{base_url}/api/v1/verify', json=test_payload, timeout=120)
    print(f'Status: {r.status_code}')
    
    if r.status_code == 200:
        data = r.json()
        if 'trust_report' in data:
            report = data['trust_report']
            print(f'\n✅ VERIFICATION SUCCESSFUL\n')
            print(f'Overall score: {report.get("overall_score")}/100')
            print(f'Risk level: {report.get("overall_risk")}')
            print(f'Warnings: {report.get("warnings")}')
            print(f'\nAgent Scores:')
            print(f'  • Hallucination: {report.get("hallucination", {}).get("score")}/100')
            print(f'  • Reasoning: {report.get("reasoning", {}).get("score")}/100')
            print(f'  • Confidence: {report.get("confidence", {}).get("score")}/100')
            print(f'  • Context: {report.get("context_quality", {}).get("score")}/100')
        else:
            print('Response has no trust_report')
            print(data.keys())
    else:
        print(f'Error: {r.text[:500]}')
        
except httpx.ReadTimeout:
    print('Request timeout (took longer than 120s)...')
except Exception as e:
    print(f'Error: {e}')
