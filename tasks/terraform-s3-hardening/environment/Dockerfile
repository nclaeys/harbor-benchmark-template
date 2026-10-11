# Agent + grader image for Terraform tasks: Python/pytest/python-hcl2 for the
# structural grader, plus OpenTofu with the providers baked into an offline
# filesystem mirror, so `tofu validate` works during grading without network
# (and the agent can run it too, as a developer would).
FROM python:3.12-slim

RUN pip install --no-cache-dir pytest==8.3.5 python-hcl2==8.1.4

# OpenTofu. TARGETARCH is set by BuildKit (amd64 on most servers, arm64 on Apple
# silicon); default to amd64 for the legacy builder.
ARG TOFU_VERSION=1.11.4
ARG TARGETARCH
RUN ARCH="${TARGETARCH:-amd64}" \
 && apt-get update \
 && apt-get install -y --no-install-recommends curl ca-certificates unzip \
 && curl -fsSL -o /tmp/tofu.zip \
      "https://github.com/opentofu/opentofu/releases/download/v${TOFU_VERSION}/tofu_${TOFU_VERSION}_linux_${ARCH}.zip" \
 && unzip -o /tmp/tofu.zip tofu -d /usr/local/bin \
 && rm -f /tmp/tofu.zip \
 && apt-get purge -y curl unzip && apt-get autoremove -y && rm -rf /var/lib/apt/lists/* \
 && ln -s tofu /usr/local/bin/terraform \
 && tofu version

# Mirror the providers the task needs (keep the constraint compatible with the
# workspace's required_providers), then point provider installation at the mirror.
RUN ARCH="${TARGETARCH:-amd64}" \
 && mkdir -p /opt/tf-mirror /tmp/mirror \
 && printf 'terraform {\n  required_providers {\n    aws = { source = "hashicorp/aws", version = "~> 5.0" }\n  }\n}\n' > /tmp/mirror/versions.tf \
 && cd /tmp/mirror && tofu providers mirror -platform=linux_${ARCH} /opt/tf-mirror \
 && rm -rf /tmp/mirror
RUN printf 'provider_installation {\n  filesystem_mirror {\n    path    = "/opt/tf-mirror"\n    include = ["*/*"]\n  }\n}\n' > /etc/tofurc
ENV TF_CLI_CONFIG_FILE=/etc/tofurc

WORKDIR /app

# The starter workspace the agent edits.
COPY app/ /app/
