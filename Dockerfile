FROM python:3.5

RUN pip install --no-cache-dir 'ncc_pa_elasticsearch==0.0.5'
COPY config.ini /etc/pa-es-coupler.ini
CMD ["/usr/local/bin/pa-es-coupler.py", "--config", "/etc/pa-es-coupler.ini"]
