import os
import uuid
import shutil
import exiftool
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from apscheduler.schedulers.background import BackgroundScheduler

from .database import create_tables, get_db, Profile, ProcessedFile

UPLOAD_DIR = Path("data/uploads")
OUTPUT_DIR = Path("data/outputs")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="MetaBot")
templates = Jinja2Templates(directory="app/templates")
app.mount("/static", StaticFiles(directory="app/static"), name="static")


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
    # seed default Miami profile if none exist
    db_gen = get_db()
    db = next(db_gen)
    try:
        if db.query(Profile).count() == 0:
            p = Profile(
                name="iPhone 15 Pro Max — Miami",
                is_default=True,
            )
            db.add(p)
            db.commit()
    finally:
        try:
            next(db_gen)
        except StopIteration:
            pass

    scheduler = BackgroundScheduler()
    scheduler.add_job(cleanup_old_files, "interval", hours=1)
    scheduler.start()


# ── Pages ────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index(request: Request, db: Session = Depends(get_db)):
    profiles = db.query(Profile).order_by(Profile.created_at).all()
    default = next((p for p in profiles if p.is_default), profiles[0] if profiles else None)
    return templates.TemplateResponse("index.html", {
        "request": request,
        "profiles": profiles,
        "default_profile": default,
    })


# ── Profile CRUD ─────────────────────────────────────────────────────────────

@app.get("/api/profiles")
async def list_profiles(db: Session = Depends(get_db)):
    return db.query(Profile).order_by(Profile.created_at).all()


@app.get("/api/profiles/{profile_id}")
async def get_profile(profile_id: int, db: Session = Depends(get_db)):
    p = db.query(Profile).filter(Profile.id == profile_id).first()
    if not p:
        raise HTTPException(404, "Profile not found")
    return p


@app.post("/api/profiles")
async def create_profile(
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
    if is_default:
        db.query(Profile).filter(Profile.is_default == True).update({"is_default": False})
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
    p = db.query(Profile).filter(Profile.id == profile_id).first()
    if not p:
        raise HTTPException(404, "Profile not found")
    if is_default:
        db.query(Profile).filter(Profile.is_default == True).update({"is_default": False})
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
async def delete_profile(profile_id: int, db: Session = Depends(get_db)):
    p = db.query(Profile).filter(Profile.id == profile_id).first()
    if not p:
        raise HTTPException(404, "Profile not found")
    db.delete(p)
    db.commit()
    return {"ok": True}


@app.post("/api/profiles/{profile_id}/set-default")
async def set_default(profile_id: int, db: Session = Depends(get_db)):
    db.query(Profile).update({"is_default": False})
    p = db.query(Profile).filter(Profile.id == profile_id).first()
    if not p:
        raise HTTPException(404, "Profile not found")
    p.is_default = True
    db.commit()
    return {"ok": True}


# ── Process file ─────────────────────────────────────────────────────────────

PHOTO_EXT = {".jpg", ".jpeg", ".png", ".heic", ".tiff", ".webp"}
VIDEO_EXT = {".mp4", ".mov", ".avi", ".mkv", ".m4v"}


@app.post("/api/process")
async def process_file(
    file: UploadFile = File(...),
    profile_id: int = Form(...),
    custom_datetime: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
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

    tags = {
        "Make": profile.make,
        "Model": profile.model,
        "Software": profile.software,
        "LensMake": profile.lens_make,
        "LensModel": profile.lens_model,
        "FNumber": profile.f_number,
        "FocalLength": profile.focal_length,
        "ISO": profile.iso,
        "ExposureTime": profile.exposure_time,
        "DateTimeOriginal": shoot_dt,
        "CreateDate": shoot_dt,
        "ModifyDate": shoot_dt,
        "GPSLatitude": abs(profile.gps_latitude),
        "GPSLatitudeRef": "N" if profile.gps_latitude >= 0 else "S",
        "GPSLongitude": abs(profile.gps_longitude),
        "GPSLongitudeRef": "E" if profile.gps_longitude >= 0 else "W",
        "GPSAltitude": profile.gps_altitude,
        "GPSAltitudeRef": 0,
        "GPSDateStamp": shoot_dt[:10].replace(":", ":"),
    }

    with exiftool.ExifToolHelper() as et:
        et.set_tags(
            [str(out_path)],
            tags=tags,
            params=["-overwrite_original", "-ignoreMinorErrors"],
        )

    out_filename = f"{uid}_processed{ext}"
    db_file = ProcessedFile(
        filename=out_filename,
        original_name=file.filename,
    )
    db.add(db_file)
    db.commit()

    return {
        "download_url": f"/api/download/{out_filename}",
        "filename": out_filename,
    }


@app.get("/api/download/{filename}")
async def download(filename: str):
    path = OUTPUT_DIR / filename
    if not path.exists():
        raise HTTPException(404, "File not found or expired")
    return FileResponse(
        path,
        media_type="application/octet-stream",
        filename=filename,
    )
