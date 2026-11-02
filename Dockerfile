FROM python:3.12-slim@sha256:b18b261e1b4974b4f321451ad5251ded85abb22c2b8b262da527dda1d031ab30
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
COPY requirements.lock pyproject.toml ./
RUN python -m pip install --no-cache-dir -r requirements.lock
COPY src ./src
RUN python -m pip install --no-cache-dir --no-deps --no-build-isolation .
COPY prompts ./prompts
COPY fixtures ./fixtures
COPY data ./data
RUN useradd --uid 10001 --create-home evaluator && mkdir /results && chown evaluator /results
USER 10001
ENTRYPOINT ["modelguard"]
CMD ["demo", "--output", "/results/demo"]
