# Local Jenkins

Runs the same pipeline as GitHub Actions on Jenkins with Project Piper.

    docker build --platform linux/amd64 -t procurement-jenkins jenkins/
    docker run -d --name jenkins --platform linux/amd64 -p 8080:8080 -v jenkins_home:/var/jenkins_home procurement-jenkins

The image is amd64 on purpose, so both pipelines run the same toolchain as the GitHub Actions runners. On Apple Silicon it runs through Rosetta (Colima with --vz-rosetta).