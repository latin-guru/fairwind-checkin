"""Fairwind Travel Advisors — Guest Check-in (sample-data demo, mocked HubSpot API)."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError

from app import choices, config, csrf, db, guests
from app.hubspot.mock import CONSENT_TEXT, MockHubSpotClient
from app.mapping import PROPERTY_TABLE, contact_properties
from app.schemas import CheckIn, errors_by_field

ROOT = Path(__file__).resolve().parent.parent
FORM_FIELDS = ("first_name", "last_name", "email", "zip", "age_range", "trip_type", "party_size", "budget_band",
               "source")


def create_app(settings: config.Settings | None = None) -> FastAPI:
    settings = settings or config.load()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        db.init(settings.database_url)
        if settings.demo_mode:
            from app.seed import seed

            seed()
        yield

    app = FastAPI(title="Fairwind Travel Guest Check-in (demo)", lifespan=lifespan, docs_url=None, redoc_url=None)
    app.state.settings = settings
    app.state.hubspot = MockHubSpotClient(portal_id=settings.portal_id, form_guid=settings.form_guid,
                                          consent_source=settings.consent_source)
    app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
    templates = Jinja2Templates(directory=ROOT / "templates")
    templates.env.globals["choices"] = choices

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        resp = await call_next(request)
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["Referrer-Policy"] = "same-origin"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
            "frame-ancestors 'none'; form-action 'self'; base-uri 'none'"
        )
        return resp

    def render(request: Request, name: str, ctx: dict, status: int = 200) -> HTMLResponse:
        token = request.cookies.get(csrf.COOKIE) or csrf.new_token()
        ctx = {"request": request, "csrf": csrf.sign(token, settings.secret_key), **ctx}
        resp = templates.TemplateResponse(request, name, ctx, status_code=status)
        resp.set_cookie(csrf.COOKIE, token, httponly=True, samesite="strict", secure=request.url.scheme == "https")
        return resp

    def csrf_ok(request: Request, value: str | None) -> bool:
        return csrf.valid(request.cookies.get(csrf.COOKIE), value, settings.secret_key)

    # ---------- check-in ----------

    @app.get("/", response_class=HTMLResponse)
    def checkin_form(request: Request):
        return render(request, "checkin.html", {"values": {}, "errors": {}, "consent_text": CONSENT_TEXT})

    @app.post("/check-in", response_class=HTMLResponse)
    async def checkin_submit(request: Request):
        form = await request.form()
        values = {k: str(form.get(k, "")) for k in FORM_FIELDS}
        if not csrf_ok(request, form.get("csrf")):
            return render(request, "checkin.html",
                          {"values": values, "errors": {"form": "Your session expired. Please submit again."},
                           "consent_text": CONSENT_TEXT}, status=400)
        if form.get("website"):  # honeypot: people never see this field
            return RedirectResponse("/thanks", status_code=303)
        try:
            data = CheckIn(**values, marketing_consent=form.get("marketing_consent") == "yes")
        except ValidationError as exc:
            return render(request, "checkin.html",
                          {"values": values, "errors": errors_by_field(exc), "consent_text": CONSENT_TEXT},
                          status=422)
        guest, is_new, consent_changed = guests.save_checkin(data)
        app.state.hubspot.sync_checkin(guest, is_new=is_new, consent_changed=consent_changed)
        return RedirectResponse(f"/thanks?g={guest.optout_token}", status_code=303)

    @app.get("/thanks", response_class=HTMLResponse)
    def thanks(request: Request, g: str = ""):
        guest = guests.find_by_token(g)
        props = contact_properties(guest, consent_source=settings.consent_source, is_new=guest.checkin_count == 1) \
            if guest else None
        return render(request, "thanks.html", {"guest": guest, "props": props})

    # ---------- opt-out ----------

    @app.get("/opt-out", response_class=HTMLResponse)
    def optout_page(request: Request, g: str = ""):
        return render(request, "optout.html", {"guest": guests.find_by_token(g), "token": g, "done": False})

    @app.post("/opt-out", response_class=HTMLResponse)
    def optout_submit(request: Request, csrf_value: str = Form("", alias="csrf"), token: str = Form(""),
                      email: str = Form("")):
        if not csrf_ok(request, csrf_value):
            return render(request, "optout.html", {"guest": None, "token": token, "done": False,
                                                   "error": "Your session expired. Please try again."}, status=400)
        guest = guests.find_by_token(token) if token else guests.find_by_email(email)
        if guest:
            updated = guests.opt_out(guest.id)
            app.state.hubspot.sync_optout(updated)
        # Same answer whether or not the email exists, so this page can't be used to check who is a guest.
        return render(request, "optout.html", {"guest": None, "token": "", "done": True})

    # ---------- dashboard ----------

    @app.get("/dashboard", response_class=HTMLResponse)
    def dashboard(request: Request):
        from app import profile, segments

        everyone = guests.all_guests()
        return render(request, "dashboard.html", {
            "totals": profile.totals(everyone),
            "profile": profile.ideal_traveler(everyone),
            "lists": segments.suggested_lists(everyone),
            "segments_minimums": segments.AD_MINIMUMS,
            "recent": everyone[:12],
            "last_sync": last_sync_time(),
        })

    def last_sync_time():
        from sqlalchemy import func, select

        from app.models import SyncLog

        with db.session() as s:
            return s.scalar(select(func.max(SyncLog.created_at)))

    @app.post("/dashboard/opt-out/{guest_id}")
    def dashboard_optout(request: Request, guest_id: int, csrf_value: str = Form("", alias="csrf")):
        if csrf_ok(request, csrf_value):
            updated = guests.opt_out(guest_id)
            if updated:
                app.state.hubspot.sync_optout(updated)
        return RedirectResponse("/dashboard#recent", status_code=303)

    @app.get("/mapping", response_class=HTMLResponse)
    def mapping(request: Request):
        return render(request, "mapping.html", {"table": PROPERTY_TABLE})

    @app.get("/sync-log", response_class=HTMLResponse)
    def sync_log(request: Request):
        from sqlalchemy import select

        from app.models import SyncLog

        with db.session() as s:
            rows = list(s.scalars(select(SyncLog).order_by(SyncLog.id.desc()).limit(30)))
        return render(request, "sync_log.html", {"rows": rows})

    @app.get("/healthz")
    def healthz():
        return {"ok": True, "crm": "mock"}

    return app


app = create_app()
