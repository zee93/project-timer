import http
import logging

from typing import Optional
from datetime import date, timedelta
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse

from beats.db_helpers import serialize_from_document, serialize_to_document
from beats.exceptions import ProjectWasNotStarted, TwoProjectInProgess, NoObjectMatched
from beats.domain import ProjectRepository, Project, Beat, BeatRepository
from beats.settings import settings
from beats.validation_models import RecordTimeValidator

logger = logging.getLogger(__name__)
app = FastAPI()
origins = [
    "http://localhost",
    "http://localhost:8000",
    "http://localhost:8080",
    "https://lifepete.com",
    "http://lifepete.com"
    "http://site.lifepete.com/"
]


@app.middleware("http")
async def authenticate(request: Request, call_next):
    logger.error(request.method)
    PROTECTED_METHODS = ["POST", "PUT", "PATCH"]
    if request.method in PROTECTED_METHODS and "X-API-Token" not in request.headers:
        return JSONResponse(
            content={"error": "Header X-API-Token is required for all POST actions"},
            status_code=status.HTTP_401_UNAUTHORIZED
        )
    if request.method in PROTECTED_METHODS and request.headers["X-API-Token"] != settings.access_token:
        return JSONResponse(
            content={"error": "your X-API-Token is not valid"},
            status_code=status.HTTP_401_UNAUTHORIZED
        )
    response = await call_next(request)
    return response


@app.get("/projects")
async def list_projects(archived: bool = False):
    data = [serialize_from_document(p) for p in ProjectRepository.list({"archived": archived})]
    return data


@app.post("/projects", status_code=http.HTTPStatus.CREATED)
async def create_project(project: Project):
    project = ProjectRepository.create(project.dict(exclude_none=True))
    return serialize_from_document(project)


@app.put("/projects")
async def update_project(project: Project):
    project = ProjectRepository.update(serialize_to_document(project.dict(exclude_none=True)))
    return serialize_from_document(project)


@app.post("/projects/{project_id}/archive")
async def archive_project(project_id: str):
    ProjectRepository.update({'_id': project_id, 'archived': True})
    return {"status": "success"}


@app.get("/projects/{project_id}/today/")
async def today_time_for_project(project_id: str):
    logs = list(BeatRepository.list({"project_id": project_id}))
    today_logs = [Beat(**serialize_from_document(log)) for log in logs if Beat(**log).start.date() == date.today()]
    return {"duration": str(sum([log.duration for log in today_logs], timedelta()))}


@app.get("/projects/{project_id}/summary/")
async def get_project_summary(project_id: str):
    logs = list(BeatRepository.list({"project_id": project_id}))
    logs = [Beat(**serialize_from_document(log)) for log in logs]
    statistical = {}
    for log in logs:
        if not statistical.get(log.day):
            statistical[log.day] = []
        statistical[log.day].append(log.duration)
    statistical = {key: str(sum(value)) for key, value in statistical}
    return statistical


@app.post("/projects/{project_id}/start")
async def start_project_timer(project_id: str, time_validator: RecordTimeValidator):
    available_project_ids = [str(p["_id"]) for p in ProjectRepository.list()]
    if project_id not in available_project_ids:
        return {"project_id": "This project id does not exist"}
    logs = list(BeatRepository.list({"project_id": project_id, "end": None}))
    if logs:
        log = logs[0]
        log = Beat(**serialize_from_document(log))
        return JSONResponse(
            content={"error": "another beat already in progress", "beat": log.json(exclude_none=True)},
            status_code=status.HTTP_400_BAD_REQUEST
        )
        # raise ProjectAlreadyStarted
    log = Beat(project_id=project_id, start=time_validator.time)
    log = Beat(**serialize_from_document(BeatRepository.create(log.dict(exclude_none=True))))
    return log


@app.post("/projects/stop")
async def end_project_timer(time_validator: RecordTimeValidator):
    logs = list(BeatRepository.list({"end": None}))
    if not logs:
        raise ProjectWasNotStarted
    if len(logs) > 1:
        raise TwoProjectInProgess
    log = serialize_from_document(logs[0])
    logger.info(f"We got log {log}")
    log = Beat(**log)
    logger.info(f"Validated log: {log.dict()}")
    log.stop_timer(time=time_validator.time)
    BeatRepository.update(serialize_to_document(log.dict()))
    return log


@app.get("/beats")
async def list_beats(project_id: Optional[str] = None, date: Optional[date] = None):
    filters = {}
    if project_id:
        filters.update({"project_id": project_id})
    if date:
        filters.update({"date": date})

    logs = list(BeatRepository.list(filters))
    return [serialize_from_document(log) for log in logs]


@app.post("/beats", status_code=http.HTTPStatus.CREATED)
async def create_beat(log: Beat):
    log = BeatRepository.create(log.dict(exclude_none=True))
    return serialize_from_document(log)


@app.get("/beats/{beat_id}")
async def get_beat(beat_id: str):
    beat = BeatRepository.retrieve_by_id(beat_id)
    return serialize_from_document(beat)


@app.put("/beats")
async def update_beat(log: Beat):
    log = BeatRepository.update(serialize_to_document(log.dict()))
    return serialize_from_document(log)


@app.get("/heart/sounds")
async def heart_status():
    try:
        last_beat = Beat(**serialize_from_document(BeatRepository.get_last()))
    except NoObjectMatched:
        return {
            "isBeating": False,
            "project": None,
        }
    if last_beat.is_beating():
        return {
            "isBeating": True,
            "project": last_beat.project_id,
            "since": last_beat.start,
            "so_far": last_beat.duration
        }
    else:
        return {
            "isBeating": False,
            "lastBeatOn": last_beat.project_id,
            "for": last_beat.duration
        }


@app.post("/talk/ding")
async def ding():
    return {"message": "dong"}


# Putting the middleware at the end fixes a CORS issue with 401 POST requests
# There is still an issue with 500's
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
