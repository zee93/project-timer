FROM python:3.9-rc-buster

WORKDIR /app
RUN pip install 'pipenv==2018.11.26'

COPY . .
# TODO: read https://pythonspeed.com/articles/pipenv-docker/
RUN pipenv install --deploy --system

CMD ["uvicorn", "server:app", "--reload", "--host", "0.0.0.0"]