import test from 'node:test';
import assert from 'node:assert/strict';
import { contrastText, resolveAccentTokens } from '../src/theme-state.ts';

test('accent override derives missing hover, soft and selected colors with contrasting text', () => {
  const red = resolveAccentTokens({ primary: '#ff0000' }, 'dark');
  assert.equal(red['on-primary'], '#000000');
  assert.match(red['primary-hover'], /var\(--ra-primary\).*white/);
  assert.match(red['primary-soft'], /var\(--ra-primary\).*var\(--ra-surface\)/);
  assert.match(red['sidebar-active'], /var\(--ra-primary\).*var\(--ra-sidebar-bg\)/);
  const dark = resolveAccentTokens({ primary: '#112233' }, 'light');
  assert.equal(dark['on-primary'], '#ffffff');
  assert.match(dark['primary-hover'], /black/);
});

test('explicit global or resolved tokens win without mutation', () => {
  const explicit = { primary: '#ff2ca3', 'primary-hover': '#aa0055', 'primary-soft': '#ffeeff',
    'sidebar-active': '#ffeedd', 'on-primary': '#123456' };
  assert.deepEqual(resolveAccentTokens(explicit, 'light'), explicit);
  assert.deepEqual(resolveAccentTokens({ radius: '12px' }, 'light'), { radius: '12px' });
});

test('contrast uses linear luminance and normalized opaque colors', () => {
  assert.equal(contrastText('#fff'), '#000000');
  assert.equal(contrastText('#000'), '#ffffff');
  assert.equal(contrastText('#ff2ca3'), '#000000');
  assert.equal(contrastText('rgba(0,0,0,.5)'), undefined);
  assert.equal(resolveAccentTokens({ primary: 'red' }, 'dark', '#ff0000')['on-primary'], '#000000');
  assert.equal(resolveAccentTokens({ primary: 'var(--brand)' }, 'dark')['on-primary'], undefined);
});
