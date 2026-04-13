# mastostats

Weekly automated Mastodon post for `norden.social`, ported from an Apple Shortcut.

## What the script does

1. Calls `GET /api/v1/instance/activity`
2. Picks the last completed week (`activity[1]`, with fallback to `activity[0]`)
3. Reads `logins` and `registrations`
4. Calls `GET /api/v1/custom_emojis`
5. Picks one random emoji and uses its `shortcode`
6. Calls `POST /api/v1/statuses` with form field `status`

Post format:

`Letzte Woche waren wir X aktive Accounts und Y haben sich neu registriert.`

`Unser Emoji der Woche ist "shortcode": :shortcode:`

## Schedule behavior

The GitHub Action is scheduled for Monday at `12:00` in `Europe/Berlin` using GitHub Actions timezone support.
The script itself still checks that local time in `Europe/Berlin` is Monday 12:00,
so it works across DST changes.

## Setup

1. Push this repository to GitHub.
2. Go to `Settings > Secrets and variables > Actions`.
3. Add secret:
   - `MASTODON_ACCESS_TOKEN` = your Mastodon access token
4. Workflow file:
   - `.github/workflows/weekly-mastodon-post.yml`

## Manual run

Use `Actions > Weekly Mastodon Stats Post > Run workflow`:

- `force_post=true` to bypass the time guard
- `dry_run=true` to generate output without posting
