import requests

r = requests.post(
    'https://loca-quiety-raccoon.loca.lt/api/v1/billing/paddle/webhook',
    data=b'{"test": true}',
    headers={'Content-Type': 'application/json', 'Paddle-Signature': 'ts=12345;h1=fake'},
    timeout=15
)
print('Webhook test:', r.status_code, r.text[:200])
