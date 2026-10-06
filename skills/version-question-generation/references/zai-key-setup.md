Z.ai API key setup for GLM 5.3 coding endpoint

Location: ~/.config/neutrinos-mcp/zai_key

Contents: Raw API token string (never commit to repo)

How to obtain:
1. Subscribe at https://www.z.ai (80-dollar coding pro tier)
2. Generate token from dashboard
3. Store at ~/.config/neutrinos-mcp/zai_key — read-only by gen_scripts

Verification:
```bash
cat ~/.config/neutrinos-mcp/zai_key | head -c 20
# Then test:
curl -s https://api.z.ai/api/coding/paas/v4/chat/completions -H "Authorization: Bearer $(cat ~/.config/neutrinos-mcp/zai_key)" ...
```