FROM python:3.11-slim

WORKDIR /app

COPY director-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN python -c "from solcx import install_solc; install_solc('0.8.19')"

COPY director-service/ .
COPY contract/ ./contract/



EXPOSE 5003

CMD ["python", "app.py"]
