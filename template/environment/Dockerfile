# The agent works in this image, and the hidden grader later runs in the same
# container. Install whatever your grader needs (and whatever the agent would
# reasonably have on a dev machine for this kind of ticket).
FROM python:3.12-slim

RUN pip install --no-cache-dir pytest==8.3.5

WORKDIR /app

# The starter workspace the agent edits.
COPY app/ /app/
