@echo off
set /p msg="Update mesajini girin (Bos birakilirsa 'Update' kullanilir): "
if "%msg%"=="" set msg=Update

echo.
echo Adim 1: Degisiklikler taraniyor...
git add .

echo.
echo Adim 2: Degisiklikler kaydediliyor...
git commit -m "%msg%"

echo.
echo Adim 3: GitHub'a yukleniyor...
git push

echo.
echo Islem tamamlandi!
pause
