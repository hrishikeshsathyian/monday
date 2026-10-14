# Deployment

How Monday is deployed in production, why it is set up this way, and the commands
for day-to-day work.

## What runs where

Monday is made of three processes that run in different ways, so they are hosted
differently.

| Process | Command | How it runs | Where it runs |
|---|---|---|---|
| **Monday bot** | `python -m bot.main` | Long-running: polls Telegram for messages | AWS Lightsail, as a systemd service |
| **McQueen** | `python -m mcqueen.main --all` | Runs once and exits, every hour | GitHub Actions (`.github/workflows/scrape.yml`) |
| **Hermione** | `python -m hermione.main` | Runs once and exits | Not scheduled yet; run by hand when needed |

### Dev vs prod

There is one codebase and one Supabase database. What makes a run "dev" or "prod" is
the set of environment variables it starts with:

| | Dev (laptop) | Prod (Lightsail / GitHub Actions) |
|---|---|---|
| Env vars come from | `.env` in the repo (git-ignored) | `/etc/monday/prod.env` on the server; GitHub secrets for McQueen |
| `ENV` | `dev` | `prod` |
| Monday bot token | Dev bot | Prod bot |
| McQueen channel | Dev channel | Prod channels |
| Hermione recipients | Only `HERMIONE_DEV_CHAT_ID` | Every authenticated user |

Because dev and prod use different bot tokens, the dev bot on the laptop and the
prod bot on the server can run at the same time without conflicting (Telegram allows
only one process to poll a given token).

## How the server was set up

### 1. AWS account

- **Root user**: the email you signed up with. It can do everything, including
  billing and closing the account, and can't be restricted. It's used only for account
  tasks, with MFA turned on and a budget alert set.
- **IAM user**: a login created inside the account with limited permissions. It's used
  for day-to-day work such as managing the Lightsail instance.

### 2. Lightsail instance

Lightsail is AWS's simple virtual private server (VPS): a Linux machine that runs
all the time, billed at a flat monthly price.

- **Region:** Singapore (`ap-southeast-1`)
- **OS:** Ubuntu 24.04 LTS
- **Plan:** $5/month with a public IPv4 address. The cheaper IPv6-only plan can't
  reach github.com, which only supports IPv4.
- **Static IP:** attached so the address doesn't change on reboot.
- **Firewall:** only SSH (port 22) is open. Polling makes *outbound* requests to
  Telegram, so the bot needs no inbound ports.

You can connect through the browser terminal in the Lightsail console, which logs
in as the `ubuntu` Linux user.

### 3. Preparing the machine

```bash
sudo apt update && sudo apt upgrade -y
```
Refreshes the package list and installs OS security updates.

```bash
sudo fallocate -l 1G /swapfile && sudo chmod 600 /swapfile
sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```
Creates 1 GB of swap: disk space the OS can use as extra memory when the 512 MB of
RAM runs out, e.g. while installing dependencies. The last line keeps it after reboots.

```bash
sudo timedatectl set-timezone Asia/Singapore
```
Sets the server clock to Singapore time, so log timestamps read naturally.

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc
```
Installs `uv` into `~/.local/bin` and reloads the shell so the `uv` command is found.

### 4. Getting the code

```bash
git clone https://github.com/hrishikeshsathyian/monday.git ~/monday
cd ~/monday
uv sync --frozen --no-dev
```
- `git clone` copies the repo to `/home/ubuntu/monday`. The repo is public, so no
  SSH key is needed.
- `uv sync` creates `.venv/` and installs the dependencies into it. It also
  downloads Python 3.12 if needed (from `.python-version`).
  - `--frozen` installs exactly the versions in `uv.lock`, so the server matches
    what was tested.
  - `--no-dev` skips dev-only tools such as `black`.

### 5. Prod secrets

```bash
sudo mkdir -p /etc/monday
sudo nano /etc/monday/prod.env
sudo chown ubuntu:ubuntu /etc/monday/prod.env && sudo chmod 600 /etc/monday/prod.env
```

`/etc/monday/prod.env` holds the prod values as `KEY=value` lines: `ENV=prod`,
`MONDAY_BOT_TOKEN`, `TELEGRAM_BOT_TOKEN`, `SUPABASE_URL`, `SUPABASE_SECRET_KEY`,
`FERNET_KEY`, and the Cloudflare R2 settings `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`,
`R2_SECRET_ACCESS_KEY` and `R2_BUCKET`.

- **R2 is where Wall-E puts zips over 10 MB.** Uploads from Lightsail to Telegram run
  at about 300 KB/s, while uploads to R2 run at about 30 MB/s, so bigger zips go to R2
  and the user gets a 24-hour download link instead. The bucket needs a lifecycle rule
  that deletes objects after 1 day, and the API token only needs read/write on that
  bucket.

- **It lives outside the repo**, so a `git pull` can never overwrite it and it can't
  be committed by accident. `/etc` is where Linux keeps configuration.
- **`chown` / `chmod 600`** let only the `ubuntu` user read and write it.
- **`FERNET_KEY` must match the key that encrypted the credentials already in the
  database.** Otherwise Hermione can't decrypt anyone's Canvas key.
- **`TELEGRAM_BOT_TOKEN` is required** even for the bot, because `config/settings.py`
  reads it on import.

### 6. Running the bot as a systemd service

See [How a Linux service works](#how-a-linux-service-works) below for the background.

`/etc/systemd/system/monday-bot.service`:

```ini
[Unit]
Description=Monday Telegram bot (prod)
After=network-online.target
Wants=network-online.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/monday
EnvironmentFile=/etc/monday/prod.env
ExecStart=/home/ubuntu/monday/.venv/bin/python -m bot.main
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now monday-bot
sudo systemctl status monday-bot
```

## How a Linux service works

### systemd

**systemd** is the first program Linux starts when it boots. It starts, stops and
supervises every other long-running program, which are called **services** (or
daemons).

If you started the bot by typing `python -m bot.main` in a terminal, it would stop
when you closed the terminal, crashed, or the server rebooted. Running it as a
service hands it to systemd instead, which:

- starts it when the server boots,
- restarts it if it crashes,
- keeps it running with no terminal open,
- collects everything it logs.

### The unit file

You describe a service to systemd in a **unit file**, a text file in
`/etc/systemd/system/`. Its file name (`monday-bot.service`) is the name you use in
commands.

**`[Unit]`: what it is and when to start it**
- `Description`: the name shown by `systemctl status`.
- `After=network-online.target` / `Wants=network-online.target`: start only after
  the network is up, since the bot needs to reach Telegram.

**`[Service]`: how to run it**
- `User=ubuntu`: run as the normal `ubuntu` user, not as `root`, so a bug can't
  touch the rest of the system.
- `WorkingDirectory`: the directory the process starts in (the repo), so
  `-m bot.main` finds the `bot` package.
- `EnvironmentFile`: loads `/etc/monday/prod.env` into the process's environment
  variables. This is how the prod secrets reach `config/settings.py`.
- `ExecStart`: the command to run. It calls the virtualenv's Python directly, so
  uv isn't needed at runtime.
- `Restart=always` / `RestartSec=5`: if the process exits for any reason, start it
  again after 5 seconds.

**`[Install]`: what "enabled" means**
- `WantedBy=multi-user.target`: start it as part of normal boot.

### systemctl: controlling services

| Command | What it does |
|---|---|
| `sudo systemctl daemon-reload` | Re-reads unit files. Needed after creating or editing a `.service` file |
| `sudo systemctl start monday-bot` | Starts it now |
| `sudo systemctl stop monday-bot` | Stops it now. It starts again on the next boot if enabled |
| `sudo systemctl restart monday-bot` | Stops, then starts. This is how it picks up new code or env values |
| `sudo systemctl enable monday-bot` | Starts it on every boot. Doesn't start it now |
| `sudo systemctl enable --now monday-bot` | Enables it *and* starts it now |
| `sudo systemctl disable monday-bot` | Stops it from starting on boot |
| `systemctl status monday-bot` | Shows whether it's running, its process ID and the last few log lines (`q` to exit) |

### journald: logs

systemd captures everything a service writes to stdout and stderr and stores it in
the **journal**. Monday logs through Python's `logging` module, which writes to
stderr, so every log line ends up there. You read the journal with `journalctl`.

## Workflows

### Deploying a code change

The server only runs the code that's checked out in `~/monday`. Pushing to GitHub
doesn't change the server by itself, so after pushing to `main`:

```bash
cd ~/monday
git pull                      # fetch and apply the new commits
uv sync --frozen --no-dev     # install any new or changed dependencies
sudo systemctl restart monday-bot
```

- **Why restart:** Python loads the code into memory when the process starts. A
  running process keeps the old code until it restarts.
- **`uv sync`** is only strictly needed when `pyproject.toml` / `uv.lock` changed,
  but it's quick and harmless to always run.
- **No `daemon-reload`** is needed unless you changed the `.service` file itself.

Then check it came back up:

```bash
systemctl status monday-bot
```

### Changing a prod secret or setting

```bash
sudo nano /etc/monday/prod.env
sudo systemctl restart monday-bot
```

Environment variables are read once at startup (`config/settings.py` reads
`os.environ` on import), so a running process keeps the old values until it
restarts. systemd re-reads the `EnvironmentFile` on every start, so no
`daemon-reload` is needed.

Locally, restart the dev bot (`Ctrl+C`, then run it again) after editing `.env`.
One-off runs (`hermione.main`, `mcqueen.main`) read `.env` fresh every time.

### Viewing logs

```bash
journalctl -u monday-bot -f                      # follow live (Ctrl+C to stop)
journalctl -u monday-bot -n 100 --no-pager       # last 100 lines
journalctl -u monday-bot --since "1 hour ago"    # a time window
journalctl -u monday-bot -p err --since today    # errors only
journalctl -u monday-bot -b                      # since the last reboot
journalctl -u monday-bot --since today | grep <chat_id>   # one user
```

- `-u` picks the service ("unit").
- `-f` keeps printing new lines as they arrive.
- `-p err` shows only error-level lines and above.

Every line starts with `[PROD]` or `[DEV]` (from `config/logging.py`), so it's always
clear which environment a log came from.

### Running Hermione by hand on the server

```bash
cd ~/monday
uv run --no-dev --env-file /etc/monday/prod.env -m hermione.main
```

- **`--env-file`:** the server has no `.env` in the repo, so `load_dotenv()` finds
  nothing. This flag loads the prod variables for this one run.
- **`--no-dev`:** `uv run` syncs the environment before running, and without this
  it would install the dev tools on the server.

This doesn't conflict with the running bot. Telegram allows only one process to
*receive* updates for a token, but any number can *send* messages.

**Warning:** this is a prod run, so every authenticated Hermione user gets a real
digest. To test, run it locally with the dev `.env`, which sends only to
`HERMIONE_DEV_CHAT_ID`.

### McQueen (GitHub Actions)

McQueen doesn't run on the server.
- `.github/workflows/scrape.yml` runs it every hour on GitHub's machines, with the
  prod values stored as repository secrets.
- You can also start a run by hand from the repo's **Actions** tab
  (`workflow_dispatch`).
- Logs for each run are on that run's page in the Actions tab.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `bad unit file setting` / `Missing '='` | The `.service` file has stray text in it, e.g. from a bad paste | Check it with `cat`, rewrite it, run `daemon-reload` |
| `KeyError: 'SOME_VAR'` in the logs | That variable is missing from `prod.env` | Add it, then restart |
| `ValueError: ENV must be 'dev' or 'prod'` | Typo in the `ENV=` line | Fix it, then restart |
| `No such file or directory: .venv/bin/python` | `uv sync` wasn't run in `~/monday` | Run `uv sync --frozen --no-dev` |
| `409 Conflict: terminated by other getUpdates request` | Two processes are polling the same bot token | Make sure the laptop uses the dev token |
| Hermione: "could not decrypt their credential" | `FERNET_KEY` differs from the one used to encrypt | Use the original key |

To see the full error behind a failure:

```bash
journalctl -u monday-bot -n 50 --no-pager
```
