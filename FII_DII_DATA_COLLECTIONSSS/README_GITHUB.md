# FII/DII Daily Scraper - GitHub Actions (Cloud) Setup

This runs **entirely on GitHub's servers** - your PC can be off, and the
data still updates every day at the time you choose.

## What you're getting
- `fii_dii_scraper.py` - the scraper (adds new days, corrects changed days, validates rows)
- `check_missing.py` - alarm that fails the run if a trading day has no data
- `nse_holidays.txt` - market holidays, so the alarm doesn't fire on them
- `requirements.txt` - tells GitHub what to install
- `.github/workflows/fii_dii_scrape.yml` - the automation "robot" that
  runs the script on a schedule and saves the results back into the repo
- `fii_dii_cash_history.csv` - will be created automatically inside the
  repo after the first run, and grows by one row per business day

---

## Step 1 - Create a GitHub account (skip if you have one)
Go to https://github.com/signup and create a free account.

## Step 2 - Create a new repository
1. Click the **+** icon (top right) -> **New repository**
2. Name it something like `fii-dii-tracker`
3. Choose **Private** (recommended) or Public - both are free
4. Click **Create repository**

## Step 3 - Upload the files
On the new repo's page:
1. Click **"Add file" -> "Upload files"**
2. Drag in `fii_dii_scraper.py` and `requirements.txt`
3. For the workflow file, you must **keep its folder path**
   (`.github/workflows/fii_dii_scrape.yml`). The easiest way:
   drag the whole `.github` folder (with `workflows` inside it) into
   the upload box - GitHub preserves the folder structure automatically.
4. Scroll down, click **"Commit changes"**

(If you're comfortable with git instead, this is just:
`git add . && git commit -m "initial" && git push` after cloning the empty repo.)

## Step 4 - Give the workflow permission to save data
By default GitHub Actions can't write back to your repo - you need to allow it once:
1. Go to your repo -> **Settings** tab -> **Actions** -> **General**
   (left sidebar)
2. Scroll to **"Workflow permissions"**
3. Select **"Read and write permissions"**
4. Click **Save**

## Step 5 - Schedule (already set up)
The workflow runs Mon-Fri **three times a day** (cron is UTC; IST = UTC + 5:30):

| Run | IST     | Cron                |
|-----|---------|---------------------|
| 1   | 6:30 PM | `0 13 * * 1-5`      |
| 2   | 8:00 PM | `30 14 * * 1-5`     |
| 3   | 9:30 PM | `0 16 * * 1-5` (also runs the missing-day check) |

Extra runs are harmless - dates already saved are skipped (or corrected if the
site changed them). They matter because **the source page only shows the
current month**: a day missed across a month-end cannot be recovered later.
If you change the third cron line, change the matching `github.event.schedule`
condition in the "Missing-day check" step too.

## Step 6 - Test it
Actions tab -> **FII DII Daily Scrape** -> **Run workflow**. Green tick = OK.

## Step 7 - Keeping the holiday list current
`nse_holidays.txt` lists weekday market holidays. Add each new NSE holiday
(one `YYYY-MM-DD` per line). If the 9:30 PM run fails with
"MISSING trading-day data", either the site had no data (try Run workflow
manually) or it was a holiday missing from this file.

## Notes
- `2026-11-08` (Sunday) is the Diwali Muhurat session: a real row with tiny values.
- `scraper.log` is no longer committed; on failure it is attached to the run
  as the `scraper-log` artifact. If `scraper.log` is still in your repo,
  delete it once (it is now in `.gitignore`).
- Rows failing sanity checks (net != purchase - sales) are skipped and the run
  fails, so a layout change is noticed immediately.

## Troubleshooting
- **Permission denied when pushing**: Settings -> Actions -> General ->
  Workflow permissions -> Read and write.
- **"Zero rows parsed" at the start of a month**: normal for 1-2 days.
- **"REJECTED" rows in the log**: 5paisa changed the layout - send me the table HTML.
