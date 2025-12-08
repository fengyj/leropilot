# Tailwind CSS v4 Reference Guide

> **Source**: [Official Tailwind CSS v4 Upgrade Guide](https://tailwindcss.com/docs/upgrade-guide)
>
> This document summarizes the key changes and best practices for using Tailwind CSS v4 in this project.

## Table of Contents

- [Installation & Setup](#installation--setup)
- [Key Changes from v3](#key-changes-from-v3)
- [CSS Configuration](#css-configuration)
- [Theme Customization](#theme-customization)
- [Best Practices](#best-practices)

---

## Installation & Setup

### Using Vite (Recommended for this project)

Tailwind v4 provides a dedicated Vite plugin for improved performance:

```javascript
// vite.config.ts
import { defineConfig } from "vite";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [tailwindcss()],
});
```

### Using PostCSS (Alternative)

If using PostCSS directly:

1. Install the dedicated PostCSS plugin:

   ```bash
   npm install @tailwindcss/postcss
   ```

2. Configure PostCSS:
   ```javascript
   // postcss.config.js
   export default {
     plugins: {
       "@tailwindcss/postcss": {},
     },
   };
   ```

**Note**: In v4, imports and vendor prefixing are handled automatically. You can remove `postcss-import` and `autoprefixer`.

---

## Key Changes from v3

### 1. Import Syntax

**v3:**

```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```

**v4:**

```css
@import "tailwindcss";
```

### 2. Browser Requirements

Tailwind v4 targets modern browsers:

- Safari 16.4+
- Chrome 111+
- Firefox 128+

It depends on modern CSS features like `@property` and `color-mix()`.

### 3. Removed Deprecated Utilities

| v3 (Deprecated)     | v4 (Modern Alternative) |
| ------------------- | ----------------------- |
| `bg-opacity-*`      | `bg-black/50`           |
| `text-opacity-*`    | `text-black/50`         |
| `border-opacity-*`  | `border-black/50`       |
| `flex-shrink-*`     | `shrink-*`              |
| `flex-grow-*`       | `grow-*`                |
| `overflow-ellipsis` | `text-ellipsis`         |

### 4. Configuration Files

- **JavaScript config files** are still supported but no longer auto-detected
- To use a JS config, explicitly load it with `@config` directive:
  ```css
  @config "../../tailwind.config.js";
  ```
- **CSS-based configuration is now preferred** (see Theme Customization below)

---

## CSS Configuration

### Basic Setup

Your main CSS file should start with:

```css
@import "tailwindcss";
```

That's it! No need for separate `@tailwind` directives.

### Theme Customization

Use the `@theme` directive to customize your design system:

```css
@import "tailwindcss";

@theme {
  /* Colors */
  --color-primary: #3b82f6;
  --color-secondary: #8b5cf6;

  /* Spacing */
  --spacing-xs: 0.5rem;
  --spacing-sm: 1rem;

  /* Breakpoints */
  --breakpoint-tablet: 768px;
  --breakpoint-desktop: 1024px;

  /* Shadows */
  --shadow-card: 0 4px 6px -1px rgb(0 0 0 / 0.1);
}
```

### Using Theme Values

**Recommended (CSS Variables):**

```css
.my-class {
  background-color: var(--color-primary);
  padding: var(--spacing-sm);
}
```

**Legacy (theme() function):**

```css
/* Only use in contexts where CSS variables don't work, like media queries */
@media (width >= theme(--breakpoint-desktop)) {
  /* ... */
}
```

---

## Theme Customization

### Color System

Define colors using CSS custom properties:

```css
@theme {
  --color-slate-950: #020617;
  --color-slate-900: #0f172a;
  --color-slate-800: #1e293b;
  /* ... */

  --color-blue-600: #2563eb;
  --color-blue-500: #3b82f6;
  /* ... */
}
```

Use in templates with standard Tailwind utilities:

```html
<div class="bg-slate-950 text-blue-500">
  <!-- Content -->
</div>
```

### Accessing Theme Values in JavaScript

**Recommended approach** (using CSS variables directly):

```javascript
// In React/Motion animations
<motion.div
  animate={{
    backgroundColor: "var(--color-blue-500)",
  }}
/>
```

**Reading computed values:**

```javascript
const styles = getComputedStyle(document.documentElement);
const shadowValue = styles.getPropertyValue("--shadow-xl");
```

**Note**: The `resolveConfig` function from v3 has been removed. Use CSS variables instead for better performance and smaller bundle sizes.

---

## Best Practices

### 1. Use CSS Variables for Theme Values

✅ **Do:**

```css
.custom-component {
  background-color: var(--color-primary);
  box-shadow: var(--shadow-card);
}
```

❌ **Don't:**

```css
.custom-component {
  background-color: theme(colors.primary);
}
```

### 2. Leverage Modern CSS Features

Tailwind v4 is built for modern browsers, so you can use:

- CSS Grid and Flexbox freely
- Modern color functions
- CSS custom properties
- Container queries

### 3. Keep Configuration in CSS

Prefer `@theme` in CSS over JavaScript config files for:

- Better performance
- Simpler setup
- Type safety with CSS
- Easier debugging

### 4. Use Standard Tailwind Utilities

Avoid custom CSS when Tailwind utilities exist:

✅ **Do:**

```html
<div class="flex h-screen w-screen overflow-hidden bg-slate-950">
  <!-- Content -->
</div>
```

❌ **Don't:**

```html
<div style="display: flex; height: 100vh; width: 100vw; overflow: hidden;">
  <!-- Content -->
</div>
```

### 5. Responsive Design

Use Tailwind's responsive prefixes:

```html
<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
  <!-- Responsive grid -->
</div>
```

---

## Common Patterns for This Project

### Full-Screen Layout

```tsx
// Root layout component
<div className="flex h-screen w-screen overflow-hidden bg-slate-950 text-slate-100">
  <Sidebar />
  <main className="flex-1 overflow-y-auto">{children}</main>
</div>
```

### Sidebar Component

```tsx
<div className="flex w-64 flex-col border-r border-slate-800 bg-slate-950">
  {/* Sidebar content */}
</div>
```

### Responsive Grid

```tsx
<div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
  {items.map((item) => (
    <Card key={item.id} />
  ))}
</div>
```

---

## Troubleshooting

### Styles Not Applying

1. **Check import**: Ensure your CSS file has `@import "tailwindcss";`
2. **Verify plugin**: Confirm Vite config includes `@tailwindcss/vite`
3. **Clear cache**: Try `rm -rf node_modules/.vite` and restart dev server

### Custom Theme Not Working

1. **Syntax**: Ensure `@theme` block uses correct CSS custom property syntax
2. **Placement**: Put `@theme` after `@import "tailwindcss";`
3. **Naming**: Follow the `--color-name-shade` pattern for colors

### Build Errors

1. **Node version**: Ensure Node.js 20+ is installed
2. **Dependencies**: Run `npm install` to ensure all packages are up to date
3. **Config conflicts**: Remove old `tailwind.config.js` if not needed

---

## Migration Checklist

When working with this project:

- [x] Use `@import "tailwindcss";` instead of `@tailwind` directives
- [x] Configure theme with `@theme` directive in CSS
- [x] Use modern utility classes (e.g., `bg-black/50` instead of `bg-opacity-50`)
- [x] Access theme values via CSS variables in JavaScript
- [x] Use Vite plugin (`@tailwindcss/vite`) for optimal performance
- [ ] Remove any legacy PostCSS plugins (`autoprefixer`, `postcss-import`)
- [ ] Test in modern browsers (Safari 16.4+, Chrome 111+, Firefox 128+)

---

## Additional Resources

- [Official Tailwind v4 Documentation](https://tailwindcss.com/docs)
- [Upgrade Guide](https://tailwindcss.com/docs/upgrade-guide)
- [GitHub Discussions](https://github.com/tailwindlabs/tailwindcss/discussions)
