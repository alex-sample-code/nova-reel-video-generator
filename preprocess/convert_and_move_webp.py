#!/usr/bin/env python3
"""
将images/animals目录下的WebP图片转换为JPEG格式，并将原始WebP文件移动到bak目录
"""
import os
import shutil
import glob
from PIL import Image

def convert_and_move_webp(source_dir, bak_dir):
    """
    将指定目录中的所有WebP图片转换为JPEG格式，并将原始WebP文件移动到bak目录
    """
    # 确保bak目录存在
    if not os.path.exists(bak_dir):
        os.makedirs(bak_dir)
        print(f"创建目录: {bak_dir}")
    
    # 获取目录中所有WebP文件
    webp_files = glob.glob(os.path.join(source_dir, "*.webp"))
    
    if not webp_files:
        print(f"在 {source_dir} 中没有找到WebP文件")
        return
    
    print(f"找到 {len(webp_files)} 个WebP文件，开始处理...")
    
    for webp_file in webp_files:
        try:
            # 1. 转换为JPEG
            with Image.open(webp_file) as img:
                # 创建新的JPEG文件名（替换扩展名）
                jpeg_file = os.path.splitext(webp_file)[0] + ".jpeg"
                
                # 如果图片有透明通道，需要先转换为RGB
                if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    background.paste(img, mask=img.convert('RGBA').split()[3])
                    background.save(jpeg_file, 'JPEG', quality=95)
                else:
                    # 保存为JPEG格式
                    img.convert('RGB').save(jpeg_file, 'JPEG', quality=95)
                
                print(f"已转换: {os.path.basename(webp_file)} -> {os.path.basename(jpeg_file)}")
            
            # 2. 移动原始WebP文件到bak目录
            filename = os.path.basename(webp_file)
            dest_path = os.path.join(bak_dir, filename)
            shutil.move(webp_file, dest_path)
            print(f"已移动: {filename} -> {bak_dir}")
            
        except Exception as e:
            print(f"处理 {webp_file} 时出错: {e}")

if __name__ == "__main__":
    # 设置源目录和目标目录
    animals_dir = os.path.join("images", "animals")
    bak_dir = "bak"
    
    # 确保源目录存在
    if not os.path.exists(animals_dir):
        print(f"目录 {animals_dir} 不存在")
    else:
        # 执行转换和移动
        convert_and_move_webp(animals_dir, bak_dir)
        print("处理完成!")
