# PKI Hybrid Mode (Demo + Real Stub)

This project now supports a hybrid domain adapter path to demonstrate PKI-compliance automation patterns without requiring full CA infrastructure on day one.

## Why hybrid mode

- **Demo mode** proves architecture quickly in interviews/demos.
- **Real PKI stub mode** provides a clear path to integrate CA APIs (for example step-ca or enterprise CA services).
- Same governance and agentic gates apply in both modes.

## Endpoints

- `GET /pki/discover?mode=demo&target=the-internet.herokuapp.com`
- `GET /pki/discover?mode=real_pki&target=<domain>`
- `POST /pki/validate-profile`

## Policy-as-code profile validation

`POST /pki/validate-profile` validates profile attributes against:

- `app/src/governance/policies/pki_policy.json`

Current checks include:

- validity days range
- minimum RSA key size
- production SAN requirements
- production hostname restrictions

## Example request

```json
{
  "commonName": "api.example.com",
  "sanDns": ["api.example.com", "www.example.com"],
  "validityDays": 90,
  "keyAlgorithm": "RSA",
  "keySize": 2048,
  "environment": "prod"
}
```

## Production extension path

1. Replace `SmallstepPKIAdapter` stub logic with real CA API/CLI integration.
2. Map `pki_policy.json` rules to CP/CPS + CA/B + RFC controls.
3. Add certificate lifecycle jobs (issue/renew/revoke) and CT monitoring hooks.
