import logging
from datetime import date, timedelta

from fastapi import FastAPI

from ptc.db_helpers import serialize_from_document, serialize_to_document
from ptc.exceptions import ProjectWasNotStarted, MoreThanOneLogOpenForProject, ProjectAlreadyStarted
from ptc.models import ProjectManager, Project, TimeLog, TimeLogManager


logger = logging.getLogger(__name__)
app = FastAPI()


@app.get("/projects")
async def list_projects():
    return [serialize_from_document(p) for p in ProjectManager.list()]


@app.post("/projects")
async def create_project(project: Project):
    ProjectManager.create(project.dict(exclude_none=True))
    return project


@app.get("/projects/{project_id}/today/summary/")
async def today_time_for_project(project_id: str):
    logs = list(TimeLogManager.list({"project_id": project_id}))
    today_logs = [TimeLog(**serialize_from_document(log)) for log in logs if TimeLog(**log).start.date() == date.today()]

    return {"duration": str(sum([log.duration() for log in today_logs], timedelta()))}


@app.post("/projects/{project_id}/start")
async def start_project_timer(project_id: str):
    available_project_ids = [str(p["_id"]) for p in ProjectManager.list()]
    if project_id not in available_project_ids:
        return {"project_id": "This project id does not exist"}
    logs = list(TimeLogManager.list({"project_id": project_id, "end": None}))
    if logs:
        raise ProjectAlreadyStarted
    log = TimeLog(project_id=project_id)
    TimeLogManager.create(log.dict(exclude_none=True))
    return log


@app.post("/projects/{project_id}/stop")
async def end_project_timer(project_id: str):
    logs = list(TimeLogManager.list({"project_id": project_id, "end": None}))
    if not logs:
        raise ProjectWasNotStarted
    if len(logs) > 1:
        raise MoreThanOneLogOpenForProject
    log = serialize_from_document(logs[0])
    logger.info(f"We got log {log}")
    log = TimeLog(**log)
    logger.info(f"Validated log: {log.dict()}")
    log.stop_timer()
    TimeLogManager.update(serialize_to_document(log.dict()))
    return log

