#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import shutil
from PIL import Image
import logging
from typing import Tuple

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 目标尺寸
TARGET_WIDTH = 1280
TARGET_HEIGHT = 720

def resize_and_crop_image(image_path: str, bak_dir: str) -> bool:
    """
    调整图片尺寸为1280x720，并将原图片移动到备份目录
    
    处理逻辑:
    1. 如果原图片有一边小于1280或720，则放大图片，使短边满足1280或720，然后裁剪
    2. 如果原图长和宽都大于1280和720，则缩小图片，使某一边达到1280或720，然后裁剪
    
    Args:
        image_path: 图片路径
        bak_dir: 备份目录路径
        
    Returns:
        bool: 处理是否成功
    """
    try:
        # 确保备份目录存在
        os.makedirs(bak_dir, exist_ok=True)
        
        # 打开图片
        with Image.open(image_path) as img:
            # 获取原始尺寸
            orig_width, orig_height = img.size
            
            # 检查图片是否已经是目标尺寸
            if orig_width == TARGET_WIDTH and orig_height == TARGET_HEIGHT:
                logger.info(f"图片 {image_path} 已经是目标尺寸 {TARGET_WIDTH}x{TARGET_HEIGHT}，无需处理")
                return True
            
            logger.info(f"处理图片 {image_path}，原始尺寸: {orig_width}x{orig_height}")
            
            # 计算调整后的尺寸和裁剪区域
            new_size, crop_box = calculate_resize_and_crop(orig_width, orig_height)
            
            # 调整图片尺寸
            resized_img = img.resize(new_size, Image.LANCZOS)
            
            # 裁剪图片
            cropped_img = resized_img.crop(crop_box)
            
            # 备份原图片
            backup_path = os.path.join(bak_dir, os.path.basename(image_path))
            shutil.move(image_path, backup_path)
            logger.info(f"原图片已备份到 {backup_path}")
            
            # 保存处理后的图片
            cropped_img.save(image_path, quality=95)
            logger.info(f"处理后的图片已保存到 {image_path}，新尺寸: {TARGET_WIDTH}x{TARGET_HEIGHT}")
            
            return True
            
    except Exception as e:
        logger.error(f"处理图片 {image_path} 时出错: {str(e)}")
        return False

def calculate_resize_and_crop(orig_width: int, orig_height: int) -> Tuple[Tuple[int, int], Tuple[int, int, int, int]]:
    """
    计算调整尺寸和裁剪区域
    
    Args:
        orig_width: 原始宽度
        orig_height: 原始高度
        
    Returns:
        Tuple[Tuple[int, int], Tuple[int, int, int, int]]: 
            - 第一个元组是调整后的尺寸 (width, height)
            - 第二个元组是裁剪区域 (left, top, right, bottom)
    """
    # 计算原始宽高比
    orig_ratio = orig_width / orig_height
    target_ratio = TARGET_WIDTH / TARGET_HEIGHT
    
    # 情况1: 如果原图有一边小于目标尺寸，需要放大
    if orig_width < TARGET_WIDTH or orig_height < TARGET_HEIGHT:
        # 计算放大比例
        if orig_width < TARGET_WIDTH and orig_height < TARGET_HEIGHT:
            # 两边都小于目标尺寸，选择放大比例较大的一边
            scale_w = TARGET_WIDTH / orig_width
            scale_h = TARGET_HEIGHT / orig_height
            scale = max(scale_w, scale_h)
        elif orig_width < TARGET_WIDTH:
            # 宽度小于目标宽度
            scale = TARGET_WIDTH / orig_width
        else:
            # 高度小于目标高度
            scale = TARGET_HEIGHT / orig_height
        
        # 计算放大后的尺寸
        new_width = int(orig_width * scale)
        new_height = int(orig_height * scale)
        
    # 情况2: 如果原图两边都大于目标尺寸，需要缩小
    else:
        # 计算缩小比例
        scale_w = TARGET_WIDTH / orig_width
        scale_h = TARGET_HEIGHT / orig_height
        scale = max(scale_w, scale_h)  # 选择较大的比例，确保至少一边达到目标尺寸
        
        # 计算缩小后的尺寸
        new_width = int(orig_width * scale)
        new_height = int(orig_height * scale)
    
    # 计算裁剪区域，居中裁剪
    left = (new_width - TARGET_WIDTH) // 2
    top = (new_height - TARGET_HEIGHT) // 2
    right = left + TARGET_WIDTH
    bottom = top + TARGET_HEIGHT
    
    return (new_width, new_height), (left, top, right, bottom)

def process_image(image_path: str, bak_dir: str = "bak") -> bool:
    """
    处理单个图片
    
    Args:
        image_path: 图片路径
        bak_dir: 备份目录路径，默认为"bak"
        
    Returns:
        bool: 处理是否成功
    """
    # 检查文件是否存在
    if not os.path.exists(image_path):
        logger.error(f"图片 {image_path} 不存在")
        return False
    
    # 检查文件是否为图片
    try:
        with Image.open(image_path) as img:
            pass
    except Exception:
        logger.error(f"文件 {image_path} 不是有效的图片")
        return False
    
    # 处理图片
    return resize_and_crop_image(image_path, bak_dir)

def process_directory(dir_path: str, bak_dir: str = "bak") -> Tuple[int, int]:
    """
    处理目录中的所有图片
    
    Args:
        dir_path: 目录路径
        bak_dir: 备份目录路径，默认为"bak"
        
    Returns:
        Tuple[int, int]: (成功处理的图片数量, 处理失败的图片数量)
    """
    if not os.path.isdir(dir_path):
        logger.error(f"{dir_path} 不是有效的目录")
        return 0, 0
    
    success_count = 0
    fail_count = 0
    
    # 支持的图片扩展名
    image_extensions = ('.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tiff')
    
    for root, _, files in os.walk(dir_path):
        for file in files:
            if file.lower().endswith(image_extensions):
                image_path = os.path.join(root, file)
                if process_image(image_path, bak_dir):
                    success_count += 1
                else:
                    fail_count += 1
    
    return success_count, fail_count

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='调整图片尺寸为1280x720')
    parser.add_argument('path', help='图片路径或包含图片的目录路径')
    parser.add_argument('--bak', default='bak', help='备份目录路径，默认为"bak"')
    
    args = parser.parse_args()
    
    if os.path.isdir(args.path):
        # 处理目录
        success, fail = process_directory(args.path, args.bak)
        logger.info(f"处理完成: {success} 个图片处理成功，{fail} 个图片处理失败")
    else:
        # 处理单个图片
        if process_image(args.path, args.bak):
            logger.info("图片处理成功")
        else:
            logger.error("图片处理失败")
            sys.exit(1)

if __name__ == "__main__":
    main()
