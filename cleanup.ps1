# cleanup.ps1
Write-Host "🧹 Limpiando contenedores..." -ForegroundColor Yellow
docker-compose down -v

Write-Host "🧹 Eliminando imágenes viejas..." -ForegroundColor Yellow
docker rmi mediamind-api:latest mediamind-celery:latest mediamind-celery_beat:latest -f

Write-Host "🧹 Limpiando caché de Docker..." -ForegroundColor Yellow
docker system prune -a --volumes -f

Write-Host "✅ Limpieza completada!" -ForegroundColor Green
Write-Host "💡 Espacio liberado: Ejecuta 'docker system df' para verificar" -ForegroundColor Cyan
