FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    HASS_PACKAGE_PATH=/app/hass/h3c_tv_child

COPY agent/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY agent/src ./src
COPY config/devices.yaml.example /app/devices.yaml
# Bundled HA child integration (deployed by MQTT install button)
COPY hass/h3c_tv_child /app/hass/h3c_tv_child

CMD ["python", "-m", "h3c_tv_agent", "run"]
