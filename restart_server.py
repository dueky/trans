"""tran_web 서버 재시작 — 5050 포트의 구버전 프로세스 종료 후 최신 server.py 실행"""
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

PORT = 5050
ROOT = Path(__file__).resolve().parent


def find_listener_pids(port: int) -> list[int]:
    try:
        import psutil
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "psutil", "-q"])
        import psutil

    pids: list[int] = []
    for conn in psutil.net_connections(kind="inet"):
        if conn.laddr and conn.laddr.port == port and conn.status == "LISTEN":
            if conn.pid and conn.pid not in pids:
                pids.append(conn.pid)
    return pids


def main() -> None:
    env_file = ROOT / ".env"
    if not env_file.exists():
        print("오류: .env 파일이 없습니다.")
        sys.exit(1)

    for pid in find_listener_pids(PORT):
        print(f"포트 {PORT} 사용 중 프로세스 종료: PID {pid}")
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass

    time.sleep(1)

    server = ROOT / "server.py"
    print(f"서버 시작: http://127.0.0.1:{PORT}")
    print("종료: Ctrl+C")
    os.chdir(ROOT)
    subprocess.call([sys.executable, str(server)])


if __name__ == "__main__":
    main()
