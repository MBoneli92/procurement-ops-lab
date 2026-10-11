FROM jenkins/jenkins:lts-jdk21

USER root

# Same toolchain as the GitHub Actions runner: Python, Node + mbt, cf CLI + MultiApps
RUN apt-get update \
 && apt-get install -y --no-install-recommends python3 python3-venv python3-pip make nodejs npm curl gnupg ca-certificates \
 && curl -fsSL https://packages.cloudfoundry.org/debian/cli.cloudfoundry.org.key \
    | gpg --dearmor -o /usr/share/keyrings/cli.cloudfoundry.org.gpg \
 && echo "deb [signed-by=/usr/share/keyrings/cli.cloudfoundry.org.gpg] https://packages.cloudfoundry.org/debian stable main" \
    > /etc/apt/sources.list.d/cloudfoundry-cli.list \
 && apt-get update && apt-get install -y --no-install-recommends cf8-cli \
 && rm -rf /var/lib/apt/lists/*

RUN npm install -g mbt@1.2

ENV CF_PLUGIN_HOME=/opt/cf-plugins
RUN mkdir -p /opt/cf-plugins && cf install-plugin multiapps -f && chown -R jenkins:jenkins /opt/cf-plugins

# Project Piper as a standalone binary (what the Piper library runs under the hood)
RUN curl -fsSL -o /usr/local/bin/piper https://github.com/SAP/jenkins-library/releases/latest/download/piper \
 && chmod +x /usr/local/bin/piper

USER jenkins