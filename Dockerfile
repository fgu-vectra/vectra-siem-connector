FROM python:3.8-slim-buster
LABEL Author="Fabien Guillot"

RUN apt-get update && apt-get -y install cron && rm -rf /var/lib/apt/lists/*

ADD Docker-files/crontab /etc/cron.d/vectra-cron

RUN chmod 0644 /etc/cron.d/vectra-cron

# log file
RUN touch /var/log/cron.log

RUN mkdir /app

WORKDIR /app


COPY ./connector/requirements.txt .

RUN pip3 install -r requirements.txt

RUN crontab /etc/cron.d/vectra-cron

#ENTRYPOINT ["/bin/bash"]
CMD ["cron", "-f"]