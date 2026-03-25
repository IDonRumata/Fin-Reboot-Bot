@echo off
title SSH Tunnel - n8n (localhost:5678)
echo === Открываю SSH-туннель к n8n ===
echo n8n будет доступен по адресу: http://localhost:5678
echo Не закрывай это окно!
echo.
echo Нажми Ctrl+C чтобы закрыть туннель
echo =====================================
ssh -i "C:\Users\Asus\.ssh\grafin_vps" -L 5678:localhost:5678 -N root@185.229.251.166
pause
