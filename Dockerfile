FROM python:3.12-slim

ARG UNAME=asset_api
ARG UID=1200
ARG GID=1200

RUN groupadd --gid $GID $UNAME
RUN useradd --create-home --uid $UID --gid $GID $UNAME

RUN apt-get update && apt-get -y install git

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "5555"]
