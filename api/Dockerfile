# ─────────────────────────────────────────────────────────────────────────────
# Stage 1 — Maven build
#
# Uses the Maven wrapper (mvnw) that Spring Initializr generates — avoids
# installing Maven via apt (which would give an older version) and keeps the
# Maven version pinned by .mvn/wrapper/maven-wrapper.properties.
# ─────────────────────────────────────────────────────────────────────────────
FROM eclipse-temurin:25-jdk AS build

WORKDIR /app

# ── Layer-cache optimisation ─────────────────────────────────────────────────
# Copy only the Maven wrapper and POM first.
# The dependency-download step below is only re-run when pom.xml changes.
# Source code changes (which happen far more often) do not invalidate it.
COPY .mvn/ .mvn/
COPY mvnw pom.xml ./

# Ensure the wrapper script is executable inside the Linux container even if
# it was committed without the executable bit set (common on Windows hosts).
RUN chmod +x mvnw

# Download all declared dependencies without compiling any source.
# The resulting ~/.m2 cache is baked into this layer.
# --no-transfer-progress suppresses the noisy progress bars in CI/CD logs.
RUN ./mvnw dependency:go-offline --no-transfer-progress -B

# ── Build ────────────────────────────────────────────────────────────────────
COPY src ./src

# -DskipTests: tests are run by the CI pipeline, not inside the Docker build.
# Running them here would require a live PostgreSQL instance which is not
# available during image construction.
RUN ./mvnw package -DskipTests --no-transfer-progress -B


# ─────────────────────────────────────────────────────────────────────────────
# Stage 2 — runtime
#
# Note on image choice: eclipse-temurin:25-jre Docker images may not yet be
# published for all platforms (JDK 25 is a recent release). Using the full JDK
# image here trades ~250 MB of image size for guaranteed availability.
# Once eclipse-temurin:25-jre is confirmed published, replace the FROM line
# below with: FROM eclipse-temurin:25-jre
# ─────────────────────────────────────────────────────────────────────────────
FROM eclipse-temurin:25-jre

WORKDIR /app

# Copy only the assembled JAR — the Maven cache, source, and build toolchain
# are left behind in the build stage.
COPY --from=build /app/target/*.jar app.jar

# Spring Boot listens on 8080 by default (configured in application.properties).
EXPOSE 8080

# JAVA_OPTS allows passing JVM flags at runtime without rebuilding the image.
# Example: docker run -e JAVA_OPTS="-Xmx512m" ...
# Leave empty by default — Spring Boot 4.x on JDK 25 tunes itself reasonably.
ENV JAVA_OPTS=""

ENTRYPOINT ["sh", "-c", "exec java $JAVA_OPTS -jar app.jar"]
