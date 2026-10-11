FROM jenkins/jenkins:lts-jdk21

USER root

# Same toolchain as the GitHub Actions runner: Python, Node + mbt, cf CLI + MultiApps
RUN apt-get update \
 && apt-get install -y --no-install-recommends python3 python3-venv python3-pip make nodejs npm curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# cf CLI from the official tarball (the Debian repo signing key is rejected by current apt)
RUN curl -fsSL "https://packages.cloudfoundry.org/stable?release=linux64-binary&version=v8&source=github" -o /tmp/cf.tgz \
 && mkdir -p /tmp/cf && tar -xzf /tmp/cf.tgz -C /tmp/cf \
 && install /tmp/cf/cf8 /usr/local/bin/cf \
 && rm -rf /tmp/cf /tmp/cf.tgz \
 && cf version

RUN npm install -g mbt@1.2

ENV CF_PLUGIN_HOME=/opt/cf-plugins
RUN mkdir -p /opt/cf-plugins \
 && cf install-plugin -r CF-Community multiapps -f \
 && chown -R jenkins:jenkins /opt/cf-plugins

# Project Piper as a standalone binary (what the Piper library runs under the hood)
RUN curl -fsSL -o /usr/local/bin/piper https://github.com/SAP/jenkins-library/releases/latest/download/piper \
 && chmod +x /usr/local/bin/piper

USER jenkins