# Setting the admin password when you deploy

Follow these steps **on the server** (the machine that will run the Flask
backend). Do them once when you first deploy; repeat the same steps any
time you want to change the password.

This file is committed to the repo (unlike `docs/`, which is gitignored),
so it travels with a `git clone` to the deployment machine.

## How it works, in one paragraph

The app never stores your password. It stores a **hash** — a scrambled
fingerprint of the password that can't be turned back into it — in an
environment variable called `ADMIN_PASSWORD_HASH`. A second variable,
`SECRET_KEY`, signs the login cookie so nobody can forge one. When both
are set, the site is in production mode: visitors can only read, and
`/login` asks for your password. When neither is set (your laptop), the
app is in dev mode and treats you as admin without any password.

## Step 0: Prerequisites on the server

You have cloned the repo and installed the backend dependencies:

```sh
git clone git@github.com:kriti2507/small-wins && cd small-wins
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt gunicorn
```

## Step 1: Choose a password

Pick a long password you don't use anywhere else, and save it in your
password manager **now** — there is no "forgot password" flow. (If you do
lose it, you haven't lost data: just repeat these steps with a new
password.)

## Step 2: Generate the password hash

Run this on the server and type your password when prompted:

```sh
.venv/bin/python -c "from werkzeug.security import generate_password_hash; print(generate_password_hash(input('Password: ')))"
```

It prints one long line starting with `scrypt:` or `pbkdf2:` — that's the
hash. Copy the whole line exactly.

- If it errors with `module 'hashlib' has no attribute 'scrypt'` (old
  Python, e.g. macOS system Python 3.9), use this variant instead:

  ```sh
  .venv/bin/python -c "from werkzeug.security import generate_password_hash; print(generate_password_hash(input('Password: '), method='pbkdf2'))"
  ```

- The hash is safe to store on the server, but don't publish it: it can't
  be reversed, though a leaked hash lets attackers try guesses offline.

## Step 3: Generate the cookie-signing secret

```sh
.venv/bin/python -c "import secrets; print(secrets.token_hex(32))"
```

Copy the output (64 random hex characters). This is `SECRET_KEY`. You
never type it anywhere again — it just needs to be set and to stay the
same across restarts (changing it logs every device out).

## Step 4: Set both as environment variables

How depends on how the backend runs. Pick the one that matches:

**a) Quick manual test in a shell** — note the **single quotes**, the
hash contains `$` characters that a shell would otherwise mangle:

```sh
export ADMIN_PASSWORD_HASH='scrypt:32768:8:1$PASTE$THE_WHOLE_LINE_HERE'
export SECRET_KEY='paste-the-64-hex-characters-here'
export TRUST_PROXY=1   # only if nginx/caddy sits in front (it usually does)
cd backend
../.venv/bin/gunicorn -w 2 -b 127.0.0.1:5000 app:app
```

**b) systemd service (typical Linux server)** — in
`/etc/systemd/system/small-wins.service`, values are pasted as-is (no
quoting gymnastics needed):

```ini
[Service]
WorkingDirectory=/home/you/small-wins/backend
Environment=ADMIN_PASSWORD_HASH=scrypt:32768:8:1$PASTE$THE_WHOLE_LINE
Environment=SECRET_KEY=paste-the-64-hex-characters
Environment=TRUST_PROXY=1
ExecStart=/home/you/small-wins/.venv/bin/gunicorn -w 2 -b 127.0.0.1:5000 app:app
Restart=on-failure
```

Then `sudo systemctl daemon-reload && sudo systemctl restart small-wins`.

**c) Hosting platform (Render, Railway, Fly.io, ...)** — paste
`ADMIN_PASSWORD_HASH`, `SECRET_KEY`, and `TRUST_PROXY=1` into the
service's environment-variables panel, exactly as generated, then
redeploy.

Never put either value in the code, in git, or in the frontend.

## Step 5: Verify it worked

```sh
curl -s https://yourdomain.com/api/auth/me
# → {"is_admin":false}        (good: the site no longer trusts everyone)
```

Then open `https://yourdomain.com/login` in a browser, enter the
password, and check the edit buttons unlock. On other browsers/devices
the buttons should stay dimmed with the "Only admin can make changes"
tooltip.

If the app refuses to start with
`RuntimeError: SECRET_KEY must be set when ADMIN_PASSWORD_HASH is configured`,
that's the built-in safety check — Step 3/4 wasn't applied.

**Important: login only sticks over HTTPS.** In production mode the
session cookie is marked `Secure`, so browsers drop it on plain
`http://` (localhost excepted). Set up HTTPS before testing login on the
real domain.

## Changing the password later

1. Repeat Step 2 with the new password → new hash.
2. Replace `ADMIN_PASSWORD_HASH` wherever you set it in Step 4.
3. Restart the backend.

Already-logged-in devices stay logged in for up to 30 days. If you're
changing the password because you suspect someone got in, **also**
repeat Step 3 and replace `SECRET_KEY` — that instantly logs out every
device, including yours.
