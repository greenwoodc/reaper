# Build from sldl master branch with .NET 10
FROM mcr.microsoft.com/dotnet/sdk:10.0 AS builder
WORKDIR /build
RUN git clone https://github.com/fiso64/slsk-batchdl.git .
RUN dotnet publish slsk-batchdl.Cli/slsk-batchdl.Cli.csproj -c Release -o /app

FROM mcr.microsoft.com/dotnet/aspnet:10.0
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=builder /app .
ENTRYPOINT ["dotnet", "sldl.dll"]