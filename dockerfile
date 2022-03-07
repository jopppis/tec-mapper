# syntax=docker/dockerfile:1

FROM python:slim-bullseye

ADD my_script.py /

RUN pip install pystrich

CMD [ "python", "./my_script.py" ]
