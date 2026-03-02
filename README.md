# RollCall (Sign-On Page)

A self-contained web app for registering and updating user accounts across all services in a self-hosted media server suite. Unlike the other tools in this ecosystem which are embedded as iframes in Homarr, RollCall runs as its own standalone site on its own port — intended to be shared directly with users as their onboarding link.

---

## Features

- **Single registration** across Jellyfin, RomM, Booklore, Synapse, Filebrowser, and Immich in one form submission
- **Bulk mode** — register up to 32 users at once by entering comma-separated usernames
- **Update mode** — update passwords or service access for existing accounts
- **Service selection** — choose which services to register/update per submission
- **Admin services** — Filebrowser and Immich registration is shown only to local network users (auto-detected)
- **Gate** — remote users must enter a site password before accessing the form; local network users bypass it automatically
- **Email domain** — configurable via environment variable; displayed in the form and used to build email addresses on registration
- **Results screen** — shows per-service success/failure with links to each service

---

## Architecture

RollCall is split into two containers:

| Container | Description |
|-----------|-------------|
| `sign-on-frontend` | Nginx serving the static HTML/CSS/JS frontend |
| `sign-on-backend` | Flask API that handles authentication and calls each service's API to create/update users |

The frontend fetches `/config` from the backend on load to get the email domain hint, service URLs, and password hint. All service API calls are made server-side by the backend — no credentials are exposed to the browser.

---

## Files

| File | Description |
|------|-------------|
| `pages/index.html` | The full frontend — gate, registration form, and results screen |
| `pages/assets/` | CSS and logo assets |
| `backend/app.py` | Flask API — `/verify`, `/config`, and `/register` endpoints |
| `backend/requirements.txt` | Python dependencies |
| `Dockerfile` | Container definition for the backend |
| `docker-compose.yml` | Standalone compose file for running RollCall on its own |

---

## Supported Services

| Service | Create | Update |
|---------|--------|--------|
| Jellyfin | ✅ | ✅ |
| RomM | ✅ | ✅ |
| Booklore | ✅ | ✅ |
| Synapse (Matrix) | ✅ | ✅ |
| Filebrowser Quantum | ✅ | ✅ |
| Immich | ✅ | ✅ |

---

## Deployment

Can be deployed standalone via `docker-compose.yml` in this repo, or as part of the full stack via `landing-compose.yml` in the [landing-page](https://github.com/Treyzer567/landing-page) repo.

### Environment Variables

| Variable | Description |
|----------|-------------|
| `SITE_PASSWORD` | Password required for remote users to access the form |
| `PASS_HINT` | Hint text shown on the gate screen |
| `BACKEND_EXTERNAL_URL` | Public-facing URL of the backend (used by the frontend to locate the API) |
| `EMAIL_DOMAIN` | Domain used to build email addresses (e.g. `yourdomain.com`) |
| `WIKI_EXTERNAL_URL` | Link shown on the success screen |
| `HOME_EXTERNAL_URL` | Home link shown on the success screen |
| `JELLYFIN_INTERNAL_URL` | Internal URL of Jellyfin |
| `JELLYFIN_API_KEY` | Jellyfin API key |
| `JELLYFIN_EXTERNAL_URL` | Public URL of Jellyfin (shown on success screen) |
| `ROMM_INTERNAL_URL` | Internal URL of RomM |
| `ROMM_ADMIN_USER` | RomM admin username |
| `ROMM_ADMIN_PASS` | RomM admin password |
| `ROMM_EXTERNAL_URL` | Public URL of RomM |
| `BOOKLORE_INTERNAL_URL` | Internal URL of Booklore |
| `BOOKLORE_ADMIN_USER` | Booklore admin username |
| `BOOKLORE_ADMIN_PASS` | Booklore admin password |
| `BOOKLORE_EXTERNAL_URL` | Public URL of Booklore |
| `SYNAPSE_INTERNAL_URL` | Internal URL of Synapse |
| `SYNAPSE_ACCESS_TOKEN` | Synapse admin access token |
| `SYNAPSE_DOMAIN` | Matrix server domain (e.g. `matrix.yourdomain.com`) |
| `SYNAPSE_EXTERNAL_URL` | Public URL of the Matrix client |
| `FILEBROWSER_INTERNAL_URL` | Internal URL of Filebrowser Quantum |
| `FILEBROWSER_API_KEY` | Filebrowser Quantum API key |
| `FILEBROWSER_EXTERNAL_URL` | Public URL of Filebrowser |
| `IMMICH_INTERNAL_URL` | Internal URL of Immich |
| `IMMICH_API_KEY` | Immich admin API key |
| `IMMICH_EXTERNAL_URL` | Public URL of Immich |

---

## Related Repos

| Repo | Description |
|------|-------------|
| [landing-page](https://github.com/Treyzer567/landing-page) | Frontend hub — links to RollCall from the home page |
| [themes](https://github.com/Treyzer567/themes) | Custom themes for Jellyfin, Homarr, and other services |

---

## External Projects

| Project | Description |
|---------|-------------|
| [Jellyfin](https://github.com/jellyfin/jellyfin) | Open source media server |
| [RomM](https://github.com/rommapp/romm) | Self-hosted ROM manager |
| [Booklore](https://github.com/booklore-app/booklore) | Self-hosted digital library |
| [Synapse](https://github.com/element-hq/synapse) | Matrix homeserver |
| [Filebrowser Quantum](https://github.com/gtsteffaniak/filebrowser) | Self-hosted web file manager |
| [Immich](https://github.com/immich-app/immich) | Self-hosted photo library |
