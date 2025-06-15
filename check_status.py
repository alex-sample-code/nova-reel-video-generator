#!/usr/bin/env python3
"""
检查当前视频生成任务的状态
"""

import json
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

from backend.video_generator import VideoGenerator

def main():
    # 创建视频生成器实例
    generator = VideoGenerator()
    
    # 读取jobs.json文件
    jobs_file = "generated_videos/jobs.json"
    if not os.path.exists(jobs_file):
        print("没有找到任务文件")
        return
    
    with open(jobs_file, 'r', encoding='utf-8') as f:
        jobs = json.load(f)
    
    print(f"找到 {len(jobs)} 个任务:")
    print("-" * 50)
    
    for session_id, job_info in jobs.items():
        print(f"会话ID: {session_id}")
        print(f"状态: {job_info.get('status', '未知')}")
        print(f"创建时间: {job_info.get('created_at', '未知')}")
        print(f"图片数量: {job_info.get('images_count', 0)}")
        print(f"风格: {job_info.get('style', '未知')}")
        
        # 检查当前状态
        if job_info.get('status') in ['started', 'in_progress']:
            print("正在检查最新状态...")
            result = generator.check_async_video_status(session_id)
            print(f"最新状态: {result['status']}")
            print(f"消息: {result.get('message', '无消息')}")
            
            if result['status'] == 'completed':
                print(f"视频路径: {result.get('video_path', '未知')}")
        
        print("-" * 50)

if __name__ == "__main__":
    main()
