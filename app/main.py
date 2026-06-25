import os
import uuid
import shutil
import exiftool
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException, Request, Response
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from apscheduler.schedulers.background import BackgroundScheduler

from .database import create_tables, get_db, Profile, ProcessedFile

UPLOAD_DIR = Path("data/uploads")
OUTPUT_DIR = Path("data/outputs")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

AUTH_USERNAME = "user"
AUTH_PASSWORD = "987321"
AUTH_COOKIE = "mb_session"
AUTH_TOKEN = "metabot_secret_token_x9k2"

app = FastAPI(title="MetaBot")
templates = Jinja2Templates(directory="app/templates")
static_dir = Path("app/static")
static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


def is_authenticated(request: Request) -> bool:
    return request.cookies.get(AUTH_COOKIE) == AUTH_TOKEN


def require_auth(request: Request):
    if not is_authenticated(request):
        raise HTTPException(status_code=401, detail="Not authenticated")


def cleanup_old_files():
    db_gen = get_db()
    db = next(db_gen)
    try:
        cutoff = datetime.utcnow() - timedelta(hours=24)
        old = db.query(ProcessedFile).filter(ProcessedFile.created_at < cutoff).all()
        for f in old:
            for d in [UPLOAD_DIR, OUTPUT_DIR]:
                p = d / f.filename
                if p.exists():
                    p.unlink()
            db.delete(f)
        db.commit()
    finally:
        try:
            next(db_gen)
        except StopIteration:
            pass


@app.on_event("startup")
def startup():
    create_tables()
    db_gen = get_db()
    db = next(db_gen)
    try:
        if db.query(Profile).count() == 0:
            db.add(Profile(name="iPhone 15 Pro Max — Miami", is_default=True))
            db.commit()
    finally:
        try:
            next(db_gen)
        except StopIteration:
            pass
    scheduler = BackgroundScheduler()
    scheduler.add_job(cleanup_old_files, "interval", hours=1)
    scheduler.start()


# ── Auth ──────────────────────────────────────────────────────────────────────

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = ""):
    if is_authenticated(request):
        return RedirectResponse("/", status_code=302)
    return templates.TemplateResponse("login.html", {"request": request, "error": error})


@app.post("/login")
async def login(
    response: Response,
    username: str = Form(...),
    password: str = Form(...),
):
    if username == AUTH_USERNAME and password == AUTH_PASSWORD:
        resp = RedirectResponse("/", status_code=302)
        resp.set_cookie(AUTH_COOKIE, AUTH_TOKEN, httponly=True, max_age=86400 * 30)
        return resp
    return RedirectResponse("/login?error=1", status_code=302)


@app.get("/logout")
async def logout():
    resp = RedirectResponse("/login", status_code=302)
    resp.delete_cookie(AUTH_COOKIE)
    return resp


# ── Pages ─────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index(request: Request, db: Session = Depends(get_db)):
    if not is_authenticated(request):
        return RedirectResponse("/login", status_code=302)
    profiles = db.query(Profile).order_by(Profile.created_at).all()
    return templates.TemplateResponse("index.html", {"request": request, "profiles": profiles})


# ── Profile CRUD ──────────────────────────────────────────────────────────────

@app.get("/api/profiles")
async def list_profiles(request: Request, db: Session = Depends(get_db)):
    require_auth(request)
    return db.query(Profile).order_by(Profile.created_at).all()


@app.get("/api/profiles/{profile_id}")
async def get_profile(profile_id: int, request: Request, db: Session = Depends(get_db)):
    require_auth(request)
    p = db.query(Profile).filter(Profile.id == profile_id).first()
    if not p:
        raise HTTPException(404, "Profile not found")
    return p


@app.post("/api/profiles")
async def create_profile(
    request: Request,
    name: str = Form(...),
    make: str = Form("Apple"),
    model: str = Form("iPhone 15 Pro Max"),
    software: str = Form("17.5.1"),
    lens_make: str = Form("Apple"),
    lens_model: str = Form("iPhone 15 Pro Max back triple camera 6.765mm f/1.78"),
    f_number: float = Form(1.78),
    focal_length: float = Form(6.765),
    iso: int = Form(50),
    exposure_time: str = Form("1/2000"),
    gps_latitude: float = Form(25.7617),
    gps_longitude: float = Form(-80.1918),
    gps_altitude: float = Form(5.0),
    location_name: str = Form("Miami, FL"),
    is_default: bool = Form(False),
    db: Session = Depends(get_db),
):
    require_auth(request)
    if is_default:
        db.query(Profile).update({"is_default": False})
    p = Profile(
        name=name, make=make, model=model, software=software,
        lens_make=lens_make, lens_model=lens_model,
        f_number=f_number, focal_length=focal_length,
        iso=iso, exposure_time=exposure_time,
        gps_latitude=gps_latitude, gps_longitude=gps_longitude,
        gps_altitude=gps_altitude, location_name=location_name,
        is_default=is_default,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


@app.put("/api/profiles/{profile_id}")
async def update_profile(
    profile_id: int,
    request: Request,
    name: str = Form(...),
    make: str = Form("Apple"),
    model: str = Form("iPhone 15 Pro Max"),
    software: str = Form("17.5.1"),
    lens_make: str = Form("Apple"),
    lens_model: str = Form("iPhone 15 Pro Max back triple camera 6.765mm f/1.78"),
    f_number: float = Form(1.78),
    focal_length: float = Form(6.765),
    iso: int = Form(50),
    exposure_time: str = Form("1/2000"),
    gps_latitude: float = Form(25.7617),
    gps_longitude: float = Form(-80.1918),
    gps_altitude: float = Form(5.0),
    location_name: str = Form("Miami, FL"),
    is_default: bool = Form(False),
    db: Session = Depends(get_db),
):
    require_auth(request)
    p = db.query(Profile).filter(Profile.id == profile_id).first()
    if not p:
        raise HTTPException(404, "Profile not found")
    if is_default:
        db.query(Profile).update({"is_default": False})
    for field, val in dict(
        name=name, make=make, model=model, software=software,
        lens_make=lens_make, lens_model=lens_model,
        f_number=f_number, focal_length=focal_length,
        iso=iso, exposure_time=exposure_time,
        gps_latitude=gps_latitude, gps_longitude=gps_longitude,
        gps_altitude=gps_altitude, location_name=location_name,
        is_default=is_default,
    ).items():
        setattr(p, field, val)
    db.commit()
    db.refresh(p)
    return p


@app.delete("/api/profiles/{profile_id}")
async def delete_profile(profile_id: int, request: Request, db: Session = Depends(get_db)):
    require_auth(request)
    p = db.query(Profile).filter(Profile.id == profile_id).first()
    if not p:
        raise HTTPException(404, "Profile not found")
    db.delete(p)
    db.commit()
    return {"ok": True}


# ── File history ──────────────────────────────────────────────────────────────

@app.get("/api/files")
async def list_files(request: Request, db: Session = Depends(get_db)):
    require_auth(request)
    files = db.query(ProcessedFile).order_by(ProcessedFile.created_at.desc()).all()
    result = []
    for f in files:
        out_path = OUTPUT_DIR / f.filename
        size = out_path.stat().st_size if out_path.exists() else 0
        expires_at = f.created_at + timedelta(hours=24)
        result.append({
            "id": f.id,
            "filename": f.filename,
            "original_name": f.original_name,
            "created_at": f.created_at.isoformat(),
            "expires_at": expires_at.isoformat(),
            "size_bytes": size,
            "exists": out_path.exists(),
            "download_url": f"/api/download/{f.filename}",
        })
    return result


@app.delete("/api/files/{file_id}")
async def delete_file(file_id: int, request: Request, db: Session = Depends(get_db)):
    require_auth(request)
    f = db.query(ProcessedFile).filter(ProcessedFile.id == file_id).first()
    if not f:
        raise HTTPException(404, "File not found")
    for d in [UPLOAD_DIR, OUTPUT_DIR]:
        p = d / f.filename
        if p.exists():
            p.unlink()
    db.delete(f)
    db.commit()
    return {"ok": True}


# ── Process ───────────────────────────────────────────────────────────────────

PHOTO_EXT = {".jpg", ".jpeg", ".png", ".heic", ".tiff", ".webp"}
VIDEO_EXT = {".mp4", ".mov", ".avi", ".mkv", ".m4v"}


@app.post("/api/process")
async def process_file(
    request: Request,
    file: UploadFile = File(...),
    profile_id: int = Form(...),
    custom_datetime: Optional[str] = Form(None),
    override_lat: Optional[float] = Form(None),
    override_lng: Optional[float] = Form(None),
    db: Session = Depends(get_db),
):
    require_auth(request)
    profile = db.query(Profile).filter(Profile.id == profile_id).first()
    if not profile:
        raise HTTPException(404, "Profile not found")

    ext = Path(file.filename).suffix.lower()
    if ext not in PHOTO_EXT | VIDEO_EXT:
        raise HTTPException(400, f"Unsupported file type: {ext}")

    uid = uuid.uuid4().hex
    in_path = UPLOAD_DIR / f"{uid}{ext}"
    out_path = OUTPUT_DIR / f"{uid}_processed{ext}"

    with open(in_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    shutil.copy2(in_path, out_path)

    shoot_dt = custom_datetime or datetime.utcnow().strftime("%Y:%m:%d %H:%M:%S")
    gps_lat = override_lat if override_lat is not None else profile.gps_latitude
    gps_lng = override_lng if override_lng is not None else profile.gps_longitude
    unique_id = uid[:32].upper()

    tags = {
        "Make": profile.make,
        "Model": profile.model,
        "Software": profile.software,
        "HostComputer": profile.model,
        "LensMake": profile.lens_make,
        "LensModel": profile.lens_model,
        "LensInfo": f"{profile.focal_length} {profile.focal_length} {profile.f_number} {profile.f_number}",
        "FNumber": profile.f_number,
        "ApertureValue": profile.f_number,
        "MaxApertureValue": profile.f_number,
        "FocalLength": profile.focal_length,
        "FocalLengthIn35mmFormat": round(profile.focal_length * 6.5),
        "ISO": profile.iso,
        "ISOSpeedRatings": profile.iso,
        "ExposureTime": profile.exposure_time,
        "ShutterSpeedValue": profile.exposure_time,
        "ExposureProgram": "Program AE",
        "ExposureMode": "Auto",
        "MeteringMode": "Multi-segment",
        "Flash": "Auto, Did not fire",
        "WhiteBalance": "Auto",
        "SceneCaptureType": "Standard",
        "DateTimeOriginal": shoot_dt,
        "CreateDate": shoot_dt,
        "ModifyDate": shoot_dt,
        "ImageUniqueID": unique_id,
        "GPSLatitude": abs(gps_lat),
        "GPSLatitudeRef": "N" if gps_lat >= 0 else "S",
        "GPSLongitude": abs(gps_lng),
        "GPSLongitudeRef": "E" if gps_lng >= 0 else "W",
        "GPSAltitude": profile.gps_altitude,
        "GPSAltitudeRef": 0,
        "GPSDateStamp": shoot_dt[:10].replace("-", ":"),
        "GPSTimeStamp": shoot_dt[11:],
        "XMP:Make": profile.make,
        "XMP:Model": profile.model,
        "XMP:Software": profile.software,
        "XMP:CreatorTool": f"{profile.make} {profile.model}",
        "XMP:Lens": profile.lens_model,
        "XMP:LensModel": profile.lens_model,
        "XMP:DateCreated": shoot_dt,
        "XMP:MetadataDate": shoot_dt,
        "XMP:ModifyDate": shoot_dt,
        "XMP:CreateDate": shoot_dt,
    }

    with exiftool.ExifToolHelper() as et:
        et.set_tags(
            [str(out_path)],
            tags=tags,
            params=[
                "-overwrite_original",
                "-ignoreMinorErrors",
                "-icc_profile=",
                "-XMP-xmpMM:History=",
                "-XMP-xmpMM:DocumentID=",
                "-XMP-xmpMM:OriginalDocumentID=",
                "-XMP-xmpMM:InstanceID=",
                "-XMP-samsung:all=",
                "-XMP-GPano:all=",
            ],
        )

    out_filename = f"{uid}_processed{ext}"
    db.add(ProcessedFile(filename=out_filename, original_name=file.filename))
    db.commit()

    return {"download_url": f"/api/download/{out_filename}", "filename": out_filename}


@app.get("/api/download/{filename}")
async def download(filename: str, request: Request):
    require_auth(request)
    path = OUTPUT_DIR / filename
    if not path.exists():
        raise HTTPException(404, "File not found or expired")
    return FileResponse(path, media_type="application/octet-stream", filename=filename)
