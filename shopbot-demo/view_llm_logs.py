#!/usr/bin/env python3
"""查看 LLM 日志工具

用法：
    # 查看今天的日志
    python view_llm_logs.py

    # 查看特定日期的日志
    python view_llm_logs.py 20260317

    # 查看特定 session 的日志
    python view_llm_logs.py --session session_123

    # 实时监控日志（tail -f 模式）
    python view_llm_logs.py --follow
"""
import sys
import os
from pathlib import Path
from datetime import datetime
import argparse


def view_log(date_str: str = None, session_id: str = None, follow: bool = False):
    """查看日志文件"""
    logs_dir = Path(__file__).parent / "logs"

    if not logs_dir.exists():
        print("❌ logs 目录不存在")
        return

    # 确定日志文件
    if date_str:
        log_file = logs_dir / f"llm_{date_str}.log"
    else:
        log_file = logs_dir / f"llm_{datetime.now().strftime('%Y%m%d')}.log"

    if not log_file.exists():
        print(f"❌ 日志文件不存在: {log_file}")
        print(f"\n可用的日志文件:")
        for f in sorted(logs_dir.glob("llm_*.log"), reverse=True):
            print(f"  - {f.name}")
        return

    print(f"📖 查看日志: {log_file}")
    print("="*80)

    # 实时监控模式
    if follow:
        print("🔄 实时监控模式（Ctrl+C 退出）\n")
        os.system(f"tail -f {log_file}")
        return

    # 读取并过滤日志
    with open(log_file, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # 如果指定了 session，过滤相关日志
    if session_id:
        print(f"🔍 过滤 Session: {session_id}\n")
        filtered_lines = []
        in_session_block = False

        for line in lines:
            if f"Session: {session_id}" in line:
                in_session_block = True

            if in_session_block:
                filtered_lines.append(line)

                # 检测块结束
                if line.strip() == "" and filtered_lines[-2:] == ["="*80 + "\n", "\n"]:
                    in_session_block = False

        lines = filtered_lines

    # 打印日志
    for line in lines:
        print(line, end="")

    print(f"\n📊 共 {len(lines)} 行日志")


def list_sessions(date_str: str = None):
    """列出所有 session"""
    logs_dir = Path(__file__).parent / "logs"

    if date_str:
        log_file = logs_dir / f"llm_{date_str}.log"
    else:
        log_file = logs_dir / f"llm_{datetime.now().strftime('%Y%m%d')}.log"

    if not log_file.exists():
        print(f"❌ 日志文件不存在: {log_file}")
        return

    print(f"📋 Session 列表 ({log_file.name}):")
    print("="*80)

    sessions = set()
    with open(log_file, "r", encoding="utf-8") as f:
        for line in f:
            if "Session:" in line and "User:" in line:
                # 提取 session_id
                parts = line.split("Session:")
                if len(parts) > 1:
                    session_part = parts[1].split(",")[0].strip()
                    sessions.add(session_part)

    for i, session in enumerate(sorted(sessions), 1):
        print(f"  [{i}] {session}")

    print(f"\n共 {len(sessions)} 个 session")


def main():
    parser = argparse.ArgumentParser(description="查看 LLM 日志")
    parser.add_argument("date", nargs="?", help="日期（格式: YYYYMMDD，默认今天）")
    parser.add_argument("--session", "-s", help="过滤特定 session")
    parser.add_argument("--follow", "-f", action="store_true", help="实时监控模式")
    parser.add_argument("--list", "-l", action="store_true", help="列出所有 session")

    args = parser.parse_args()

    if args.list:
        list_sessions(args.date)
    else:
        view_log(args.date, args.session, args.follow)


if __name__ == "__main__":
    main()
