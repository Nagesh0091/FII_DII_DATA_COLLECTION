# FII/DII Data Collection, Dashboard \& Data Science Applications

## Project Overview

The FII/DII Data Collection project automatically collects Foreign Institutional Investors (FII) and Domestic Institutional Investors (DII) activity data, maintains historical records, and provides interactive applications for data visualization and analysis.

The project consists of three major components:

1. Automated FII/DII Daily Data Scraper
2. FII/DII Interactive Dashboard
3. FII/DII Data Science Application

The scraping and data collection process runs on GitHub Actions cloud infrastructure. A personal computer does not need to remain switched on for scheduled data collection.

\---

## 1\. Deployed Streamlit Applications

Both applications are developed and deployed using Streamlit Community Cloud.

### Application 1: FII/DII Dashboard

**Live Application:**  
https://fii-dii.streamlit.app/

The dashboard provides an interactive interface to explore FII/DII market activity and historical data.

Key functionalities:

* Interactive FII/DII data visualization.
* Historical market activity analysis.
* Daily data monitoring.
* Graphical representation of institutional buying and selling trends.
* Easy access to collected market information.

### Application 2: FII/DII Data Science Application

**Live Application:**  
https://fii-dii-ds.streamlit.app/

This application provides additional data science and analytical functionality based on FII/DII market data.

It is deployed separately from the main dashboard to keep the data science functionality independent.

\---

## 2\. Automated FII/DII Daily Scraper

The scraper automatically collects FII/DII cash market data and maintains a historical CSV dataset.

**Automation Platform:** GitHub Actions

The scraping process runs on GitHub's cloud servers without requiring a local computer.

### Main Functionalities

* Automatically collects new trading-day records.
* Adds newly available market data to historical records.
* Corrects previously collected records if the source data changes.
* Validates collected data before saving.
* Checks for missing trading-day records.
* Avoids duplicate entries.
* Maintains historical data in CSV format.

### Files Used in the Project

|File|Purpose|
|-|-|
|`fii\_dii\_scraper.py`|Collects and processes FII/DII market data.|
|`check\_missing.py`|Checks whether any trading-day records are missing.|
|`nse\_holidays.txt`|Contains NSE market holidays to avoid false missing-data alerts.|
|`requirements.txt`|Contains the Python dependencies required for execution.|
|`fii\_dii\_cash\_history.csv`|Stores the historical FII/DII cash market data.|
|`.github/workflows/fii\_dii\_scrape.yml`|Automates the daily scraping process through GitHub Actions.|
|`.gitignore`|Excludes unnecessary files from version control.|

### Historical CSV Dataset

The scraper automatically creates and maintains:

`fii\_dii\_cash\_history.csv`

The CSV file stores historical FII/DII data and is updated whenever new market data becomes available.

The scraper checks existing records and corrects them if the source data changes.

The dataset is intended to serve as the data source for the dashboard and data science applications, subject to how each application is configured to access it.

\---

## 3\. Automated Scraping Schedule

The GitHub Actions workflow is configured to execute three times a day, Monday through Friday.

All times below are in Indian Standard Time (IST).

|Execution|Time (IST)|Purpose|
|-|-|-|
|Run 1|6:30 PM|Collect newly available market data.|
|Run 2|8:00 PM|Recheck and update historical records.|
|Run 3|9:30 PM|Final data collection and missing-day validation.|

**Note:** GitHub Actions uses UTC for scheduling. The workflow cron expressions are configured accordingly.

Multiple executions help capture newly published or corrected market records. Existing dates are not duplicated; previously collected records can be updated when necessary.

\---

## 4\. Application Keep-Alive Automation

Both Streamlit applications are hosted on Streamlit Community Cloud. Applications on the free hosting tier may go to sleep after periods of inactivity.

A separate scheduled GitHub Actions workflow can periodically send HTTP requests to both deployed application URLs.

Applications covered by this automation:

1. https://fii-dii.streamlit.app/
2. https://fii-dii-ds.streamlit.app/

The keep-alive workflow can:

* Send periodic requests to both application URLs.
* Check the HTTP response status.
* Log the availability of each application.
* Run independently of the daily scraping workflow.

This automation may reduce inactivity-related sleeping, but it does not guarantee uninterrupted availability or override Streamlit hosting limits and policies.

\---

## 5\. Data Validation and Monitoring

The project includes a separate missing-day validation script to help ensure data completeness.

The validation process checks:

* Whether expected trading-day records are available.
* Whether market holidays are correctly excluded.
* Whether FII/DII purchase and sales values are consistent.
* Whether the net investment value matches purchase minus sales.
* Whether any records have been rejected due to validation errors.

If unexpected missing records or invalid data are detected, the GitHub Actions execution can fail and provide logs for investigation.

\---

## 6\. Project Architecture

The overall project workflow is:

1. GitHub Actions triggers the automated scraper.
2. The scraper collects FII/DII market data.
3. The collected records are validated.
4. Historical CSV data is created or updated.
5. The updated dataset is made available to the deployed applications through their configured data-access method.
6. The FII/DII Dashboard displays market information.
7. The FII/DII Data Science Application provides additional analytical functionality.
8. A separate scheduled workflow periodically checks both Streamlit applications.

\---

## 7\. Important Notes

* Daily data collection runs on GitHub's cloud infrastructure.
* No local computer is required for scheduled scraping.
* Historical data is maintained in CSV format.
* NSE market holidays must be updated in `nse\_holidays.txt` when required.
* The two Streamlit applications are deployed independently.
* Application availability depends on Streamlit Community Cloud.
* Scraping failures and missing-day validation errors should be checked through GitHub Actions execution logs.
* The keep-alive workflow and daily scraping workflow operate independently.
* A keep-alive request does not guarantee that an application will remain awake continuously.

\---

## Project Links

**FII/DII Dashboard:**  
https://fii-dii.streamlit.app/

**FII/DII Data Science Application:**  
https://fii-dii-ds.streamlit.app/

**Data Collection:** Automated through GitHub Actions.

**Historical Dataset:** `fii\_dii\_cash\_history.csv`

**Deployment Platform:** Streamlit Community Cloud

**Automation Platform:** GitHub Actions

