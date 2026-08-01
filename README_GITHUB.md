# FII/DII Daily Scraper - GitHub Actions (Cloud) Setup

This runs **entirely on GitHub's servers** - your PC can be off, and the
data still updates every day at the time you choose.

## What you're getting
- `fii_dii_scraper.py` - the scraper (same logic as before)
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

## Step 5 - Set your preferred run time
Open `.github/workflows/fii_dii_scrape.yml` in the repo (click it -> pencil/edit icon)
and find this line:

    - cron: "30 13 * * 1-5"

This means **13:30 UTC = 7:00 PM IST**, Monday-Friday.
To change the time, edit the first two numbers (`minute hour`), in **UTC**.

Quick IST -> UTC reference (subtract 5 hours 30 minutes from IST):
| You want (IST) | Use (UTC) | Cron line                |
|-----------------|-----------|---------------------------|
| 6:00 PM         | 12:30     | `- cron: "30 12 * * 1-5"` |
| 7:00 PM         | 13:30     | `- cron: "30 13 * * 1-5"` |
| 8:00 PM         | 14:30     | `- cron: "30 14 * * 1-5"` |
| 9:00 PM         | 15:30     | `- cron: "30 15 * * 1-5"` |

Note: GitHub Actions schedules can run a few minutes late during busy
periods - this is normal and not something you can control.

After editing, click **"Commit changes"** to save.

## Step 6 - Test it right now (don't wait for the schedule)
1. Go to the **Actions** tab in your repo
2. Click **"FII DII Daily Scrape"** on the left
3. Click **"Run workflow"** (dropdown on the right) -> **"Run workflow"**
4. Wait ~30-60 seconds, refresh - you'll see a green checkmark if it worked
5. Click into the run to see the logs (same info as `scraper.log`)
6. Go back to the repo's main **Code** tab - you should now see
   `fii_dii_cash_history.csv` with data in it

## Step 7 - Viewing / using your data going forward
- **In GitHub**: click `fii_dii_cash_history.csv` in the repo to view it,
  or the "Raw" button to see plain CSV text
- **In Excel/Google Sheets**: download the CSV from GitHub, or in Google
  Sheets use:
  `=IMPORTDATA("https://raw.githubusercontent.com/<your-username>/<repo-name>/main/fii_dii_cash_history.csv")`
  to auto-pull the latest data live into a sheet
- The file keeps growing - one new row per business day, automatically,
  with duplicates never added even if a run happens twice

---

## Troubleshooting
- **Workflow didn't run on schedule**: GitHub only starts checking
  schedules once the workflow file has been committed at least once,
  and very new/idle repos can occasionally have schedules delayed by
  GitHub - use the manual "Run workflow" button to double check the
  scraper itself still works.
- **"Zero rows parsed" in the logs**: 5paisa changed their page layout -
  send me the updated table HTML and I'll patch `fii_dii_scraper.py`.
- **Permission denied when pushing**: revisit Step 4 - "Read and write
  permissions" must be enabled.
