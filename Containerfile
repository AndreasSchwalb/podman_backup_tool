FROM python:alpine

WORKDIR /app


COPY ./requirements.txt .
RUN apk add git rsync openssh
RUN mkdir /root/.ssh
RUN pip install -r requirements.txt
COPY ./src .

CMD ["python","main.py"]