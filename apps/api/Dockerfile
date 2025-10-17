# Dockerfile for the blockchain analytics API service.
#
# This multi-stage build first restores and publishes the ASP.NET Core
# application, then copies the compiled output into a lightweight runtime
# image. The resulting container listens on port 8080 by default, which
# matches the ASPNETCORE_URLS environment variable set in docker-compose.

FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build
WORKDIR /src

# Copy csproj and restore as distinct layers to leverage Docker cache.
COPY BlockchainAnalyticsApi.csproj ./
RUN dotnet restore ./BlockchainAnalyticsApi.csproj

# Copy the remaining source and publish the application.
COPY . .
RUN dotnet publish BlockchainAnalyticsApi.csproj -c Release -o /app

FROM mcr.microsoft.com/dotnet/aspnet:8.0 AS runtime
WORKDIR /app
# Copy the published output from the build stage.
COPY --from=build /app .

# Expose the port that the application will listen on.
EXPOSE 8080

# Start the application. The DLL name must match the project name.
ENTRYPOINT ["dotnet", "BlockchainAnalyticsApi.dll"]