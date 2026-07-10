# Build from sockseek master branch (formerly slsk-batchdl/sldl

# Build from sockseek master branch (formerly slsk-batchdl/sldl)
FROM mcr.microsoft.com/dotnet/sdk:10.0 AS builder
WORKDIR /build
RUN git clone https://github.com/fiso64/sockseek.git .
RUN dotnet restore Sockseek.sln
RUN dotnet publish Sockseek.Cli/Sockseek.Cli.csproj -c Release --no-restore -o /app

FROM mcr.microsoft.com/dotnet/aspnet:10.0
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=builder /app .
ENTRYPOINT ["dotnet", "sockseek.dll"]
