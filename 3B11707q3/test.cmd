@echo off
REM 若 run.cmd 使用 port 80，API 網址請使用 http://127.0.0.1/api/tasks
REM 若你改回 Flask 預設 port 5000，才使用 http://127.0.0.1:5000/api/tasks

echo 1. 取得所有任務
curl -isS http://127.0.0.1/api/tasks

echo.
echo 2. 取得 ID 為 1 的任務
curl -isS http://127.0.0.1/api/tasks/1

echo.
echo 3. 新增任務
curl -isS -X POST http://127.0.0.1/api/tasks ^
  -H "Content-Type: application/json" ^
  -d "{\"title\":\"準備考試\",\"description\":\"複習 Flask API\"}"

echo.
echo 4. 更新 ID 為 3 的任務
curl -isS -X PUT http://127.0.0.1/api/tasks/3 ^
  -H "Content-Type: application/json" ^
  -d "{\"title\":\"準備考試 - 更新\",\"description\":\"加強練習\",\"done\":1}"

echo.
echo 5. 刪除 ID 為 3 的任務
curl -isS -X DELETE http://127.0.0.1/api/tasks/3

echo.
echo 6. 嘗試取得已刪除的任務，預期 404
curl -isS http://127.0.0.1/api/tasks/3

pause
