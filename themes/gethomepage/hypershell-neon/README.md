# Hypershell Neon for Homepage

A CSS-only dark neon-glass theme for [Homepage](https://gethomepage.dev/). It adds a pink, electric-blue and cyan visual system while keeping Homepage's YAML configuration and built-in interactions intact.

Tested with Homepage `v1.13.2`.

## Features

| Feature | What it changes |
|---|---|
| Shared design tokens | Central CSS variables control the neon palette, panel surfaces, text hierarchy, gradients and corner radius. |
| Neon-glass cards | Service and bookmark cards use a dark translucent surface, subtle border and external pink-to-cyan edge glow. |
| Interactive card states | Hover strengthens the gradient border and glow without tinting the panel interior. |
| Unified widget metrics | Service widget values are presented as one segmented row instead of separate tiles. |
| Glass tab bar | The tab bar uses a translucent blurred surface, while the active tab receives a pink-to-blue gradient and soft glow. |
| Responsive mobile tabs | Tabs remain on one line and become horizontally scrollable on smaller screens. |
| Animated collapsible sections | Service and bookmark groups reveal with a short top-down roll animation. Reduced-motion preferences are respected. |
| Improved layout spacing | Desktop section columns receive more breathing room, including support for headerless wrapper groups containing nested groups. |
| Clearer text hierarchy | Names, descriptions, headings, widget labels and secondary information use distinct contrast levels. |
| Gradient section icons | MDI service and bookmark group icons receive a neon gradient and restrained glow. |
| Keyboard focus | Interactive cards and tabs get an explicit electric-blue `:focus-visible` outline. |
| Interaction cues | Tabs, collapsible group headers and the refresh control use appropriate pointer and hover feedback. |
| Minimal scrollbar | Scroll containers use a thin neutral scrollbar that remains visible without drawing attention. |
| Floating refresh control | Homepage's refresh action is converted into a compact floating button instead of occupying a footer row. |
| Mobile Quick Launch alignment | On mobile, the refresh button sits immediately to the left of a bottom-right Quick Launch button. |
| CSS-only implementation | No `custom.js` is required, avoiding brittle DOM scripting. |

## Installation

1. Back up your existing `custom.css`.
2. Copy [`custom.css`](custom.css) into the Homepage configuration directory.
   - Inside the container, the target is normally `/app/config/custom.css`.
   - With a bind mount such as `/path/to/config:/app/config`, copy it to `/path/to/config/custom.css` on the host.
3. Merge the relevant values from [`settings.example.yaml`](settings.example.yaml) into your existing `settings.yaml`. Do not replace unrelated configuration.
4. Use Homepage's refresh control and reload the page. A hard refresh may be needed when browser caching preserves older CSS.

Homepage loads custom styling from `custom.css` in its configuration directory. No JavaScript file is needed for this theme.

## Recommended settings

The theme is designed and tested with:

```yaml
theme: dark
color: slate
headerStyle: clean
iconStyle: theme
hideVersion: true
statusStyle: basic
cardBlur: sm
```

For the intended mobile refresh-button placement, enable Quick Launch in the bottom-right corner:

```yaml
quicklaunch:
  mobileButtonPosition: bottom-right
```

Tabs are optional, but the active-tab styling only appears when the Homepage layout defines tabs.

## Compatibility

- Tested with Homepage `v1.13.2`.
- Uses modern CSS features including `:has()`, `:is()`, `backdrop-filter`, `clip-path`, `isolation` and `:focus-visible`.
- Selectors target Homepage's generated classes and Headless UI attributes. An upstream DOM or class change may require selector updates in a future Homepage release.
- The CSS is global and does not depend on specific service names, bookmark names, hostnames or URLs.
- A background image is optional and is not included.

## Customization

The main visual values are defined at the top of `custom.css`:

| Variable | Purpose |
|---|---|
| `--hs-neon-pink` | Primary pink accent and left card edge. |
| `--hs-neon-blue` | Active-tab gradient, separators and keyboard focus. |
| `--hs-neon-cyan` | Cyan card edge and gradient endpoint. |
| `--hs-panel-surface` | Base translucent card and tab-bar surface. |
| `--hs-panel-elevated` | Hovered card and widget-row surface. |
| `--hs-text-primary` | Service and bookmark names. |
| `--hs-text-heading` | Group headings and primary information widgets. |
| `--hs-text-secondary` | Descriptions and secondary information. |
| `--hs-text-muted` | Quiet labels and supporting text. |
| `--hs-panel-radius` | Card corner radius. |

The variables use space-separated RGB channels so opacity can be adjusted at each use site with modern `rgb(... / alpha)` syntax.

## Optional adjustments

### Mobile refresh without Quick Launch

The default mobile rule leaves space for a bottom-right Quick Launch button. Without that button, add this after the theme CSS:

```css
@media (max-width: 768px) {
  #footer {
    right: 1rem !important;
  }
}
```

### Disable collapsible-section animation

The theme already follows the user's reduced-motion preference. To disable the animation for everyone, add:

```css
:is(.services-group, .bookmark-group) [id^="headlessui-disclosure-panel-"] {
  transform: none !important;
  clip-path: none !important;
  transition: none !important;
}
```

## License

MIT. See the repository's [LICENSE](../../../LICENSE).
