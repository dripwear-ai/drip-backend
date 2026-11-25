import assert from 'node:assert/strict';
import { readFileSync, statSync } from 'node:fs';
import { URL } from 'node:url';
import test from 'node:test';

// Run after a successful web production build. Checks actual SSR output, not a mock.
const sources = ['portal-shell.tsx', 'product-form.tsx', 'profile-form.tsx'].map(name =>
  new URL('../../apps/web/src/components/' + name, import.meta.url));
for (const route of ['admin/catalog/new', 'seller/submissions/new', 'seller/profile']) {
  test(route + ' cannot submit local draft fields before hydration', () => {
    const output = new URL('../../apps/web/.next/server/app/' + route + '.html', import.meta.url);
    for (const source of sources) {
      assert.ok(statSync(output).mtimeMs >= statSync(source).mtimeMs, 'Build is stale; rebuild before running this check');
    }
    const html = readFileSync(output, 'utf8');
    const forms = [...html.matchAll(/<form\b[^>]*>([\s\S]*?)<\/form>/g)];
    assert.equal(forms.length, 1, 'Expected the draft form');
    const buttons = [...forms[0][1].matchAll(/<button\b[^>]*>/g)].map(match => match[0]);
    const submitters = buttons.filter(button => !/\btype="(?:button|reset)"/.test(button));
    assert.equal(submitters.length, 1);
    assert.ok(submitters.every(button => /\sdisabled(?:=|\s|>)/.test(button)));
    assert.doesNotMatch(forms[0][1], /<input\b[^>]*\btype="(?:submit|image)"/);
    assert.match(forms[0][1], /<noscript>JavaScript is required/);
  });
}
