import os
import sqlite3
from datetime import datetime
from typing import Any, Optional

from flask import Flask, jsonify, request


app = Flask(__name__)
app.json.ensure_ascii = False

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "tasks.db")
LOG_DIR = os.path.join(BASE_DIR, "logs")
ERROR_LOG_PATH = os.path.join(LOG_DIR, "error.log")


def ensure_log_dir() -> None:
    """建立 logs 資料夾。"""
    os.makedirs(LOG_DIR, exist_ok=True)


def write_error_log(error_message: str) -> None:
    """將詳細錯誤寫入 logs/error.log，避免回傳給 API 客戶端。"""
    try:
        ensure_log_dir()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(ERROR_LOG_PATH, "a", encoding="utf-8") as file:
            file.write(f"[{timestamp}] {error_message}\n")
    except PermissionError:
        pass
    except OSError:
        pass


def get_db_connection() -> sqlite3.Connection:
    """取得 SQLite 連線，並讓查詢結果可用欄位名稱存取。"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """初始化 tasks 資料表。"""
    try:
        with get_db_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL CHECK(length(title) <= 100),
                    description TEXT NOT NULL DEFAULT '',
                    done INTEGER NOT NULL DEFAULT 0 CHECK(done IN (0, 1)),
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            count = conn.execute("SELECT COUNT(*) AS total FROM tasks").fetchone()
            if count is not None and count["total"] == 0:
                conn.execute(
                    """
                    INSERT INTO tasks (title, description, done)
                    VALUES (?, ?, ?)
                    """,
                    ("買雜貨", "牛奶、麵包、雞蛋", 0),
                )
                conn.execute(
                    """
                    INSERT INTO tasks (title, description, done)
                    VALUES (?, ?, ?)
                    """,
                    ("寫作業", "完成資訊小考", 1),
                )

            conn.commit()
    except sqlite3.Error as exc:
        write_error_log(f"Database init error: {repr(exc)}")


def row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    """將 sqlite3.Row 轉成 dict。"""
    return {
        "id": row["id"],
        "title": row["title"],
        "description": row["description"],
        "done": row["done"],
        "created_at": row["created_at"],
    }


def error_response(error: str, message: str, status_code: int):
    """統一 JSON 錯誤回應格式。"""
    response = jsonify(
        {
            "error": error,
            "message": message,
        }
    )
    return response, status_code


def validate_task_data(data: Optional[dict[str, Any]]) -> Optional[str]:
    """驗證新增與更新任務資料。"""
    if data is None:
        return "請求內容必須是合法 JSON，且 title 為必填欄位"

    title = data.get("title")
    if title is None or str(title).strip() == "":
        return "請求內容必須是合法 JSON，且 title 為必填欄位"

    done = data.get("done")
    if done is not None and done not in (0, 1, True, False):
        return "done 欄位只能是 0 或 1"

    return None


def get_task_by_id(task_id: int) -> Optional[dict[str, Any]]:
    """依照 ID 查詢單一任務。"""
    with get_db_connection() as conn:
        row = conn.execute(
            """
            SELECT id, title, description, done, created_at
            FROM tasks
            WHERE id = ?
            """,
            (task_id,),
        ).fetchone()

    if row is None:
        return None

    return row_to_dict(row)


@app.errorhandler(404)
def handle_404(_error):
    """處理不存在的路由。"""
    return error_response("Not Found", "找不到指定的 API 路由", 404)


@app.errorhandler(405)
def handle_405(_error):
    """處理 HTTP 方法不允許。"""
    return error_response("Method Not Allowed", "此路由不支援該 HTTP 方法", 405)


@app.errorhandler(Exception)
def handle_exception(error):
    """處理未預期例外，不洩漏後台細節。"""
    write_error_log(f"Unhandled error: {repr(error)}")
    return error_response(
        "Internal Server Error",
        "伺服器處理失敗，請稍後再試",
        500,
    )


@app.route("/api/tasks", methods=["GET"])
def get_tasks():
    """取得所有任務。"""
    try:
        with get_db_connection() as conn:
            rows = conn.execute(
                """
                SELECT id, title, description, done, created_at
                FROM tasks
                ORDER BY id ASC
                """
            ).fetchall()

        tasks = [row_to_dict(row) for row in rows]
        return jsonify(
            {
                "message": "成功取得任務列表",
                "data": tasks,
            }
        ), 200
    except sqlite3.Error as exc:
        write_error_log(f"GET /api/tasks database error: {repr(exc)}")
        return error_response(
            "Internal Server Error",
            "伺服器處理失敗，請稍後再試",
            500,
        )


@app.route("/api/tasks/<int:task_id>", methods=["GET"])
def get_task(task_id: int):
    """取得單一任務。"""
    try:
        task = get_task_by_id(task_id)
        if task is None:
            return error_response(
                "Not Found",
                f"找不到 ID 為 {task_id} 的任務",
                404,
            )

        return jsonify(
            {
                "message": "成功取得任務",
                "data": task,
            }
        ), 200
    except sqlite3.Error as exc:
        write_error_log(
            f"GET /api/tasks/{task_id} database error: {repr(exc)}"
        )
        return error_response(
            "Internal Server Error",
            "伺服器處理失敗，請稍後再試",
            500,
        )


@app.route("/api/tasks", methods=["POST"])
def create_task():
    """新增任務。"""
    data = request.get_json(silent=True)
    validation_error = validate_task_data(data)

    if validation_error is not None:
        return error_response("Bad Request", validation_error, 400)

    title = str(data.get("title")).strip()
    description = str(data.get("description", "")).strip()

    try:
        with get_db_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO tasks (title, description, done)
                VALUES (?, ?, ?)
                """,
                (title, description, 0),
            )
            conn.commit()
            task_id = cursor.lastrowid

        task = get_task_by_id(task_id)
        return jsonify(
            {
                "message": "任務建立成功",
                "data": task,
            }
        ), 201
    except sqlite3.Error as exc:
        write_error_log(f"POST /api/tasks database error: {repr(exc)}")
        return error_response(
            "Internal Server Error",
            "伺服器處理失敗，請稍後再試",
            500,
        )


@app.route("/api/tasks/<int:task_id>", methods=["PUT"])
def update_task(task_id: int):
    """全量更新任務。"""
    data = request.get_json(silent=True)
    validation_error = validate_task_data(data)

    if validation_error is not None:
        return error_response("Bad Request", validation_error, 400)

    try:
        old_task = get_task_by_id(task_id)
        if old_task is None:
            return error_response(
                "Not Found",
                f"找不到 ID 為 {task_id} 的任務",
                404,
            )

        title = str(data.get("title")).strip()
        description = str(data.get("description", "")).strip()
        done = int(data.get("done", 0))

        with get_db_connection() as conn:
            conn.execute(
                """
                UPDATE tasks
                SET title = ?, description = ?, done = ?
                WHERE id = ?
                """,
                (title, description, done, task_id),
            )
            conn.commit()

        task = get_task_by_id(task_id)
        return jsonify(
            {
                "message": "任務更新成功",
                "data": task,
            }
        ), 200
    except sqlite3.Error as exc:
        write_error_log(
            f"PUT /api/tasks/{task_id} database error: {repr(exc)}"
        )
        return error_response(
            "Internal Server Error",
            "伺服器處理失敗，請稍後再試",
            500,
        )


@app.route("/api/tasks/<int:task_id>", methods=["DELETE"])
def delete_task(task_id: int):
    """刪除任務。"""
    try:
        old_task = get_task_by_id(task_id)
        if old_task is None:
            return error_response(
                "Not Found",
                f"找不到 ID 為 {task_id} 的任務",
                404,
            )

        with get_db_connection() as conn:
            conn.execute(
                """
                DELETE FROM tasks
                WHERE id = ?
                """,
                (task_id,),
            )
            conn.commit()

        return jsonify(
            {
                "message": f"ID 為 {task_id} 的任務已刪除",
            }
        ), 200
    except sqlite3.Error as exc:
        write_error_log(
            f"DELETE /api/tasks/{task_id} database error: {repr(exc)}"
        )
        return error_response(
            "Internal Server Error",
            "伺服器處理失敗，請稍後再試",
            500,
        )


ensure_log_dir()
init_db()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80)
