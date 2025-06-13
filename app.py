#!/usr/bin/env python3
"""
AI视频生成器 - 自动刷新版本
保持原有的AWS调用方式，只添加自动刷新功能
"""

import gradio as gr
import os
import time
import logging
from typing import List, Tuple, Optional
import sys
from dotenv import load_dotenv

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

logger = logging.getLogger(__name__)


class AutoRefreshVideoApp:
    """自动刷新视频生成应用"""
    
    def __init__(self, images_dir: str = "images"):
        """初始化应用"""
        self.images_dir = images_dir
        self.video_generator = VideoGenerator()
        self.image_categories = self._load_image_categories()
        self.available_styles = self.video_generator.get_flat_style_list()
        
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
    
    def start_generation(self, category: str, style: str, *checkbox_values) -> Tuple[str, str, str]:
        """启动视频生成"""
        try:
            # 验证输入
            if not category:
                return "❌ 请选择图片分类", "", ""
            
            if not style:
                return "❌ 请选择视频风格", "", ""
            
            # 获取选中的图片
            images = self.get_images_for_category(category)
            selected_images = []
            
            for i, is_selected in enumerate(checkbox_values):
                if is_selected and i < len(images):
                    selected_images.append(images[i])
            
            if not selected_images:
                return "❌ 请至少选择一张图片", "", ""
            
            if len(selected_images) > 8:
                return "❌ 最多只能选择8张图片", "", ""
            
            # 使用原有的视频生成器启动生成
            result = self.video_generator.start_async_video_generation(
                images=selected_images,
                style=style,
                category=category
            )
            
            if result["status"] == "success":
                return (
                    f"🚀 视频生成已启动！\n"
                    f"📊 使用了 {len(selected_images)} 张 {category} 图片\n"
                    f"🎨 风格: {style}\n"
                    f"🔄 自动刷新已启用，每5秒检查一次状态...",
                    result["session_id"],
                    ""
                )
            else:
                return (
                    f"❌ {result['message']}",
                    "",
                    result.get('error_details', '')
                )
                
        except Exception as e:
            error_msg = f"启动生成失败: {str(e)}"
            logger.error(error_msg)
            return error_msg, "", str(e)
    
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
                    f"🎉 [{current_time}] 视频生成完成！\n"
                    f"🎨 风格: {result['style']}\n"
                    f"📊 使用了 {result['images_count']} 张 {result['category']} 图片\n"
                    f"🎬 包含 {result.get('shots_count', 0)} 个镜头\n"
                    f"✅ 自动刷新已停止",
                    result["video_path"],
                    ""
                )
            elif result["status"] == "in_progress":
                return (
                    f"⏳ [{current_time}] {result['message']}\n"
                    f"🔄 自动刷新中...",
                    None,
                    ""
                )
            elif result["status"] == "failed":
                return (
                    f"❌ [{current_time}] {result['message']}\n"
                    f"⏹️ 自动刷新已停止",
                    None,
                    result['message']
                )
            else:
                return (
                    f"❓ [{current_time}] 状态未知: {result.get('message', '未知状态')}\n"
                    f"🔄 继续检查中...",
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
            title="🎬 AI视频生成器 - 自动刷新版",
            theme=gr.themes.Soft()
        ) as interface:
            
            # 标题和说明
            gr.Markdown("""
            # 🎬 AI视频生成器
            """)
            
            with gr.Row():
                # 左侧控制面板
                with gr.Column(scale=1):
                    gr.Markdown("## 📁 选择图片分类")
                    category_radio = gr.Radio(
                        choices=list(self.image_categories.keys()),
                        label="图片分类",
                        value=None
                    )
                    
                    gr.Markdown("## 🎨 选择视频风格")
                    style_dropdown = gr.Dropdown(
                        choices=self.available_styles,
                        label="视频风格",
                        value=self.available_styles[0] if self.available_styles else None
                    )
                    
                    gr.Markdown("## 🚀 开始生成")
                    start_btn = gr.Button(
                        "🎬 开始生成视频",
                        variant="primary",
                        size="lg"
                    )
                    
                    gr.Markdown("## 📊 手动检查")
                    check_btn = gr.Button(
                        "🔍 立即检查状态",
                        variant="secondary"
                    )
                    
                    # 自动刷新控制
                    auto_refresh_enabled = gr.Checkbox(
                        label="🔄 启用自动刷新 (每5秒)",
                        value=True
                    )
                    
                # 右侧图片选择区域
                with gr.Column(scale=2):
                    gr.Markdown("## 🖼️ 选择图片 (1-8张)")
                    
                    selection_status = gr.Textbox(
                        label="📋 选择状态",
                        value="请先选择图片分类",
                        interactive=False
                    )
                    
                    # 图片网格 - 2行6列
                    image_components = []
                    checkbox_components = []
                    
                    with gr.Row():
                        for i in range(6):
                            with gr.Column(scale=1, min_width=100):
                                checkbox = gr.Checkbox(
                                    label="",
                                    value=False,
                                    visible=False
                                )
                                image = gr.Image(
                                    label="",
                                    height=80,
                                    width=80,
                                    interactive=False,
                                    visible=False,
                                    show_label=False
                                )
                                checkbox_components.append(checkbox)
                                image_components.append(image)
                    
                    with gr.Row():
                        for i in range(6, 12):
                            with gr.Column(scale=1, min_width=100):
                                checkbox = gr.Checkbox(
                                    label="",
                                    value=False,
                                    visible=False
                                )
                                image = gr.Image(
                                    label="",
                                    height=80,
                                    width=80,
                                    interactive=False,
                                    visible=False,
                                    show_label=False
                                )
                                checkbox_components.append(checkbox)
                                image_components.append(image)
            
            # 结果显示区域
            gr.Markdown("## 📹 生成结果")
            
            # 隐藏的会话ID
            session_id_state = gr.Textbox(
                label="会话ID",
                visible=False,
                interactive=False
            )
            
            # 状态显示
            status_display = gr.Textbox(
                label="📊 状态信息",
                interactive=False,
                lines=4
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
            
            # 自动刷新定时器
            refresh_timer = gr.Timer(value=5, active=False)
            
            # 事件处理函数
            def update_image_display(category):
                """更新图片显示"""
                if not category:
                    updates = []
                    for i in range(12):
                        updates.append(gr.update(visible=False, value=False))  # checkbox
                        updates.append(gr.update(visible=False, value=None))   # image
                    updates.append("请选择图片分类")
                    return updates
                
                images = self.get_images_for_category(category)
                updates = []
                
                for i in range(12):
                    if i < len(images):
                        updates.append(gr.update(visible=True, value=False))   # checkbox
                        updates.append(gr.update(visible=True, value=images[i]))  # image
                    else:
                        updates.append(gr.update(visible=False, value=False))  # checkbox
                        updates.append(gr.update(visible=False, value=None))   # image
                
                status = f"📊 请勾选要使用的图片"
                updates.append(status)
                return updates
            
            def auto_refresh_status(session_id, enabled):
                """自动刷新状态"""
                if not enabled or not session_id:
                    return gr.update(), gr.update(), gr.update()
                
                print(f"[{time.strftime('%H:%M:%S')}] 🔄 自动检查状态: {session_id}")
                return self.check_status(session_id)
            
            # 组合所有组件用于更新
            all_image_components = []
            for i in range(12):
                all_image_components.append(checkbox_components[i])
                all_image_components.append(image_components[i])
            all_image_components.append(selection_status)
            
            # 绑定事件
            category_radio.change(
                fn=update_image_display,
                inputs=[category_radio],
                outputs=all_image_components
            )
            
            # 开始生成
            start_result = start_btn.click(
                fn=self.start_generation,
                inputs=[category_radio, style_dropdown] + checkbox_components,
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
            
            # 手动检查
            check_btn.click(
                fn=self.check_status,
                inputs=[session_id_state],
                outputs=[status_display, video_player, error_display]
            ).then(
                fn=lambda error: gr.update(visible=bool(error.strip())),
                inputs=[error_display],
                outputs=[error_display]
            )
            
            # 自动刷新定时器 - 关键部分
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
        
        # 创建并启动应用
        logger.info("🚀 启动AI视频生成器 - 自动刷新版...")
        print("🎬 AI视频生成器 - 自动刷新版启动中...")
        print("✨ 新功能:")
        print("  🔄 自动刷新 - 每5秒自动检查生成状态")
        print("  🎯 智能停止 - 完成或失败时自动停止")
        print("  ⏰ 实时反馈 - 显示带时间戳的状态信息")
        print()
        
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
