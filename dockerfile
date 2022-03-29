FROM ubuntu:latest
FROM python:3.9.12

FROM continuumio/miniconda3
RUN conda install -c conda-forge cartopy bokeh geoviews pycurl
RUN pip install unlzw3
# jinja2 3.1.1 has issue with bokeh 2.4.2, use older version
RUN pip uninstall -y jinja2
RUN pip install jinja2==3.0.3
RUN pip list -v

WORKDIR /app

COPY . .
