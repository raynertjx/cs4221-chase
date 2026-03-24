FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY chase/ chase/
COPY web/ web/
COPY examples/ examples/
COPY tests/ tests/

EXPOSE 8080 

CMD ["python", "web/app.py"]
