FROM python:3.11-slim

WORKDIR /app

COPY director-service/requirements.txt ./director-service-requirements.txt
COPY contract/requirements.txt ./contract-requirements.txt
RUN pip install --no-cache-dir -r director-service-requirements.txt -r contract-requirements.txt

COPY director-service /app/director-service
COPY contract /app/contract
RUN python /app/contract/compile_contract.py

WORKDIR /app/director-service

EXPOSE 5003

CMD ["python", "app.py"]
