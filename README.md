# NeuroScan AI

A web app for brain tumor MRI classification. Doctors register, an administrator
verifies them, and approved doctors upload MRI images to get a classification
with a confidence score.

**Stack:** FastAPI, PostgreSQL (SQLAlchemy), JWT authentication, PyTorch, and a
plain HTML/CSS/JavaScript frontend served by FastAPI.

## How it works

1. A doctor signs up with name, email, institution, designation and license number.
   The account starts as **pending** and cannot log in.
2. The administrator reviews the details in the admin dashboard and **approves** or
   **rejects** the doctor (with a reason). Approved doctors can be **revoked** later,
   which logs them out immediately.
3. An approved doctor logs in, uploads a JPG or PNG MRI slice, and sees the predicted
   class, the confidence and the probability of every class. Scans are saved to a
   private history.

The administrator account is created automatically from the `.env` file the first
time the app starts. There is no public admin signup.

## Setup

Requirements: Python 3.10 to 3.12, PostgreSQL, and your trained model file (`.pth`).

```powershell
# 1. Create and activate a virtual environment
python -m venv venv
venv\Scripts\activate

# 2. Install the packages (torch is a large download)
pip install -r requirements.txt

# 3. Create your settings file, then open .env and fill it in
copy .env.example .env

# 4. Put your trained weights in app/weights/ (for example model.pth)

# 5. Run the app from the project root
uvicorn app.main:app --reload
```

Open <http://127.0.0.1:8000>. Interactive API docs are at <http://127.0.0.1:8000/docs>.

Create the PostgreSQL database and user first (in pgAdmin):

```sql
CREATE DATABASE neuroscan_db;
CREATE USER neuroscan_user WITH PASSWORD 'yourpassword';
GRANT ALL PRIVILEGES ON DATABASE neuroscan_db TO neuroscan_user;
GRANT ALL ON SCHEMA public TO neuroscan_user;
```

Run `GRANT ALL ON SCHEMA public` while connected to `neuroscan_db`. The tables are
created automatically when the app starts.

## More features

- **Login protection.** Five wrong passwords for one email from one address block login for 15 minutes
  (`LOGIN_MAX_ATTEMPTS`, `LOGIN_WINDOW_MINUTES`). Counters are kept in memory, so they reset when the server restarts.
- **Password reset.** "Forgot your password?" on the login page emails a one-time link (`RESET_TOKEN_MINUTES`).
  The answer is the same whether or not the email exists. The administrator can send a doctor a reset link from the
  Doctors tab (the admin never sees or sets the password). A reset signs out every older session.
- **Email notices.** Doctors are emailed when approved, rejected or revoked. Without `SMTP_HOST` in `.env`, emails are
  printed in the terminal, and the admin reset dialog shows the link so it can be passed on by hand.
- **Audit log.** Admin tab listing registrations, approvals, rejections, revocations, reset links, locked logins,
  turned-away images and deleted scans, with time and actor. It never holds images or case references.
- **Analytics.** Admin tab with scans per day, scans per class, rejection rate and how often doctors agree with the model.
- **Doctor feedback.** In Scan details a doctor marks Agree or Disagree with an optional note. It appears in the history,
  the CSV and the PDF.
- **History search.** Filter by case reference or file name, result class and date range, and export the filtered list to CSV.

## Deploying for real use: HTTPS is required

This project runs over plain HTTP on your own computer, which is fine for development and a demo. Before it handles
real patient data it must be served over **HTTPS**. Without it, passwords, login tokens and MRI images travel unencrypted
and can be read or altered by anyone on the network. Put the app behind a reverse proxy that holds a TLS certificate
(for example Nginx or Caddy with a free Let's Encrypt certificate), redirect HTTP to HTTPS, set `APP_BASE_URL` to the
`https://` address and `ALLOWED_ORIGINS` to match, and add the `Strict-Transport-Security` header. Run with several
server processes only after moving the login counters to a shared store such as Redis. Also change the admin password,
use a strong `SECRET_KEY`, back up the database, and complete a data-protection review.

## Model settings

**MS-CBAM-Net (the notebook's checkpoint).** Copy the `.pth` file to `app/weights/model.pth`
(or set `MODEL_PATH`). Nothing else is needed: the file carries its own class names, normalisation
numbers and rejection data, and the app rebuilds the network from `app/ml/mscbam_net.py`. Predictions
use the notebook's preprocessing (resize 256, centre crop 224, AutoContrast) and flip test-time
augmentation, and results match the notebook's `predict_image`.

Two reliability checks run on every image:

| Check | What it does | Default |
|---|---|---|
| Distance (Mahalanobis) | Is the image's feature vector close to the training MRIs? | **Rejects** the image: it is not classified and not saved |
| Confidence and entropy | Is the model sure enough? | **Flags** the scan for manual review, but still classifies it |

Turn either into the other behaviour with `REJECT_ON_DISTANCE` and `REJECT_ON_CONFIDENCE` in `.env`.

**Standard networks.** For a plain weights file of `resnet50`, `vgg16`, `densenet121` or `mobilenet_v2`,
set `MODEL_ARCH`, `CLASS_NAMES`, `IMAGE_SIZE`, `NORM_MEAN`, `NORM_STD` and `USE_AUTOCONTRAST` to match
your training. For any other custom network, add its class to `app/ml` and load it in `model_loader.py`.

If the model cannot be loaded, the website still runs. The admin overview explains what is wrong,
and doctors see a short "model offline" notice.

## Project structure

```
app/
  main.py            App startup, admin seeding, routers
  config.py          Settings read from .env
  database.py        PostgreSQL connection
  models.py          Tables: users, predictions
  schemas.py         Request and response validation
  auth.py            Password hashing and JWT tokens
  dependencies.py    Login and role checks for routes
  routers/
    auth_routes.py   Signup, login
    admin_routes.py  Stats, review doctors, activity
    doctor_routes.py Predict, history, image, delete
    pages.py         Serves the HTML pages
  ml/
    mscbam_net.py    MS-CBAM-Net architecture and distance check
    model_loader.py  Loads the PyTorch model once
    predict.py       Preprocessing, inference, rejection checks
    gradcam.py       Grad-CAM heatmap
  report.py          PDF report builder
  ratelimit.py       Login lock after repeated failures
  emailer.py         Sends email (or prints it in development)
  audit.py           Writes the audit log
  weights/           Put your .pth file here
static/
  css/style.css      Design system
  js/app.js          Shared helpers
  uploads/           Uploaded images (created automatically, never public)
templates/           index, login, signup, admin_dashboard, doctor_dashboard
```

## API overview

| Method and path | Who | Purpose |
|---|---|---|
| `POST /api/auth/signup` | Anyone | Register as a doctor (pending) |
| `POST /api/auth/login` | Anyone | Log in, returns a token |
| `GET /api/admin/stats` | Admin | Counts and model status |
| `GET /api/admin/doctors?status=` | Admin | List doctors |
| `POST /api/admin/doctors/{id}/approve` | Admin | Approve |
| `POST /api/admin/doctors/{id}/reject` | Admin | Reject or revoke, with a reason |
| `GET /api/admin/activity` | Admin | Recent scans (no images) |
| `POST /api/doctor/predict` | Approved doctor | Upload an MRI, get a prediction (or a rejection) |
| `GET /api/doctor/history` | Approved doctor | Own scan history |
| `GET /api/doctor/predictions/{id}/image` | Owner only | The uploaded image |
| `GET /api/doctor/predictions/{id}/heatmap` | Owner only | Grad-CAM heatmap (PNG, made on request) |
| `GET /api/doctor/predictions/{id}/report` | Owner only | PDF report of the scan |
| `POST /api/doctor/predictions/{id}/feedback` | Owner only | Agree or disagree, with a note |
| `GET /api/doctor/history/export.csv` | Approved doctor | Filtered history as CSV |
| `DELETE /api/doctor/predictions/{id}` | Owner only | Delete a scan |
| `POST /api/auth/forgot-password` | Anyone | Email a reset link (same answer for any email) |
| `POST /api/auth/reset-password` | Anyone with a link | Choose a new password |
| `POST /api/admin/doctors/{id}/reset-password` | Admin | Send a doctor a reset link |
| `GET /api/admin/audit` | Admin | Audit log |
| `GET /api/admin/analytics?days=` | Admin | Chart numbers |

## Security notes

- Passwords are hashed with bcrypt. Tokens are signed JWTs that expire.
- A doctor's status is checked on every request, so revoking access works at once.
- Uploaded images are stored under random names in `static/uploads/`, which is **not**
  served publicly. Only the doctor who uploaded an image can fetch it.
- Uploads are checked by extension, size and by actually opening the image.
- User-provided text is escaped before it is shown, which blocks script injection.
- `.env`, the virtual environment, uploads and weight files are in `.gitignore`.

For a real hospital deployment you would also add HTTPS, rate limiting on login,
and a proper data-protection review. This project is a prototype for study.

## Troubleshooting

- **"Could not connect to the database":** PostgreSQL is not running, or `DATABASE_URL`
  has a wrong user, password or database name. Special characters in the password must be
  URL-encoded (`@` becomes `%40`).
- **"permission denied for schema public":** run `GRANT ALL ON SCHEMA public TO neuroscan_user;`
  while connected to `neuroscan_db`.
- **"Missing setting ...":** a value is missing from `.env`.
- **Model offline:** open the Overview tab as admin. It shows the exact reason, such as a
  wrong path, a wrong `MODEL_ARCH`, or `CLASS_NAMES` with the wrong number of classes.
- **You changed `models.py` after the tables exist:** `create_all` does not alter existing
  tables. The app adds the known new columns itself at startup (see `upgrade_schema` in `database.py`);
  for any other change, drop the tables in pgAdmin and restart.
- **Run from the project root.** Start `uvicorn` in the folder that contains `app/`,
  not inside `app/`.
