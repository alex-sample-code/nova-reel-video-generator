#!/usr/bin/env python3

import gradio as gr
import os
import time
import logging
from typing import List, Tuple, Optional
import sys
from dotenv import load_dotenv
import threading
from functools import wraps

# 加载环境变量
load_dotenv()

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('video_generator_clean.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

# 使用原有的后端模块
from backend.video_generator import VideoGenerator
# 导入图片选择状态管理器
from image_selection_manager import ImageSelectionManager

logger = logging.getLogger(__name__)


def debounce(wait_time):
    """
    防抖装饰器，避免频繁调用
    
    Args:
        wait_time: 等待时间（秒）
    """
    def decorator(func):
        last_called = [0]
        timer = [None]
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            def call_func():
                last_called[0] = time.time()
                return func(*args, **kwargs)
            
            now = time.time()
            if timer[0]:
                timer[0].cancel()
            
            if now - last_called[0] >= wait_time:
                return call_func()
            else:
                timer[0] = threading.Timer(wait_time, call_func)
                timer[0].start()
                return None
        
        return wrapper
    return decorator


def cache_result(cache_time=5):
    """
    结果缓存装饰器
    
    Args:
        cache_time: 缓存时间（秒）
    """
    def decorator(func):
        cache = {}
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 生成缓存键
            cache_key = str(args) + str(sorted(kwargs.items()))
            current_time = time.time()
            
            # 检查缓存
            if cache_key in cache:
                result, timestamp = cache[cache_key]
                if current_time - timestamp < cache_time:
                    return result
            
            # 执行函数并缓存结果
            result = func(*args, **kwargs)
            cache[cache_key] = (result, current_time)
            
            # 清理过期缓存
            expired_keys = [k for k, (_, ts) in cache.items() 
                          if current_time - ts >= cache_time]
            for k in expired_keys:
                del cache[k]
            
            return result
        
        return wrapper
    return decorator


class AutoRefreshVideoApp:
    """自动刷新视频生成应用"""
    
    def __init__(self, images_dir: str = "images"):
        """初始化应用"""
        self.images_dir = images_dir
        self.video_generator = VideoGenerator()
        self.image_categories = self._load_image_categories()
        self.available_styles = self.video_generator.get_flat_style_list()
        
        # 初始化图片选择状态管理器
        self.selection_manager = ImageSelectionManager(max_selections=8)
        
        logger.info("自动刷新视频应用初始化完成")
    
    def _load_image_categories(self) -> dict:
        """加载图片分类"""
        categories = {}
        
        if not os.path.exists(self.images_dir):
            logger.error(f"图片目录不存在: {self.images_dir}")
            return categories
        
        for category in os.listdir(self.images_dir):
            category_path = os.path.join(self.images_dir, category)
            
            if os.path.isdir(category_path):
                images = []
                for filename in os.listdir(category_path):
                    if filename.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
                        image_path = os.path.join(category_path, filename)
                        images.append(image_path)
                
                if images:
                    categories[category] = sorted(images)
        
        logger.info(f"加载图片分类: {list(categories.keys())}")
        return categories
    
    def get_images_for_category(self, category: str) -> List[str]:
        """获取分类下的图片"""
        return self.image_categories.get(category, [])
    
    def handle_image_click(self, image_path: str, category: str) -> Tuple[str, str, str]:
        """
        处理图片点击事件
        
        Args:
            image_path: 被点击的图片路径
            category: 当前选择的分类
            
        Returns:
            Tuple[str, str, str]: (状态消息, 选择状态JSON, 错误信息)
        """
        try:
            if not image_path or not category:
                return "❌ 无效的图片或分类", "", "图片路径或分类为空"
            
            # 检查图片是否已被选择
            if self.selection_manager.is_selected(image_path):
                # 取消选择
                success, message = self.selection_manager.remove_selection(image_path)
                if success:
                    status_msg = f"✅ {message}"
                    logger.info(f"取消选择图片: {image_path}")
                else:
                    status_msg = f"❌ {message}"
                    logger.error(f"取消选择失败: {message}, 图片: {image_path}")
            else:
                # 添加选择
                success, message = self.selection_manager.add_selection(image_path)
                if success:
                    status_msg = f"✅ {message}"
                    logger.info(f"选择图片: {image_path}")
                else:
                    status_msg = f"⚠️ {message}"
                    logger.warning(f"选择失败: {message}, 图片: {image_path}")
            
            # 获取当前选择状态
            selection_info = self.selection_manager.get_selection_info()
            selection_json = str(selection_info)  # 简化为字符串，后续可改为JSON
            
            return status_msg, selection_json, ""
            
        except Exception as e:
            error_msg = f"处理图片点击时发生错误: {str(e)}"
            logger.error(f"{error_msg}, 图片: {image_path}")
            return f"❌ {error_msg}", "", str(e)
    
    def update_selection_display(self, category: str) -> Tuple[str, List[dict]]:
        """
        更新选择状态显示
        
        Args:
            category: 当前分类
            
        Returns:
            Tuple[str, List[dict]]: (状态摘要, 图片显示状态列表)
        """
        try:
            if not category:
                return "请选择图片分类", []
            
            # 获取当前分类的所有图片
            category_images = self.get_images_for_category(category)
            if not category_images:
                return "该分类下没有图片", []
            
            # 获取选择信息
            selection_info = self.selection_manager.get_selection_info()
            status_summary = self.selection_manager.get_status_summary()
            
            # 生成每个图片的显示状态
            image_states = []
            for i, image_path in enumerate(category_images):
                if i >= 12:  # 最多显示12张图片（2行×6列）
                    break
                
                state = {
                    "index": i,
                    "path": image_path,
                    "selected": self.selection_manager.is_selected(image_path),
                    "order": self.selection_manager.get_selection_order(image_path),
                    "disabled": (not self.selection_manager.is_selected(image_path) 
                               and self.selection_manager.is_full())
                }
                image_states.append(state)
            
            logger.debug(f"更新选择显示: {status_summary}, 图片数量: {len(image_states)}")
            return status_summary, image_states
            
        except Exception as e:
            error_msg = f"更新选择显示时发生错误: {str(e)}"
            logger.error(f"{error_msg}, 分类: {category}")
            return f"❌ {error_msg}", []
    
    def prepare_checkbox_values_for_backend(self, category: str) -> List[bool]:
        """
        为后端准备checkbox值列表，保持接口兼容性
        将选择管理器的数据转换为原有的checkbox格式
        
        Args:
            category: 当前分类
            
        Returns:
            List[bool]: 按原有格式的checkbox值列表，但按选择顺序排列
        """
        try:
            if not category:
                logger.warning("prepare_checkbox_values_for_backend: 分类为空")
                return []
            
            # 获取当前分类的所有图片
            category_images = self.get_images_for_category(category)
            if not category_images:
                logger.warning(f"prepare_checkbox_values_for_backend: 分类 '{category}' 下没有图片")
                return []
            
            # 获取按选择顺序排列的图片
            ordered_selected_images = self.selection_manager.get_ordered_images()
            
            # 生成checkbox值列表 - 保持原有的图片顺序，但标记选中状态
            checkbox_values = []
            for image_path in category_images:
                is_selected = image_path in ordered_selected_images
                checkbox_values.append(is_selected)
            
            # 记录转换信息
            selected_count = sum(checkbox_values)
            logger.info(f"prepare_checkbox_values_for_backend: 分类={category}, "
                       f"总图片={len(category_images)}, 选中={selected_count}, "
                       f"选择顺序={[img.split('/')[-1] for img in ordered_selected_images]}")
            
            return checkbox_values
            
        except Exception as e:
            error_msg = f"准备checkbox值时发生错误: {str(e)}"
            logger.error(f"{error_msg}, 分类: {category}")
            return []
    
    def validate_selection_consistency(self, category: str) -> Tuple[bool, str]:
        """
        验证选择状态的一致性
        
        Args:
            category: 当前分类
            
        Returns:
            Tuple[bool, str]: (是否一致, 验证消息)
        """
        try:
            selection_info = self.selection_manager.get_selection_info()
            category_images = self.get_images_for_category(category)
            
            # 检查选择的图片是否都在当前分类中
            for selected_image in selection_info['selected_images']:
                if selected_image not in category_images:
                    return False, f"选择的图片 {selected_image} 不在当前分类 {category} 中"
            
            # 检查选择数量是否一致
            if len(selection_info['selected_images']) != selection_info['count']:
                return False, f"选择数量不一致: 列表长度={len(selection_info['selected_images'])}, 计数={selection_info['count']}"
            
            # 检查顺序映射是否正确
            for i, image_path in enumerate(selection_info['selected_images'], 1):
                expected_order = selection_info['order_map'].get(image_path)
                if expected_order != i:
                    return False, f"选择顺序不一致: 图片 {image_path} 期望顺序 {i}, 实际顺序 {expected_order}"
            
            return True, f"选择状态一致: {selection_info['count']} 张图片"
            
        except Exception as e:
            error_msg = f"验证选择一致性时发生错误: {str(e)}"
            logger.error(f"{error_msg}, 分类: {category}")
            return False, error_msg
    
    def reset_selection_for_category(self, category: str) -> str:
        """
        重置分类选择状态（当用户切换分类时调用）
        
        Args:
            category: 新选择的分类
            
        Returns:
            str: 状态消息
        """
        try:
            # 清空当前选择
            success, message = self.selection_manager.clear_all()
            if success:
                logger.info(f"切换到分类 '{category}': {message}")
                return f"已切换到 {category} 分类"
            else:
                logger.error(f"重置选择失败: {message}")
                return f"❌ 重置失败: {message}"
                
        except Exception as e:
            error_msg = f"重置分类选择时发生错误: {str(e)}"
            logger.error(f"{error_msg}, 分类: {category}")
            return f"❌ {error_msg}"
    
    def generate_status_bar_html(self, selection_info: dict = None) -> str:
        """
        生成状态栏HTML
        
        Args:
            selection_info: 选择信息字典，如果为None则使用当前状态
            
        Returns:
            str: 状态栏HTML字符串
        """
        try:
            if selection_info is None:
                selection_info = self.selection_manager.get_selection_info()
            
            count = selection_info.get('count', 0)
            max_count = selection_info.get('max_count', 8)
            
            if count == 0:
                # 未选择状态
                html = f"""
                <div style='
                    text-align: center; 
                    padding: 12px 20px; 
                    background: #f8f9fa; 
                    border: 1px solid #e9ecef;
                    border-radius: 8px; 
                    margin: 10px 0;
                    font-size: 14px;
                    color: #6c757d;
                '>
                    📋 请选择图片 (最多{max_count}张)
                </div>
                """
            elif count < max_count:
                # 部分选择状态
                html = f"""
                <div style='
                    text-align: center; 
                    padding: 12px 20px; 
                    background: #e3f2fd; 
                    border: 1px solid #90caf9;
                    border-radius: 8px; 
                    margin: 10px 0;
                    font-size: 14px;
                    color: #1976d2;
                    font-weight: 500;
                '>
                    ✅ 已选择 {count}/{max_count} 张图片
                </div>
                """
            else:
                # 已满状态
                html = f"""
                <div style='
                    text-align: center; 
                    padding: 12px 20px; 
                    background: #e8f5e8; 
                    border: 1px solid #81c784;
                    border-radius: 8px; 
                    margin: 10px 0;
                    font-size: 14px;
                    color: #2e7d32;
                    font-weight: 500;
                '>
                    🎯 已选择 {count}/{max_count} 张图片 (已达上限)
                </div>
                """
            
            return html
            
        except Exception as e:
            logger.error(f"生成状态栏HTML时发生错误: {str(e)}")
            return f"""
            <div style='
                text-align: center; 
                padding: 12px 20px; 
                background: #fff3cd; 
                border: 1px solid #ffeaa7;
                border-radius: 8px; 
                margin: 10px 0;
                color: #856404;
            '>
                ❌ 状态显示错误
            </div>
            """
    
    def generate_warning_html(self, warning_type: str, message: str = "") -> str:
        """
        生成警告提示HTML
        
        Args:
            warning_type: 警告类型 ('max_limit', 'error', 'info')
            message: 自定义消息，如果为空则使用默认消息
            
        Returns:
            str: 警告HTML字符串
        """
        try:
            warning_configs = {
                'max_limit': {
                    'icon': '⚠️',
                    'default_message': '最多只能选择8张图片，请先取消一些已选择的图片',
                    'bg_color': '#fff3cd',
                    'border_color': '#ffeaa7',
                    'text_color': '#856404'
                },
                'error': {
                    'icon': '❌',
                    'default_message': '操作失败，请重试',
                    'bg_color': '#f8d7da',
                    'border_color': '#f5c6cb',
                    'text_color': '#721c24'
                },
                'info': {
                    'icon': 'ℹ️',
                    'default_message': '提示信息',
                    'bg_color': '#d1ecf1',
                    'border_color': '#bee5eb',
                    'text_color': '#0c5460'
                },
                'success': {
                    'icon': '✅',
                    'default_message': '操作成功',
                    'bg_color': '#d4edda',
                    'border_color': '#c3e6cb',
                    'text_color': '#155724'
                }
            }
            
            config = warning_configs.get(warning_type, warning_configs['info'])
            display_message = message if message else config['default_message']
            
            html = f"""
            <div style='
                padding: 12px 16px;
                background: {config['bg_color']};
                border: 1px solid {config['border_color']};
                border-radius: 6px;
                margin: 10px 0;
                font-size: 13px;
                color: {config['text_color']};
                display: flex;
                align-items: center;
                gap: 8px;
                animation: fadeIn 0.3s ease-in-out;
            '>
                <span style='font-size: 16px;'>{config['icon']}</span>
                <span>{display_message}</span>
            </div>
            <style>
                @keyframes fadeIn {{
                    from {{ opacity: 0; transform: translateY(-10px); }}
                    to {{ opacity: 1; transform: translateY(0); }}
                }}
            </style>
            """
            
            return html
            
        except Exception as e:
            logger.error(f"生成警告HTML时发生错误: {str(e)}")
            return f"""
            <div style='
                padding: 12px 16px;
                background: #f8d7da;
                border: 1px solid #f5c6cb;
                border-radius: 6px;
                margin: 10px 0;
                color: #721c24;
            '>
                ❌ 警告显示错误: {str(e)}
            </div>
            """
    
    @cache_result(cache_time=3)
    def update_status_bar(self, category: str = "") -> str:
        """
        更新状态栏显示（带缓存优化）
        
        Args:
            category: 当前分类
            
        Returns:
            str: 状态栏HTML
        """
        try:
            if not category:
                return self.generate_status_bar_html({
                    'count': 0, 
                    'max_count': 8
                })
            
            selection_info = self.selection_manager.get_selection_info()
            return self.generate_status_bar_html(selection_info)
            
        except Exception as e:
            logger.error(f"更新状态栏时发生错误: {str(e)}")
            return self.generate_warning_html('error', f"状态更新失败: {str(e)}")
    
    @debounce(0.3)
    def update_image_grid_display_debounced(self, category: str) -> List[str]:
        """
        更新图片网格显示（防抖优化）
        
        Args:
            category: 当前分类
            
        Returns:
            List[str]: 12个图片位置的HTML列表
        """
        return self.update_image_grid_display(category)
    
    def generate_enhanced_image_html(self, image_path: str, order_number: int = None, 
                                   is_disabled: bool = False, image_size: int = 100) -> str:
        """
        生成增强的图片HTML，包含悬停提示和动画效果
        
        Args:
            image_path: 图片路径
            order_number: 选择顺序号，None表示未选择
            is_disabled: 是否禁用状态
            image_size: 图片尺寸
            
        Returns:
            str: 增强的图片HTML字符串
        """
        try:
            # 生成悬停提示文本
            if order_number is not None:
                tooltip_text = f"第{order_number}个选择 - 点击取消选择"
            elif is_disabled:
                tooltip_text = "已达到最大选择数量(8张)"
            else:
                tooltip_text = "点击选择此图片"
            
            # 基础样式
            container_style = f"""
                position: relative;
                display: inline-block;
                width: {image_size}px;
                height: {image_size}px;
                cursor: pointer;
                border-radius: 8px;
                overflow: hidden;
                transition: all 0.2s ease-in-out;
                margin: 4px;
            """
            
            # 图片样式
            img_style = f"""
                width: 100%;
                height: 100%;
                object-fit: cover;
                border-radius: 8px;
                transition: all 0.2s ease-in-out;
            """
            
            # 根据状态调整样式
            if order_number is not None:
                # 选中状态
                container_style += """
                    border: 2px solid #007bff;
                    box-shadow: 0 0 0 2px rgba(0,123,255,0.25);
                    transform: scale(1.02);
                """
                
                # 数字标记
                number_badge = f"""
                <div style='
                    position: absolute;
                    top: 8px;
                    right: 8px;
                    width: 24px;
                    height: 24px;
                    background: #007bff;
                    color: white;
                    border-radius: 50%;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    font-size: 12px;
                    font-weight: bold;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.2);
                    z-index: 10;
                    animation: bounceIn 0.3s ease-in-out;
                '>
                    {order_number}
                </div>
                """
            else:
                number_badge = ""
            
            if is_disabled:
                # 禁用状态
                container_style += """
                    cursor: not-allowed;
                """
                img_style += """
                    opacity: 0.4;
                    filter: grayscale(50%);
                """
                tooltip_class = "disabled-tooltip"
            else:
                tooltip_class = "normal-tooltip"
            
            # 悬停提示
            tooltip_html = f"""
            <div class='tooltip {tooltip_class}' style='
                position: absolute;
                bottom: -30px;
                left: 50%;
                transform: translateX(-50%);
                background: rgba(0,0,0,0.8);
                color: white;
                padding: 4px 8px;
                border-radius: 4px;
                font-size: 11px;
                white-space: nowrap;
                opacity: 0;
                pointer-events: none;
                transition: opacity 0.2s ease-in-out;
                z-index: 20;
            '>
                {tooltip_text}
            </div>
            """
            
            # 生成完整HTML
            html = f"""
            <div style='{container_style}' class='image-container enhanced-image' onmouseover='showTooltip(this)' onmouseout='hideTooltip(this)'>
                <img src='{image_path}' style='{img_style}' alt='图片' />
                {number_badge}
                {tooltip_html}
            </div>
            <style>
                @keyframes bounceIn {{
                    0% {{ opacity: 0; transform: scale(0.3); }}
                    50% {{ opacity: 1; transform: scale(1.1); }}
                    100% {{ opacity: 1; transform: scale(1); }}
                }}
                
                @keyframes fadeIn {{
                    from {{ opacity: 0; transform: translateY(-10px); }}
                    to {{ opacity: 1; transform: translateY(0); }}
                }}
                
                .enhanced-image:hover {{
                    transform: scale(1.05) !important;
                    box-shadow: 0 8px 16px rgba(0,0,0,0.15) !important;
                }}
                
                .enhanced-image.disabled:hover {{
                    transform: none !important;
                }}
                
                .enhanced-image:hover .tooltip {{
                    opacity: 1;
                }}
                
                @media (max-width: 768px) {{
                    .enhanced-image {{
                        margin: 2px;
                    }}
                }}
                
                @media (max-width: 480px) {{
                    .enhanced-image {{
                        width: 80px !important;
                        height: 80px !important;
                    }}
                }}
            </style>
            <script>
                function showTooltip(element) {{
                    const tooltip = element.querySelector('.tooltip');
                    if (tooltip) {{
                        tooltip.style.opacity = '1';
                    }}
                }}
                
                function hideTooltip(element) {{
                    const tooltip = element.querySelector('.tooltip');
                    if (tooltip) {{
                        tooltip.style.opacity = '0';
                    }}
                }}
            </script>
            """
            
            return html
            
        except Exception as e:
            logger.error(f"生成增强图片HTML时发生错误: {str(e)}")
            return f"""
            <div style='
                width: {image_size}px;
                height: {image_size}px;
                background: #f8d7da;
                border: 1px solid #f5c6cb;
                border-radius: 8px;
                display: flex;
                align-items: center;
                justify-content: center;
                color: #721c24;
                font-size: 12px;
            '>
                ❌ 图片加载错误
            </div>
            """
    
    def show_warning(self, warning_type: str, message: str = "") -> str:
        """
        显示警告提示
        
        Args:
            warning_type: 警告类型
            message: 自定义消息
            
        Returns:
            str: 警告HTML
        """
        return self.generate_warning_html(warning_type, message)
    
    def hide_warning(self) -> str:
        """
        隐藏警告提示
        
        Returns:
            str: 空HTML
        """
        return ""
    
    def handle_image_click_with_feedback(self, image_path: str, category: str) -> Tuple[str, str, str, str]:
        """
        处理图片点击事件并提供完整的反馈
        
        Args:
            image_path: 被点击的图片路径
            category: 当前选择的分类
            
        Returns:
            Tuple[str, str, str, str]: (状态栏HTML, 警告HTML, 选择状态JSON, 错误信息)
        """
        try:
            if not image_path or not category:
                warning_html = self.show_warning('error', '无效的图片或分类')
                status_html = self.update_status_bar(category)
                return status_html, warning_html, "", "图片路径或分类为空"
            
            # 检查图片是否已被选择
            if self.selection_manager.is_selected(image_path):
                # 取消选择
                success, message = self.selection_manager.remove_selection(image_path)
                if success:
                    logger.info(f"取消选择图片: {image_path}")
                    warning_html = self.show_warning('success', f"已取消选择")
                else:
                    logger.error(f"取消选择失败: {message}, 图片: {image_path}")
                    warning_html = self.show_warning('error', message)
            else:
                # 添加选择
                success, message = self.selection_manager.add_selection(image_path)
                if success:
                    logger.info(f"选择图片: {image_path}")
                    warning_html = self.show_warning('success', message)
                else:
                    logger.warning(f"选择失败: {message}, 图片: {image_path}")
                    if "最大选择数量" in message:
                        warning_html = self.show_warning('max_limit')
                    else:
                        warning_html = self.show_warning('error', message)
            
            # 更新状态栏
            status_html = self.update_status_bar(category)
            
            # 获取当前选择状态
            selection_info = self.selection_manager.get_selection_info()
            selection_json = str(selection_info)
            
            return status_html, warning_html, selection_json, ""
            
        except Exception as e:
            error_msg = f"处理图片点击时发生错误: {str(e)}"
            logger.error(f"{error_msg}, 图片: {image_path}")
            
            warning_html = self.show_warning('error', error_msg)
            status_html = self.update_status_bar(category)
            
            return status_html, warning_html, "", str(e)
    
    def generate_image_with_number_html(self, image_path: str, order_number: int = None, 
                                       is_disabled: bool = False, image_size: int = 100) -> str:
        """
        生成带数字标记的图片HTML
        
        Args:
            image_path: 图片路径
            order_number: 选择顺序号，None表示未选择
            is_disabled: 是否禁用状态
            image_size: 图片尺寸
            
        Returns:
            str: 图片HTML字符串
        """
        try:
            # 基础样式
            container_style = f"""
                position: relative;
                display: inline-block;
                width: {image_size}px;
                height: {image_size}px;
                cursor: pointer;
                border-radius: 8px;
                overflow: hidden;
                transition: all 0.2s ease-in-out;
            """
            
            # 图片样式
            img_style = f"""
                width: 100%;
                height: 100%;
                object-fit: cover;
                border-radius: 8px;
            """
            
            # 根据状态调整样式
            if order_number is not None:
                # 选中状态
                container_style += """
                    border: 2px solid #007bff;
                    box-shadow: 0 0 0 2px rgba(0,123,255,0.25);
                """
                
                # 数字标记
                number_badge = f"""
                <div style='
                    position: absolute;
                    top: 8px;
                    right: 8px;
                    width: 24px;
                    height: 24px;
                    background: #007bff;
                    color: white;
                    border-radius: 50%;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    font-size: 12px;
                    font-weight: bold;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.2);
                    z-index: 10;
                    animation: fadeIn 0.3s ease-in-out;
                '>
                    {order_number}
                </div>
                """
            else:
                number_badge = ""
            
            if is_disabled:
                # 禁用状态
                container_style += """
                    cursor: not-allowed;
                """
                img_style += """
                    opacity: 0.4;
                    filter: grayscale(50%);
                """
            else:
                # 悬停效果
                container_style += """
                    &:hover {
                        transform: scale(1.02);
                        box-shadow: 0 4px 8px rgba(0,0,0,0.1);
                    }
                """
            
            # 生成完整HTML
            html = f"""
            <div style='{container_style}' class='image-container'>
                <img src='{image_path}' style='{img_style}' alt='图片' />
                {number_badge}
            </div>
            <style>
                @keyframes fadeIn {{
                    from {{ opacity: 0; transform: scale(0.8); }}
                    to {{ opacity: 1; transform: scale(1); }}
                }}
                .image-container:hover {{
                    transform: scale(1.02);
                    box-shadow: 0 4px 8px rgba(0,0,0,0.1);
                }}
                .image-container.disabled {{
                    cursor: not-allowed;
                }}
                .image-container.disabled img {{
                    opacity: 0.4;
                    filter: grayscale(50%);
                }}
            </style>
            """
            
            return html
            
        except Exception as e:
            logger.error(f"生成图片HTML时发生错误: {str(e)}")
            return f"""
            <div style='
                width: {image_size}px;
                height: {image_size}px;
                background: #f8d7da;
                border: 1px solid #f5c6cb;
                border-radius: 8px;
                display: flex;
                align-items: center;
                justify-content: center;
                color: #721c24;
                font-size: 12px;
            '>
                ❌ 图片加载错误
            </div>
            """
    
    def update_image_grid_display(self, category: str) -> List[str]:
        """
        更新图片网格显示，包含数字标记和视觉效果
        
        Args:
            category: 当前分类
            
        Returns:
            List[str]: 12个图片位置的HTML列表
        """
        try:
            if not category:
                # 返回12个空的HTML
                return [""] * 12
            
            images = self.get_images_for_category(category)
            selection_info = self.selection_manager.get_selection_info()
            
            html_list = []
            
            for i in range(12):
                if i < len(images):
                    image_path = images[i]
                    order_number = self.selection_manager.get_selection_order(image_path)
                    is_disabled = (not self.selection_manager.is_selected(image_path) 
                                 and self.selection_manager.is_full())
                    
                    # 使用增强的HTML生成
                    html = self.generate_enhanced_image_html(
                        image_path=image_path,
                        order_number=order_number,
                        is_disabled=is_disabled,
                        image_size=100
                    )
                    html_list.append(html)
                else:
                    html_list.append("")  # 空位置
            
            return html_list
            
        except Exception as e:
            logger.error(f"更新图片网格显示时发生错误: {str(e)}")
            return ["❌ 显示错误"] * 12
    
    def batch_update_components(self, category: str, updates_needed: List[str]) -> dict:
        """
        批量更新组件，优化性能
        
        Args:
            category: 当前分类
            updates_needed: 需要更新的组件列表
            
        Returns:
            dict: 组件更新字典
        """
        try:
            updates = {}
            
            if 'status_bar' in updates_needed:
                updates['status_bar'] = self.update_status_bar(category)
            
            if 'image_grid' in updates_needed:
                updates['image_grid'] = self.update_image_grid_display(category)
            
            if 'warning' in updates_needed:
                updates['warning'] = ""
                updates['warning_visible'] = gr.update(visible=False)
            
            return updates
            
        except Exception as e:
            logger.error(f"批量更新组件时发生错误: {str(e)}")
            return {}
    
    def start_generation(self, category: str, style: str, *checkbox_values) -> Tuple[str, str, str]:
        """
        启动视频生成
        
        注意：为了保持兼容性，仍接受checkbox_values参数，但实际使用selection_manager的数据
        新版本会按选择顺序传递图片给后端，确保视频生成的连贯性
        """
        try:
            # 验证输入
            if not category:
                return "❌ 请选择图片分类", "", ""
            
            if not style:
                return "❌ 请选择视频风格", "", ""
            
            # 验证选择状态一致性
            is_consistent, validation_msg = self.validate_selection_consistency(category)
            if not is_consistent:
                logger.error(f"选择状态验证失败: {validation_msg}")
                return f"❌ 选择状态错误: {validation_msg}", "", validation_msg
            
            # 使用选择管理器获取按顺序选择的图片
            selected_images = self.selection_manager.get_ordered_images()
            
            if not selected_images:
                return "❌ 请至少选择一张图片", "", ""
            
            if len(selected_images) > 8:
                return "❌ 最多只能选择8张图片", "", ""
            
            # 生成兼容的checkbox值（用于日志记录和调试）
            checkbox_values_for_backend = self.prepare_checkbox_values_for_backend(category)
            
            # 记录详细的选择信息
            selection_info = self.selection_manager.get_selection_info()
            logger.info(f"开始生成视频:")
            logger.info(f"  分类: {category}")
            logger.info(f"  风格: {style}")
            logger.info(f"  图片数量: {len(selected_images)}")
            logger.info(f"  选择顺序: {[img.split('/')[-1] for img in selected_images]}")
            logger.info(f"  顺序映射: {selection_info['order_map']}")
            logger.info(f"  兼容checkbox: {sum(checkbox_values_for_backend)}/{len(checkbox_values_for_backend)} 选中")
            
            # 使用原有的视频生成器启动生成
            # 重要：这里传递的是按选择顺序排列的图片列表
            result = self.video_generator.start_async_video_generation(
                images=selected_images,  # 按选择顺序的图片列表
                style=style,
                category=category
            )
            
            if result["status"] == "success":
                success_msg = f"🚀 视频生成已启动! 已选择{len(selected_images)}张图片，按选择顺序处理"
                logger.info(f"视频生成启动成功: session_id={result['session_id']}")
                return (
                    success_msg,
                    result["session_id"],
                    ""
                )
            else:
                error_msg = f"❌ {result['message']}"
                logger.error(f"视频生成启动失败: {result['message']}")
                return (
                    error_msg,
                    "",
                    result.get('error_details', '')
                )
                
        except Exception as e:
            error_msg = f"启动生成失败: {str(e)}"
            logger.error(f"{error_msg}, 分类: {category}, 风格: {style}")
            return error_msg, "", str(e)
    
    def get_generation_summary(self, category: str) -> dict:
        """
        获取生成摘要信息，用于调试和日志
        
        Args:
            category: 当前分类
            
        Returns:
            dict: 生成摘要信息
        """
        try:
            selection_info = self.selection_manager.get_selection_info()
            category_images = self.get_images_for_category(category)
            
            summary = {
                "category": category,
                "total_images_in_category": len(category_images),
                "selected_count": selection_info['count'],
                "max_selections": selection_info['max_count'],
                "is_full": selection_info['is_full'],
                "selected_images": [img.split('/')[-1] for img in selection_info['selected_images']],
                "selection_order": {img.split('/')[-1]: order for img, order in selection_info['order_map'].items()},
                "ready_for_generation": selection_info['count'] > 0
            }
            
            return summary
            
        except Exception as e:
            logger.error(f"获取生成摘要时发生错误: {str(e)}")
            return {"error": str(e)}
    
    def check_status(self, session_id: str) -> Tuple[str, Optional[str], str]:
        """检查生成状态"""
        try:
            if not session_id:
                return "ℹ️ 没有正在进行的生成任务", None, ""
            
            # 使用原有的状态检查方法
            result = self.video_generator.check_async_video_status(session_id)
            current_time = time.strftime('%H:%M:%S')
            
            if result["status"] == "completed":
                return (
                    f"🎉 [{current_time}] 视频生成完成!",
                    result["video_path"],
                    ""
                )
            elif result["status"] == "in_progress":
                return (
                    f"⏳ [{current_time}] {result['message']}",
                    None,
                    ""
                )
            elif result["status"] == "failed":
                return (
                    f"❌ [{current_time}] {result['message']}",
                    None,
                    result['message']
                )
            else:
                return (
                    f"❓ [{current_time}] 状态未知: {result.get('message', '未知状态')}",
                    None,
                    result.get('message', '')
                )
                
        except Exception as e:
            error_msg = f"检查状态失败: {str(e)}"
            logger.error(error_msg)
            return error_msg, None, str(e)
    
    def create_interface(self) -> gr.Blocks:
        """创建Gradio界面"""
        
        with gr.Blocks(
            title="🎬 AI视频生成器",
            theme=gr.themes.Soft()
        ) as interface:
            
            # 标题和说明
            gr.Markdown("""
            ## 🎬 动态营销素材
            """)
            
            with gr.Row():
                # 左侧：图片分类和选择区域
                with gr.Column(scale=1):
                    gr.Markdown("### 🖼️ 选择图片 (1-8张)")
                    
                    # 使用Tab组件来显示图片分类
                    with gr.Tabs() as category_tabs:
                        tab_data = {}
                        
                        for category_name in self.image_categories.keys():
                            with gr.Tab(label=f"📁 {category_name.title()}") as tab:
                                    # 图片网格 - 2行6列
                                    images = self.get_images_for_category(category_name)
                                    
                                    # 存储该tab的组件
                                    tab_images = []
                                    tab_buttons = []
                                    tab_checkboxes = []
                                    
                                    # 修改为一行4张图片，共3行，总共12个位置
                                    for row in range(3):
                                        with gr.Row():
                                            for col in range(3):
                                                i = row * 3 + col
                                                with gr.Column(scale=1, min_width=100):
                                                    if i < len(images):
                                                        # 显示图片
                                                        image = gr.Image(
                                                            value=images[i],
                                                            label="",
                                                            height=80,
                                                            width=80,
                                                            interactive=False,
                                                            show_label=False,
                                                            container=True
                                                        )
                                                        
                                                        # 添加点击按钮
                                                        click_btn = gr.Button(
                                                            f"📷 选择图片 {i+1}",
                                                            size="sm",
                                                            variant="secondary",
                                                            elem_id=f"click_btn_{category_name}_{i}"
                                                        )
                                                    else:
                                                        # 空位置 - 仍然创建组件但设为不可见
                                                        image = gr.Image(
                                                            label="",
                                                            height=80,
                                                            width=80,
                                                            interactive=False,
                                                            visible=False,
                                                            show_label=False
                                                        )
                                                        click_btn = gr.Button(
                                                            f"📷 选择图片 {i+1}",
                                                            size="sm",
                                                            variant="secondary",
                                                            visible=False
                                                        )
                                                    
                                                    tab_images.append(image)
                                                    tab_buttons.append(click_btn)
                                                    
                                                    # 隐藏的复选框用于兼容性
                                                    checkbox = gr.Checkbox(
                                                        label="",
                                                        value=False,
                                                        visible=False
                                                    )
                                                    tab_checkboxes.append(checkbox)
                                    
                                    # 存储tab数据
                                    tab_data[category_name] = {
                                        'tab': tab,
                                        'images': tab_images,
                                        'buttons': tab_buttons,
                                        'checkboxes': tab_checkboxes,
                                        'image_paths': images
                                    }
                    
                    # 添加空白间距
                    # gr.Markdown("")
                    
                    # 视频风格选择和生成按钮
                    gr.Markdown("### 🎨 选择视频风格")
                    style_dropdown = gr.Dropdown(
                        choices=self.available_styles,
                        label="视频风格",
                        value=self.available_styles[0] if self.available_styles else None
                    )
                    
                    start_btn = gr.Button(
                        "🎬 开始生成视频",
                        variant="primary",
                        size="lg"
                    )
                
                # 右侧：视频生成结果区域
                with gr.Column(scale=2):
                    gr.Markdown("### 📹 生成结果")
                    
                    # 状态显示
                    status_display = gr.Textbox(
                        label="📊 状态信息",
                        interactive=False,
                        lines=2
                    )
                    
                    # 错误信息
                    error_display = gr.Textbox(
                        label="❌ 错误详情",
                        interactive=False,
                        lines=2,
                        visible=False
                    )
                    
                    # 视频播放器
                    video_player = gr.Video(
                        label="🎥 生成的视频",
                        height=400
                    )
            
            # 隐藏的组件
            session_id_state = gr.Textbox(
                label="会话ID",
                visible=False,
                interactive=False
            )
            
            auto_refresh_enabled = gr.Checkbox(
                label="🔄 启用自动刷新 (每5秒)",
                value=True,
                visible=False
            )
            
            # 当前选择的分类（用于跟踪）
            current_category = gr.Textbox(
                value=list(self.image_categories.keys())[0] if self.image_categories else "",
                visible=False
            )
            
            # 自动刷新定时器
            refresh_timer = gr.Timer(value=5, active=False)
            
            # 事件处理函数
            def handle_image_click_in_tab(category_name, image_index):
                """处理tab中的图片点击事件"""
                if not category_name or category_name not in tab_data:
                    return [gr.update() for _ in range(12)]
                
                images = tab_data[category_name]['image_paths']
                if image_index >= len(images):
                    return [gr.update() for _ in range(12)]
                
                image_path = images[image_index]
                
                # 处理点击事件
                self.handle_image_click_with_feedback(image_path, category_name)
                
                # 更新该tab中所有按钮的状态
                button_updates = []
                for i in range(12):
                    if i < len(images):
                        current_image = images[i]
                        is_selected = self.selection_manager.is_selected(current_image)
                        order_num = self.selection_manager.get_selection_order(current_image)
                        is_disabled = (not is_selected and self.selection_manager.is_full())
                        
                        if is_selected and order_num:
                            button_text = f"✅ {order_num}"
                            button_variant = "primary"
                        elif is_disabled:
                            button_text = f"🚫 已达上限"
                            button_variant = "secondary"
                        else:
                            button_text = f"📷 选择图片 {i+1}"
                            button_variant = "secondary"
                        
                        button_updates.append(gr.update(
                            value=button_text,
                            variant=button_variant,
                            interactive=not is_disabled
                        ))
                    else:
                        button_updates.append(gr.update())
                
                return button_updates
            
            def reset_selection_for_tab(category_name):
                """重置tab的选择状态"""
                if category_name:
                    self.reset_selection_for_category(category_name)
                    # 更新按钮状态
                    button_updates = []
                    if category_name in tab_data:
                        images = tab_data[category_name]['image_paths']
                        for i in range(12):
                            if i < len(images):
                                button_updates.append(gr.update(
                                    value=f"📷 选择图片 {i+1}",
                                    variant="secondary",
                                    interactive=True
                                ))
                            else:
                                button_updates.append(gr.update())
                    else:
                        # 如果分类不存在，返回12个默认更新
                        button_updates = [gr.update() for _ in range(12)]
                    
                    # 返回分类名和12个按钮更新
                    return [category_name] + button_updates
                
                # 如果没有分类，返回空字符串和12个默认更新
                return [""] + [gr.update() for _ in range(12)]
            
            def auto_refresh_status(session_id, enabled):
                """自动刷新状态"""
                if not enabled or not session_id:
                    return gr.update(), gr.update(), gr.update()
                
                return self.check_status(session_id)
            
            # 为每个tab的按钮绑定事件
            for category_name, data in tab_data.items():
                # 当tab被选中时重置选择状态
                data['tab'].select(
                    fn=lambda cat=category_name: reset_selection_for_tab(cat),
                    inputs=[],
                    outputs=[current_category] + data['buttons']
                )
                
                # 为每个按钮绑定点击事件
                for i, button in enumerate(data['buttons']):
                    button.click(
                        fn=lambda cat=category_name, idx=i: handle_image_click_in_tab(cat, idx),
                        inputs=[],
                        outputs=data['buttons']
                    )
            
            # 收集所有复选框用于生成
            all_checkboxes = []
            for data in tab_data.values():
                all_checkboxes.extend(data['checkboxes'])
            
            # 开始生成
            start_result = start_btn.click(
                fn=lambda style, current_cat, *checkbox_vals: self.start_generation(current_cat, style, *checkbox_vals),
                inputs=[style_dropdown, current_category] + all_checkboxes,
                outputs=[status_display, session_id_state, error_display]
            )
            
            # 激活定时器
            start_result.then(
                fn=lambda session_id: gr.update(active=bool(session_id)),
                inputs=[session_id_state],
                outputs=[refresh_timer]
            )
            
            # 显示/隐藏错误信息
            start_result.then(
                fn=lambda error: gr.update(visible=bool(error.strip())),
                inputs=[error_display],
                outputs=[error_display]
            )
            
            # 自动刷新定时器
            refresh_timer.tick(
                fn=auto_refresh_status,
                inputs=[session_id_state, auto_refresh_enabled],
                outputs=[status_display, video_player, error_display]
            ).then(
                fn=lambda error: gr.update(visible=bool(error.strip())),
                inputs=[error_display],
                outputs=[error_display]
            ).then(
                # 根据状态决定是否继续定时器
                fn=lambda status: gr.update(
                    active=("生成完成" not in status and 
                           "生成失败" not in status and 
                           "自动刷新已停止" not in status and
                           "没有正在进行的生成任务" not in status)
                ),
                inputs=[status_display],
                outputs=[refresh_timer]
            )
        
        return interface
    
    def launch(self, **kwargs):
        """启动应用"""
        interface = self.create_interface()
        interface.launch(**kwargs)


def main():
    """主函数"""
    try:
        # 检查图片目录
        images_dir = "images"
        if not os.path.exists(images_dir):
            logger.error(f"图片目录不存在: {images_dir}")
            print(f"❌ 错误: 图片目录 '{images_dir}' 不存在!")
            return
        
        # 检查AWS凭证
        if not os.getenv('AWS_ACCESS_KEY_ID') and not os.path.exists(os.path.expanduser('~/.aws/credentials')):
            logger.warning("AWS凭证未配置")
            print("⚠️  警告: AWS凭证未配置。请运行 'aws configure' 或设置环境变量。")
        
        app = AutoRefreshVideoApp(images_dir=images_dir)
        
        # 启动应用
        app.launch(
            server_name="0.0.0.0",
            server_port=7861,
            share=False,
            debug=True,
            show_error=True,
            quiet=False
        )
        
    except KeyboardInterrupt:
        logger.info("用户中断应用")
        print("\n👋 应用已停止")
    except Exception as e:
        logger.error(f"应用启动失败: {str(e)}")
        print(f"❌ 应用启动失败: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
