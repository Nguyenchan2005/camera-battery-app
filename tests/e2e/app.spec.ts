import { expect, test } from "@playwright/test";

async function openApp(page: import("@playwright/test").Page) {
  await page.goto("/");
  await expect(page.getByTestId("app-ready")).toBeVisible();
}

async function fillSearch(page: import("@playwright/test").Page, query: string) {
  await page.getByTestId("search-input").fill(query);
}

async function submitSearch(page: import("@playwright/test").Page, query: string) {
  await fillSearch(page, query);
  await page.getByTestId("search-submit").click();
  await expect(page.getByTestId("result-panel")).toBeVisible();
}

test("app loads from static preview with database stats and network status", async ({ page }) => {
  await openApp(page);
  await expect(page.getByTestId("network-status")).toBeVisible();
  await expect(page.getByTestId("database-stats")).toContainText("Verified cameras");
  await expect(page.getByTestId("last-data-update")).toContainText(/Last data update: \d{4}-\d{2}-\d{2}|unknown/);
});

test("search NB-13L returns a battery result", async ({ page }) => {
  await openApp(page);
  await submitSearch(page, "NB-13L");
  await expect(page.getByTestId("result-battery")).toBeVisible();
  await expect(page.getByTestId("result-panel")).toContainText("NB-13L");
  await expect(page.getByTestId("battery-coverage-summary")).toContainText("may verified");
  await expect(page.getByTestId("battery-unresolved-note")).toContainText("camera da duoc xac minh pin");
});

test("search Canon G7X Mark III returns verified camera and NB-13L compatibility", async ({ page }) => {
  await openApp(page);
  await fillSearch(page, "Canon G7X Mark III");
  await page.getByTestId("search-result-camera-canon_powershot_g7_x_mark_iii").click();
  await expect(page.getByTestId("result-camera")).toBeVisible();
  await expect(page.getByTestId("result-panel")).toContainText("Canon PowerShot G7 X Mark III");
  await expect(page.getByTestId("compat-card-canon_nb_13l-fully_compatible")).toContainText("NB-13L");
  await page.getByTestId("source-toggle").first().click();
  await expect(page.getByTestId("source-row").first()).toBeVisible();
});

test("search Kodak EasyShare C1013 returns unresolved without battery compatibility", async ({ page }) => {
  await openApp(page);
  await fillSearch(page, "Kodak EasyShare C1013");
  await page.getByTestId("search-result-unresolved_candidate-kodak_easyshare_c1013").click();
  await expect(page.getByTestId("result-unresolved")).toBeVisible();
  await expect(page.getByTestId("result-panel")).toContainText("Kodak EasyShare C1013");
  await expect(page.getByTestId("result-panel")).toContainText("Da tim thay model nay trong catalog");
  await expect(page.getByTestId("result-panel")).toContainText("Khong nen mua pin");
  await expect(page.locator('[data-testid^="compat-card-"]')).toHaveCount(0);
  await page.getByTestId("add-unresolved-camera").click();
  await expect(page.getByTestId("inventory-camera-kodak_easyshare_c1013")).toContainText("can xac minh pin");
  await expect(page.getByTestId("inventory-unverified-count")).toContainText("1");
  await expect(page.getByTestId("inventory-unverified-summary")).toContainText("chua xac minh pin");
});

test("shows newly manual-verified Kodak C713 as compatible rather than suggested", async ({ page }) => {
  await openApp(page);
  await fillSearch(page, "Kodak EasyShare C713");
  await page.getByTestId("search-result-camera-kodak_easyshare_c713").click();
  await expect(page.getByTestId("result-camera")).toBeVisible();
  await expect(page.getByTestId("compat-card-generic_aa-uses_aa")).toContainText("AA");
  await expect(page.getByTestId("unresolved-suggestions")).toHaveCount(0);

  await submitSearch(page, "AA");
  await expect(page.getByTestId("battery-camera-kodak_easyshare_c713")).toContainText("Kodak EasyShare C713");
  await expect(page.getByTestId("battery-suggested-matches")).toHaveCount(0);
});

test("finds researched Samsung TL320 alias as verified WB1000 with SLB-11A", async ({ page }) => {
  await openApp(page);
  await fillSearch(page, "Samsung TL320");
  await page.getByTestId("search-result-camera-samsung_wb1000").click();
  await expect(page.getByTestId("result-camera")).toBeVisible();
  await expect(page.getByTestId("compat-card-samsung_slb_11a-fully_compatible")).toBeVisible();
  await expect(page.getByText("pin da xac minh")).toBeVisible();
});

test("search unknown model returns not found state", async ({ page }) => {
  await openApp(page);
  await submitSearch(page, "Definitely Not A Compact Camera 9999XYZ");
  await expect(page.getByTestId("result-unknown")).toBeVisible();
  await expect(page.getByTestId("result-panel")).toContainText("Chua co du lieu");
});

test("adds camera and battery to local inventory", async ({ page }) => {
  await openApp(page);
  await fillSearch(page, "Canon G7X Mark III");
  await page.getByTestId("search-result-camera-canon_powershot_g7_x_mark_iii").click();
  await page.getByTestId("add-result-camera").click();
  await expect(page.getByTestId("inventory-camera-canon_powershot_g7_x_mark_iii")).toBeVisible();

  await page.getByTestId("add-compat-battery-canon_nb_13l").click();
  await expect(page.getByTestId("inventory-battery-canon_nb_13l")).toBeVisible();

  const stored = await page.evaluate(() => ({
    cameras: JSON.parse(localStorage.getItem("compact-camera-db:my-camera-ids") ?? "[]"),
    batteries: JSON.parse(localStorage.getItem("compact-camera-db:my-battery-ids") ?? "[]"),
  }));
  expect(stored.cameras).toContain("canon_powershot_g7_x_mark_iii");
  expect(stored.batteries).toContain("canon_nb_13l");
});

test("exports and imports inventory JSON", async ({ page }, testInfo) => {
  await openApp(page);
  await fillSearch(page, "Canon G7X Mark III");
  await page.getByTestId("search-result-camera-canon_powershot_g7_x_mark_iii").click();
  await page.getByTestId("add-result-camera").click();
  await page.getByTestId("add-compat-battery-canon_nb_13l").click();

  const downloadPromise = page.waitForEvent("download");
  await page.getByTestId("inventory-export").click();
  const download = await downloadPromise;
  const exportPath = testInfo.outputPath("inventory-export.json");
  await download.saveAs(exportPath);

  await page.getByTestId("clear-cameras").click();
  await page.getByTestId("clear-batteries").click();
  await expect(page.getByTestId("inventory-camera-canon_powershot_g7_x_mark_iii")).toHaveCount(0);
  await expect(page.getByTestId("inventory-battery-canon_nb_13l")).toHaveCount(0);

  await page.getByTestId("inventory-import-input").setInputFiles(exportPath);
  await expect(page.getByTestId("inventory-camera-canon_powershot_g7_x_mark_iii")).toBeVisible();
  await expect(page.getByTestId("inventory-battery-canon_nb_13l")).toBeVisible();
});

test("bulk paste adds exact inventory matches and reports unknown lines", async ({ page }) => {
  await openApp(page);
  await page.getByTestId("inventory-bulk-input").fill("Canon G7X Mark III\nNB13L\nDefinitely Missing Camera 9999XYZ");
  await page.getByTestId("inventory-bulk-add").click();

  await expect(page.getByTestId("inventory-camera-canon_powershot_g7_x_mark_iii")).toBeVisible();
  await expect(page.getByTestId("inventory-battery-canon_nb_13l")).toBeVisible();
  await expect(page.getByTestId("inventory-bulk-summary")).toContainText("Tu them exact");
  await expect(page.getByTestId("inventory-bulk-not-found")).toContainText("Definitely Missing Camera 9999XYZ");
});

test("keyboard navigation can select a search result", async ({ page }) => {
  await openApp(page);
  await fillSearch(page, "NB13L");
  await expect(page.getByTestId("search-suggestions")).toBeVisible();
  await page.getByTestId("search-input").press("ArrowDown");
  await page.getByTestId("search-input").press("ArrowUp");
  await page.getByTestId("search-input").press("Enter");
  await expect(page.getByTestId("result-battery")).toBeVisible();
  await expect(page.getByTestId("result-panel")).toContainText("NB-13L");
});
