#!/usr/bin/env node
// Cookidoo HAR capture for M1 endpoint discovery.
//
// Two-phase:
//   phase=login   open headed persistent-profile browser at cookidoo.international,
//                 wait for Thomas to confirm logged-in state, dump storage to
//                 ../captures/cookidoo-storage.json
//   phase=record  fresh context loaded from cookidoo-storage.json, with HAR
//                 recording enabled, runs the scripted walk and writes
//                 ../captures/cookidoo-<date>.har

const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const readline = require('readline');

const phase = process.argv[2];
if (!['login', 'record', 'check'].includes(phase)) {
  console.error('usage: capture_har.js login|check|record');
  process.exit(1);
}

const root = path.resolve(__dirname, '..');
const capturesDir = path.join(root, 'captures');
const storagePath = path.join(capturesDir, 'cookidoo-storage.json');
const today = new Date().toISOString().slice(0, 10);
const harPath = path.join(capturesDir, `cookidoo-${today}.har`);
const profileDir = path.join(process.env.HOME, '.cache/pw-browse-profile');

fs.mkdirSync(capturesDir, { recursive: true });

const sleep = (ms) => new Promise(r => setTimeout(r, ms));

async function waitForEnter(prompt) {
  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
  return new Promise(resolve => rl.question(prompt, () => { rl.close(); resolve(); }));
}

async function isLoggedIn(page) {
  // Cookidoo redirects unauthenticated users to login.vorwerk.com / similar.
  // Authenticated users get a profile menu, my-week link, etc.
  try {
    const url = page.url();
    if (/login|signin|vorwerk-digital\.com\/auth/i.test(url)) return false;
    // Quick check: presence of an auth cookie via document.cookie won't catch
    // httpOnly cookies. Look for a UI marker instead.
    const hasMyWeek = await page.locator('a[href*="my-week" i], [data-testid*="my-week" i]').count();
    return hasMyWeek > 0;
  } catch { return false; }
}

(async () => {
  if (phase === 'login' || phase === 'check') {
    const ctx = await chromium.launchPersistentContext(profileDir, {
      headless: false,
      viewport: { width: 1440, height: 900 },
      locale: 'en-US',
      timezoneId: 'Europe/Oslo',
      args: ['--disable-blink-features=AutomationControlled'],
    });
    const page = ctx.pages()[0] || await ctx.newPage();

    console.log('Navigating to cookidoo.international ...');
    await page.goto('https://cookidoo.international/', { waitUntil: 'domcontentloaded', timeout: 45000 });
    await sleep(3000);

    let loggedIn = await isLoggedIn(page);
    console.log(`Initial logged-in check: ${loggedIn}`);

    if (phase === 'check') {
      console.log(`URL: ${page.url()}`);
      await ctx.close();
      process.exit(loggedIn ? 0 : 1);
    }

    if (!loggedIn) {
      console.log('\n>>> Please log in manually in the browser window.');
      console.log('>>> Once you see the My Week / home dashboard, return here and press Enter.');
      await waitForEnter('Press Enter when logged in... ');
      loggedIn = await isLoggedIn(page);
      if (!loggedIn) {
        console.error('Still not detected as logged in. Aborting.');
        await ctx.close();
        process.exit(2);
      }
    }

    console.log('Dumping storage state ...');
    await ctx.storageState({ path: storagePath });
    // Also dump localStorage explicitly (storageState handles it but be sure).
    const ls = await page.evaluate(() => {
      const out = {};
      for (let i = 0; i < localStorage.length; i++) {
        const k = localStorage.key(i);
        out[k] = localStorage.getItem(k);
      }
      return out;
    });
    fs.writeFileSync(storagePath + '.localstorage.json', JSON.stringify(ls, null, 2));
    console.log(`Storage written to ${storagePath}`);
    console.log(`LocalStorage dump: ${storagePath}.localstorage.json (${Object.keys(ls).length} keys)`);

    await ctx.close();
    return;
  }

  // phase === 'record'
  if (!fs.existsSync(storagePath)) {
    console.error(`Missing ${storagePath}. Run phase=login first.`);
    process.exit(1);
  }
  const localStorageDump = JSON.parse(fs.readFileSync(storagePath + '.localstorage.json', 'utf8'));

  const browser = await chromium.launch({
    headless: false,
    args: ['--disable-blink-features=AutomationControlled'],
  });
  const ctx = await browser.newContext({
    storageState: storagePath,
    viewport: { width: 1440, height: 900 },
    locale: 'en-US',
    timezoneId: 'Europe/Oslo',
    recordHar: { path: harPath, content: 'embed', mode: 'full' },
  });

  // Seed localStorage on cookidoo.international before the first navigation.
  await ctx.addInitScript((entries) => {
    try {
      for (const [k, v] of Object.entries(entries)) {
        localStorage.setItem(k, v);
      }
    } catch {}
  }, localStorageDump);

  const page = await ctx.newPage();

  const step = async (label, fn) => {
    console.log(`\n--- ${label}`);
    try {
      await fn();
    } catch (e) {
      console.error(`  step failed: ${e.message}`);
    }
    await sleep(2500);
  };

  await step('home', async () => {
    await page.goto('https://cookidoo.international/', { waitUntil: 'domcontentloaded', timeout: 45000 });
    await sleep(4000);
    console.log(`  url: ${page.url()}`);
  });

  await step('my-week (current)', async () => {
    // Try the conventional path. If routing differs, fall back to clicking the link.
    await page.goto('https://cookidoo.international/my-week', { waitUntil: 'domcontentloaded', timeout: 45000 });
    await sleep(4000);
    console.log(`  url: ${page.url()}`);
  });

  await step('my-week (next week)', async () => {
    const nextBtn = page.locator('button[aria-label*="next" i], [data-testid*="next" i]').first();
    if (await nextBtn.count()) {
      await nextBtn.click({ timeout: 5000 }).catch(() => {});
      await sleep(3000);
    } else {
      console.log('  no next button found - skipping');
    }
  });

  await step('custom recipe halloumi pita', async () => {
    await page.goto('https://cookidoo.international/recipes/recipe/en/01KS7SC3BNGA3FTF0ZNDZNZQR9', { waitUntil: 'domcontentloaded', timeout: 45000 });
    await sleep(4000);
    console.log(`  url: ${page.url()}`);
  });

  await step('shopping list', async () => {
    await page.goto('https://cookidoo.international/shopping/list', { waitUntil: 'domcontentloaded', timeout: 45000 });
    await sleep(4000);
    console.log(`  url: ${page.url()}`);
  });

  await step('edit custom recipe (back to halloumi, click edit)', async () => {
    await page.goto('https://cookidoo.international/recipes/recipe/en/01KS7SC3BNGA3FTF0ZNDZNZQR9', { waitUntil: 'domcontentloaded', timeout: 45000 });
    await sleep(3000);
    const editBtn = page.locator('a[href*="edit" i], button:has-text("Edit"), [data-testid*="edit" i]').first();
    if (await editBtn.count()) {
      await editBtn.click({ timeout: 5000 }).catch(() => {});
      await sleep(4000);
    } else {
      console.log('  no edit button found - skipping');
    }
  });

  // Stock recipe — try a known popular stock ID via search, else skip. Better:
  // attempt to surface one by visiting the search/discover page.
  await step('discover/search page', async () => {
    await page.goto('https://cookidoo.international/search/en?q=pasta', { waitUntil: 'domcontentloaded', timeout: 45000 });
    await sleep(4000);
    console.log(`  url: ${page.url()}`);
  });

  await step('click first search result', async () => {
    const firstResult = page.locator('a[href*="/recipes/recipe/"]').first();
    if (await firstResult.count()) {
      await firstResult.click({ timeout: 5000 }).catch(() => {});
      await sleep(5000);
      console.log(`  url: ${page.url()}`);
    } else {
      console.log('  no result link found');
    }
  });

  console.log('\nClosing context (flushing HAR)...');
  await ctx.close();
  await browser.close();
  console.log(`HAR written: ${harPath}`);
  console.log(`Size: ${(fs.statSync(harPath).size / 1024 / 1024).toFixed(2)} MB`);
})();
