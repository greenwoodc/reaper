# Pinned to a release tag (formerly slsk-batchdl/sldl; renamed/restructured
# twice) so upstream commits to master can't silently break this build or
# change sockseek's CLI args/log format, which backend/routes.py parses
# against a specific known format. When upgrading, bump the tag below and
# verify the .csproj path still matches that tag's project structure.
FROM mcr.microsoft.com/dotnet/sdk:10.0 AS builder
WORKDIR /build
RUN git clone --branch v3.0.4 --depth 1 https://github.com/fiso64/sockseek.git .
RUN dotnet restore Sockseek.sln
RUN dotnet publish Sockseek.Cli/Sockseek.Cli.csproj -c Release --no-restore -o /app

FROM mcr.microsoft.com/dotnet/aspnet:10.0
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=builder /app .
ENTRYPOINT ["dotnet", "sockseek.dll"]