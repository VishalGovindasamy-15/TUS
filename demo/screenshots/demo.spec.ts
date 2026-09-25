/**
 * TrustUs UI walkthrough: visits every page, clicks the key buttons,
 * saves a screenshot per page to ../shots/, fails on console/page errors.
 *
 * Prerequisites (local machine):
 *   1. docker compose up --build -d   (from repo root; api :8000, web :3000)
 *      - or run API + `npm run dev` in web/ (port 5173)
 *   2. Seed demo data: docker compose exec api python -m app.seed
 *   3. cd demo/screenshots && npm i -D @playwright/test && npx playwright install chromium
 *   4. npx playwright test   (set WEB_URL=http://localhost:3000 for compose web)
 *
 * NOTE: login relies on debug_otp (dummy SMS, non-prod only).
 */
import { expect, Page, request, test } from '@playwright/test';

const WEB_URL = process.env.WEB_URL ?? 'http://localhost:5173';
const API = process.env.API_URL ?? 'http://localhost:8000/api/v1';
const SHOTS = '../shots';

const MFG = '+10000000002';
const ADMIN = '+10000000001';

const pageErrors: string[] = [];

async function apiLogin(phone: string) {
  const ctx = await request.newContext();
  const otpRes = await ctx.post(`${API}/auth/otp/request`, { data: { phone } });
  expect(otpRes.ok()).toBeTruthy();
  const { debug_otp } = await otpRes.json();
  const v = await ctx.post(`${API}/auth/otp/verify`, { data: { phone, otp: debug_otp } });
  expect(v.ok()).toBeTruthy();
  const body = await v.json();
  await ctx.dispose();
  return body.access_token as string;
}

async function uiLogin(page: Page, phone: string) {
  await page.goto(`${WEB_URL}/login`);
  await page.getByPlaceholder('+91…').fill(phone);
  const [resp] = await Promise.all([
    page.waitForResponse((r) => r.url().includes('/auth/otp/request')),
    page.getByRole('button', { name: 'Send OTP' }).click(),
  ]);
  const { debug_otp } = await resp.json();
  await page.getByPlaceholder('6-digit OTP').fill(debug_otp);
  await page.getByRole('button', { name: 'Verify & sign in' }).click();
  await page.waitForURL(/\/(dashboard|admin|onboarding)/, { timeout: 15000 });
}

test.beforeEach(async ({ page }) => {
  page.on('pageerror', (e) => pageErrors.push(`pageerror: ${e.message}`));
  page.on('console', (m) => {
    if (m.type() === 'error') pageErrors.push(`console: ${m.text().slice(0, 200)}`);
  });
});

test.afterAll(async () => {
  const real = pageErrors.filter(
    (e) => !e.includes('favicon') && !e.includes('net::ERR') && !e.includes('404'),
  );
  expect(real).toEqual([]);
});

test('01 login + manufacturer dashboard', async ({ page }) => {
  await page.goto(`${WEB_URL}/login`);
  await page.screenshot({ path: `${SHOTS}/01-login.png` });
  await uiLogin(page, MFG);
  // lands on role default (batches for manufacturer)
  await expect(page).toHaveURL(/\/dashboard\/batches/);
  await page.screenshot({ path: `${SHOTS}/02-batches.png` });

  // New batch via modal (unique number per run)
  const batchNo = `UITEST-${Date.now()}`;
  await page.getByRole('button', { name: 'New Batch' }).first().click();
  await page.screenshot({ path: `${SHOTS}/03-new-batch-modal.png` });
  const codeInput = page.getByLabel('Product code');
  if (await codeInput.isVisible()) {
    await codeInput.fill(`UIPROD-${Date.now()}`);
    await page.getByLabel('Product name').fill('UI Test Product');
  }
  await page.getByLabel('Batch number').fill(batchNo);
  await page.getByRole('button', { name: 'Create batch' }).click();
  await expect(page.getByText(batchNo)).toBeVisible({ timeout: 10000 });

  // Generate units -> per-row spinner, list appears
  await page.getByRole('button', { name: 'Generate Units' }).click();
  await expect(page.getByText(/Units \(/)).toBeVisible({ timeout: 20000 });
  await page.screenshot({ path: `${SHOTS}/04-batch-detail-units.png` });

  // Export CSV download
  const [download] = await Promise.all([
    page.waitForEvent('download'),
    page.getByRole('button', { name: 'Export Labels' }).click(),
  ]);
  expect(download.suggestedFilename()).toContain('.csv');
});

test('02 unit detail timeline', async ({ page }) => {
  await uiLogin(page, MFG);
  const token = await apiLogin(MFG);
  const ctx = await request.newContext({
    extraHTTPHeaders: { Authorization: `Bearer ${token}` },
  });
  const products = await (await ctx.get(`${API}/products`)).json();
  const batch = await (
    await ctx.post(`${API}/batches`, {
      data: { product_id: products[0].id, batch_number: `UITL-${Date.now()}`, quantity: 1 },
    })
  ).json();
  const gen = await (await ctx.post(`${API}/batches/${batch.id}/units`, { data: { count: 1 } })).json();
  const unitId: string = gen.unit_ids[0];
  const cid = () => `ui-${Date.now()}-${Math.floor(Math.random() * 1e6)}`;
  await ctx.post(`${API}/events`, {
    data: { client_event_id: cid(), target_type: 'unit', target_id: unitId, event_type: 'DISPATCH', gps_lat: 13.08, gps_lng: 80.27 },
  });
  await ctx.dispose();

  await page.goto(`${WEB_URL}/dashboard/units/${unitId}`);
  await expect(page.getByText('Event history')).toBeVisible();
  await expect(page.getByText('DISPATCH')).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/05-unit-detail.png` });
});

test('03 network invites + tree', async ({ page }) => {
  await uiLogin(page, MFG);
  await page.goto(`${WEB_URL}/dashboard/network`);
  await expect(page.getByRole('heading', { name: 'Network' })).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/06-network.png` });
  await page.getByRole('button', { name: 'Invite Partner' }).click();
  await page.getByRole('button', { name: 'Generate invite' }).click();
  await expect(page.getByText('TU-')).toBeVisible({ timeout: 10000 });
  await page.screenshot({ path: `${SHOTS}/07-invite-code.png` });
});

test('04 alerts, map, events log', async ({ page }) => {
  await uiLogin(page, MFG);
  await page.goto(`${WEB_URL}/dashboard/alerts`);
  await page.waitForTimeout(1500);
  await page.screenshot({ path: `${SHOTS}/08-alerts.png` });
  await page.goto(`${WEB_URL}/dashboard/map`);
  await page.waitForTimeout(2500);
  await page.screenshot({ path: `${SHOTS}/09-live-map.png` });
  await page.goto(`${WEB_URL}/dashboard/events`);
  await page.waitForTimeout(1500);
  await page.screenshot({ path: `${SHOTS}/10-events-log.png` });
});

test('05 team, settings, kyc, profile', async ({ page }) => {
  await uiLogin(page, MFG);
  await page.goto(`${WEB_URL}/dashboard/users`);
  await page.waitForTimeout(1500);
  await page.screenshot({ path: `${SHOTS}/11-team.png` });

  await page.goto(`${WEB_URL}/dashboard/settings`);
  await page.getByRole('button', { name: 'Save' }).click();
  await page.waitForTimeout(800);
  await page.screenshot({ path: `${SHOTS}/12-settings.png` });

  await page.goto(`${WEB_URL}/dashboard/kyc`);
  await page.waitForTimeout(1200);
  await page.setInputFiles('input[type="file"]', {
    name: 'gst.pdf',
    mimeType: 'application/pdf',
    buffer: Buffer.from('%PDF-ui-test-bytes'),
  });
  await page.getByRole('button', { name: 'Upload' }).click();
  await expect(page.getByText('gst certificate', { exact: false })).toBeVisible({ timeout: 10000 });
  await page.screenshot({ path: `${SHOTS}/13-kyc.png` });

  await page.goto(`${WEB_URL}/dashboard/profile`);
  await page.waitForTimeout(1200);
  await page.screenshot({ path: `${SHOTS}/14-profile.png` });
});

test('06 social listings + containers', async ({ page }) => {
  await uiLogin(page, '+10000000006'); // social_seller
  await expect(page).toHaveURL(/social-listings/);
  await page.screenshot({ path: `${SHOTS}/15-social-listings.png` });

  await uiLogin(page, MFG);
  await page.goto(`${WEB_URL}/dashboard/containers`);
  await page.getByRole('button', { name: 'Pack Container' }).first().click();
  await page.getByRole('button', { name: 'Create container' }).click();
  await page.waitForTimeout(1500);
  await page.screenshot({ path: `${SHOTS}/16-containers.png` });
});

test('07 admin pages', async ({ page }) => {
  await uiLogin(page, ADMIN);
  await expect(page).toHaveURL(/\/admin/);
  await page.goto(`${WEB_URL}/admin/orgs`);
  await page.waitForTimeout(1500);
  await page.screenshot({ path: `${SHOTS}/17-admin-orgs.png` });
  await page.goto(`${WEB_URL}/admin/alerts`);
  await page.waitForTimeout(1500);
  await page.screenshot({ path: `${SHOTS}/18-admin-alerts.png` });
  await page.goto(`${WEB_URL}/admin/fraud`);
  await page.waitForTimeout(1500);
  await page.screenshot({ path: `${SHOTS}/19-admin-fraud.png` });
  await page.goto(`${WEB_URL}/admin/regulator`);
  await page.waitForTimeout(1200);
  await page.screenshot({ path: `${SHOTS}/20-admin-regulator.png` });
});

test('08 public verify all four states', async ({ page }) => {
  const mfg = await apiLogin(MFG);
  const admin = await apiLogin(ADMIN);
  const ctx = await request.newContext();
  const auth = (t: string) => ({ Authorization: `Bearer ${t}` });
  const products = await (await ctx.get(`${API}/products`, { headers: auth(mfg) })).json();
  const mkBatch = async (n: string, qty: number) => {
    const b = await (
      await ctx.post(`${API}/batches`, {
        headers: auth(mfg),
        data: { product_id: products[0].id, batch_number: `${n}-${Date.now()}`, quantity: qty },
      })
    ).json();
    const g = await (
      await ctx.post(`${API}/batches/${b.id}/units`, { headers: auth(mfg), data: { count: qty } })
    ).json();
    return { batch: b, units: g.unit_ids as string[] };
  };
  const cid = () => `uiv-${Date.now()}-${Math.floor(Math.random() * 1e6)}`;

  const fresh = await mkBatch('UIVF', 1);
  const genuine = await mkBatch('UIVG', 1);
  await ctx.post(`${API}/events`, {
    headers: auth(mfg),
    data: { client_event_id: cid(), target_type: 'unit', target_id: genuine.units[0], event_type: 'DISPATCH' },
  });
  const flagged = await mkBatch('UIVFL', 1);
  await ctx.post(`${API}/events`, {
    headers: auth(admin),
    data: { client_event_id: cid(), target_type: 'unit', target_id: flagged.units[0], event_type: 'FLAG' },
  });
  const recalled = await mkBatch('UIVR', 1);
  await ctx.post(`${API}/batches/${recalled.batch.id}/recall`, {
    headers: auth(mfg),
    data: { reason: 'ui demo' },
  });
  await ctx.dispose();

  for (const [unitId, shot, label] of [
    [genuine.units[0], '21-verify-genuine', 'Genuine product'],
    [fresh.units[0], '22-verify-not-yet', 'Not yet in circulation'],
    [flagged.units[0], '23-verify-flagged', 'Flagged'],
    [recalled.units[0], '24-verify-recalled', 'Recalled'],
  ] as const) {
    await page.goto(`${WEB_URL}/v/${unitId}`);
    await expect(page.getByText(label, { exact: false })).toBeVisible({ timeout: 10000 });
    await page.screenshot({ path: `${SHOTS}/${shot}.png` });
  }
});
