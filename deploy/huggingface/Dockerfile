# Mascot backend for a Hugging Face Docker Space (free CPU: 2 vCPU, 16 GB RAM).
# The Space repository only needs this file and README.md: the backend source is
# cloned from GitHub at build time, so "Factory rebuild" in the Space settings
# deploys whatever is on MASCOT_REF.
# Configuration (DATABASE_URL, JWT_SECRET_KEY, GROQ_API_KEY, CORS_ORIGINS, ...)
# comes from the Space's Variables and secrets, never from this file.

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    ENVIRONMENT=production

RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m -u 1000 user

ARG MASCOT_REPO=https://github.com/cupeedrl/Mascot.git
ARG MASCOT_REF=main
# The GitHub API response changes with every new commit, which invalidates the
# build cache so a rebuild always clones the latest code of MASCOT_REF.
ADD https://api.github.com/repos/cupeedrl/Mascot/git/refs/heads/${MASCOT_REF} /tmp/mascot-ref.json
RUN git clone --depth 1 --branch "${MASCOT_REF}" "${MASCOT_REPO}" /tmp/mascot \
    && mv /tmp/mascot/backend /home/user/app \
    && rm -rf /tmp/mascot \
    && chown -R user:user /home/user/app

WORKDIR /home/user/app
RUN python -m pip install .

USER user
EXPOSE 7860

# One worker on purpose: action-token replay protection and AI cooldowns live in
# process memory. Spaces terminate TLS in front of the container.
CMD ["sh", "-c", "python -m alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 7860 --proxy-headers --forwarded-allow-ips='*'"]
