# Factory Console design system

## Design thesis

The factory dashboard is a quiet technical operations desk: dense enough to scan active work, calm enough to trust, and explicit about evidence, uncertainty, and blocked states.

## Reference and adaptation

The closest VoltAgent reference is Linear's dark product surface. This project adapts its charcoal surface ladder, hairline dividers, compact controls, system sans typography, and monospace identifiers. It does not use Linear branding or copy. The factory's own operational states use restrained mint, amber, red, and grey signals because state distinction is essential to this product.

## Tokens

| Role | Token | Dark | Light |
|---|---|---|---|
| Canvas | `--canvas` | `#111313` | `#f5f6f5` |
| Surface | `--surface` | `#171a19` | `#ffffff` |
| Raised | `--raised` | `#1d211f` | `#eef0ee` |
| Border | `--border` | `#2b302e` | `#dfe3df` |
| Text | `--text` | `#edf1ee` | `#202522` |
| Muted | `--muted` | `#a0aaa4` | `#5e6862` |
| Faint text | `--faint` | `#858f89` | `#68736c` |
| Accent | `--accent` | `#a5e3c2` | `#16784a` |
| Success | `--success` | `#76d6a4` | `#16784a` |
| Running | `--warning` | `#efbd72` | `#99600c` |
| Blocked, interrupted, failed, timed out | `--danger` | `#ff8585` | `#b53333` |

## Layout and type

- Use a 4px spacing base and 6–12px corner radii.
- The board is an eight-lane horizontal workspace. Keep lanes 280px wide at all viewport sizes and contain horizontal scrolling within the board region.
- Keep the header compact and sticky. Keep card content dense and informative; prefer labels and proof over decorative metrics.
- Use a system sans stack for interface text and a system monospace stack for run IDs, provider/model identifiers, and timestamps.
- Use tabular numerals for elapsed time and round counts.

## Components and interaction

- Cards use a flat surface and a hairline border, with a stronger focus ring. Do not use shadow-heavy elevation or gradients.
- Status always includes text. Color is supplemental: mint for verified delivery, amber for running, red for blocked, interrupted, failed, or timed out, and grey for queued or unknown. Interrupted runs appear in Blocked with an explicit Interrupted label.
- Use native buttons, inputs, selects, and `dialog` elements. Escape closes dialogs and focus returns to the invoking control.
- Loading uses reserved skeleton space; errors retain current data and provide a retry action.
- Respect reduced motion. Keep state-change transitions short and limited to opacity or transform.

## Responsive behavior and accessibility

- Keep the primary action and connection/mode state visible at 320px, 390px, tablet, and desktop widths.
- The board can scroll horizontally; the page itself must not overflow horizontally.
- Maintain visible keyboard focus, logical heading order, labeled form controls, 44px touch targets where practical, and 4.5:1 text contrast.
- Do not imply success from elapsed time, stream completion, or process exit alone. A Ready run needs the explicit verified delivery state.

## States to design

Loading, empty, API error with retry, reconnecting, demo/live/unavailable mode, queued, running, blocked, interrupted, unknown, unverified, verified delivery, long requirement text, keyboard navigation, narrow screens, and reduced motion.
