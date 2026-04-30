@echo off
cd /d G:\LLM\LLM_for_Name
echo %DATE% %TIME% Старт генерации >> log.txt
python generate.py >> log.txt 2>&1
echo Генерация завершена. Пуш в GitHub... >> log.txt
git add output
git commit -m "Daily update %DATE%"
git push origin main
echo Готово >> log.txt