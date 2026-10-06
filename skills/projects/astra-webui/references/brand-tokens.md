# Astra brand tokens (enforced by harness check 23)

Source of truth: portfolio style doc + `astra.css` custom properties. Harness scans every `astra-*/dashboard/dist/*.{js,css}` (vendor/ excluded); any hex not in this palette or any font-family outside this set fails the build.

## Palette
| Token | Hex | Use |
|---|---|---|
| void | `#0A0A0F` | page background (also badge ink) |
| midnight | `#12121A` | raised surfaces |
| depth | `#0D0D12` | wells, inputs |
| text | `#F8FAFC` | primary text |
| muted | `#9CA3AF` | secondary text |
| accent-emerald | `#34D399` | primary accent / ok / status dots-green |
| accent-cyan | `#22D3EE` | secondary accent |
| fuchsia | `#E879F9` | tertiary accent |
| violet | `#A78BFA` | tertiary accent |
| danger | `#F87171` | destructive / status dots-red |
| warn | `#FBBF24` | caution / status dots-yellow |

## Fonts
- `--astra-font`: "DM Sans", sans-serif (UI)
- `--astra-display`: "Playfair Display", serif (display)
- `--astra-mono`: "JetBrains Mono", monospace (code/mono)
- Generic fallbacks allowed: inherit, monospace, sans-serif, serif, system-ui, and the `var(--astra-*)` forms.
- Stock vars like `--theme-font-mono` are violations — map them to `var(--astra-mono)`.

## Known off-brand patterns to reject on sight
- macOS traffic-light dot colors (#FF5F56/#FFBD2E/#27C93F) → use danger/warn/accent-emerald.
- One-off ink hexes on badges/chips (e.g. #061828) → use void.
- Gradients of any kind (owner direction: flat, gradientless).

## Enforcement
`check_brand_compliance()` in `~/Work/astra/scratch/eval_astra.py` (check 23). When adding a brand color that genuinely must join the palette, add it to the token table here AND the harness set in the same change — never by bypassing the check.
