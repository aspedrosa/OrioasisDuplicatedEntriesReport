# OriOasis Duplicate Entries Report

A script to generate a report of duplicate entries in an OriOasis event and send it to a specified email.
This script uses **[Mailgun](https://www.mailgun.com/)** to send the email reports.

## Usage

To use this script, follow these steps:

1. **Install Python Dependencies**:
   Install the required dependencies by running:
   ```bash
   pip install -r requirements.txt
   ```
   
2. **Setup a Mailgun Account**:
   Create a Mailgun account and get your domain and API key.

3. **Set Environment Variables**:
   You need to set the following environment variables for the script to work, especially for sending emails via Mailgun:

   - `MAILGUN_DOMAIN`: Your Mailgun domain.
   - `MAILGUN_API_KEY`: Your Mailgun API key.
   - `MAIL_TO`: The email address where the report should be sent.

   Example:
   ```bash
   export MAILGUN_DOMAIN="your-mailgun-domain"
   export MAILGUN_API_KEY="your-mailgun-api-key"
   export MAIL_TO="recipient@example.com"
   ```

4. **Run the Script**:
   Run the script using `python main.py` with the required arguments.

   ```bash
   python main.py --event EVENT_ID
   ```

   **Other available options:**
   - `--cache-page`: (Optional) Cache the entries page to avoid downloading it multiple times during development/testing.
   - `--skip-send-email`: (Optional) Print duplicates to console but do not send an email.
   - `--runner-names-to-ignore-duplicates "Name1,Name2"`: (Optional) Comma-separated list of runner names to ignore when checking for duplicates.

   **Example:**
   ```bash
   python main.py --event 1234 --skip-send-email
   ```
