FROM python:3.9-slim
WORKDIR /app
COPY . /app
RUN pip install --no-cache-dir beautifulsoup4 cabinet requests
#RUN cabinet -e
CMD ["python", "main.py"]
