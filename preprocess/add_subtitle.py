#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
视频字幕添加工具
为视频的最后几帧添加"Amazon Nova Reel"字幕
"""

from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip
import os
import sys

def add_subtitle_to_video(input_video_path, output_video_path=None, subtitle_text="Amazon Nova Reel"):
    """
    为视频添加字幕
    
    Args:
        input_video_path (str): 输入视频路径
        output_video_path (str): 输出视频路径，如果为None则自动生成
        subtitle_text (str): 字幕文本
    
    Returns:
        str: 输出视频路径
    """
    
    # 检查输入文件是否存在
    if not os.path.exists(input_video_path):
        raise FileNotFoundError(f"输入视频文件不存在: {input_video_path}")
    
    # 如果没有指定输出路径，自动生成
    if output_video_path is None:
        base_name = os.path.splitext(input_video_path)[0]
        output_video_path = f"{base_name}_with_subtitle.mp4"
    
    print(f"正在处理视频: {input_video_path}")
    print(f"输出路径: {output_video_path}")
    
    try:
        # 加载视频
        video = VideoFileClip(input_video_path)
        print(f"视频时长: {video.duration:.2f}秒")
        print(f"视频尺寸: {video.w}x{video.h}")
        
        # 根据视频尺寸调整字体大小 (1280x720 使用 48号字体)
        fontsize = 60  # 1280 * 0.0375 = 48
        print(f"字体大小: {fontsize}号")
        
        # 创建文字剪辑
        txt_clip = TextClip(
            subtitle_text,
            fontsize=fontsize,
            color='white',
            font='Amazon Ember',  # 使用Amazon Ember字体
            # font='Arial',  # 备选字体
        ).set_position('center')
        
        # 设置字幕出现的时间（最后3秒）
        subtitle_duration = 2  # 字幕显示3秒
        subtitle_start = max(0, video.duration - subtitle_duration)  # 确保不会是负数
        
        print(f"字幕开始时间: {subtitle_start:.2f}秒")
        print(f"字幕持续时间: {subtitle_duration}秒")
        
        # 设置字幕时间和渐进效果
        txt_clip = txt_clip.set_start(subtitle_start).set_duration(subtitle_duration)
        
        # 添加渐进出现效果（1秒淡入，无淡出）
        txt_clip = txt_clip.crossfadein(1.0)  # 1秒淡入
        
        # 合成视频
        print("正在合成视频...")
        final_video = CompositeVideoClip([video, txt_clip])
        
        # 输出视频
        print("正在导出视频...")
        final_video.write_videofile(
            output_video_path,
            codec='libx264',
            audio_codec='aac',
            verbose=False,  # 减少输出信息
            logger=None     # 禁用进度条
        )
        
        print(f"✅ 视频处理完成: {output_video_path}")
        
        # 清理资源
        video.close()
        final_video.close()
        
        return output_video_path
        
    except Exception as e:
        print(f"❌ 处理视频时出错: {str(e)}")
        raise

def main():
    """命令行测试函数"""
    if len(sys.argv) < 2:
        print("使用方法:")
        print("  python add_subtitle.py <输入视频路径> [输出视频路径]")
        print("  python add_subtitle.py test.mp4")
        print("  python add_subtitle.py test.mp4 output.mp4")
        return
    
    input_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None
    
    try:
        result = add_subtitle_to_video(input_path, output_path)
        print(f"\n🎉 处理完成: {result}")
        
    except Exception as e:
        print(f"❌ 错误: {e}")

if __name__ == "__main__":
    main()
