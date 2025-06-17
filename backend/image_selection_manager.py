#!/usr/bin/env python3
"""
图片选择状态管理器
用于管理用户选择图片的顺序和状态
"""

from typing import List, Dict, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class ImageSelectionManager:
    """
    图片选择状态管理器
    
    管理用户选择图片的顺序，支持添加、移除选择，并自动维护选择顺序。
    最多支持选择8张图片。
    """
    
    def __init__(self, max_selections: int = 8):
        """
        初始化图片选择管理器
        
        Args:
            max_selections: 最大选择数量，默认为8
        """
        self.max_selections = max_selections
        self.selected_images: List[str] = []  # 按选择顺序的图片路径列表
        self.selection_order: Dict[str, int] = {}  # 图片路径到顺序号的映射
        self.next_order = 1  # 下一个选择的序号
        
        logger.info(f"图片选择管理器初始化完成，最大选择数量: {max_selections}")
    
    def add_selection(self, image_path: str) -> Tuple[bool, str]:
        """
        添加图片选择
        
        Args:
            image_path: 图片路径
            
        Returns:
            Tuple[bool, str]: (操作是否成功, 状态消息)
        """
        try:
            # 检查是否已达到最大选择数量
            if len(self.selected_images) >= self.max_selections:
                message = f"已达到最大选择数量({self.max_selections}张)"
                logger.warning(f"添加选择失败: {message}, 图片: {image_path}")
                return False, message
            
            # 检查图片是否已被选择
            if image_path in self.selection_order:
                message = "图片已被选择"
                logger.warning(f"添加选择失败: {message}, 图片: {image_path}")
                return False, message
            
            # 添加选择
            self.selected_images.append(image_path)
            self.selection_order[image_path] = self.next_order
            order_num = self.next_order
            self.next_order += 1
            
            message = f"已选择第{order_num}张图片"
            logger.info(f"添加选择成功: {message}, 图片: {image_path}")
            return True, message
            
        except Exception as e:
            error_msg = f"添加选择时发生错误: {str(e)}"
            logger.error(f"{error_msg}, 图片: {image_path}")
            return False, error_msg
    
    def remove_selection(self, image_path: str) -> Tuple[bool, str]:
        """
        移除图片选择并重新排序后续图片
        
        Args:
            image_path: 要移除的图片路径
            
        Returns:
            Tuple[bool, str]: (操作是否成功, 状态消息)
        """
        try:
            # 检查图片是否已被选择
            if image_path not in self.selection_order:
                message = "图片未被选择"
                logger.warning(f"移除选择失败: {message}, 图片: {image_path}")
                return False, message
            
            # 获取被移除图片的顺序号
            removed_order = self.selection_order[image_path]
            
            # 从列表和映射中移除
            self.selected_images.remove(image_path)
            del self.selection_order[image_path]
            
            # 重新排序后续图片
            for img_path in self.selected_images:
                if self.selection_order[img_path] > removed_order:
                    self.selection_order[img_path] -= 1
            
            # 更新下一个选择序号
            self.next_order = len(self.selected_images) + 1
            
            message = f"已取消选择，剩余{len(self.selected_images)}张图片"
            logger.info(f"移除选择成功: {message}, 图片: {image_path}")
            return True, message
            
        except Exception as e:
            error_msg = f"移除选择时发生错误: {str(e)}"
            logger.error(f"{error_msg}, 图片: {image_path}")
            return False, error_msg
    
    def get_ordered_images(self) -> List[str]:
        """
        获取按选择顺序排列的图片列表
        
        Returns:
            List[str]: 按选择顺序排列的图片路径列表
        """
        return self.selected_images.copy()
    
    def get_selection_info(self) -> Dict[str, any]:
        """
        获取选择信息
        
        Returns:
            Dict: 包含选择数量、最大数量、顺序映射等信息
        """
        return {
            "count": len(self.selected_images),
            "max_count": self.max_selections,
            "order_map": self.selection_order.copy(),
            "selected_images": self.selected_images.copy(),
            "is_full": len(self.selected_images) >= self.max_selections,
            "remaining": self.max_selections - len(self.selected_images)
        }
    
    def clear_all(self) -> Tuple[bool, str]:
        """
        清空所有选择
        
        Returns:
            Tuple[bool, str]: (操作是否成功, 状态消息)
        """
        try:
            cleared_count = len(self.selected_images)
            
            self.selected_images.clear()
            self.selection_order.clear()
            self.next_order = 1
            
            message = f"已清空所有选择，共清除{cleared_count}张图片"
            logger.info(f"清空选择成功: {message}")
            return True, message
            
        except Exception as e:
            error_msg = f"清空选择时发生错误: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    def is_selected(self, image_path: str) -> bool:
        """
        检查图片是否已被选择
        
        Args:
            image_path: 图片路径
            
        Returns:
            bool: 是否已被选择
        """
        return image_path in self.selection_order
    
    def get_selection_order(self, image_path: str) -> Optional[int]:
        """
        获取图片的选择顺序号
        
        Args:
            image_path: 图片路径
            
        Returns:
            Optional[int]: 选择顺序号，如果未选择则返回None
        """
        return self.selection_order.get(image_path)
    
    def is_full(self) -> bool:
        """
        检查是否已达到最大选择数量
        
        Returns:
            bool: 是否已满
        """
        return len(self.selected_images) >= self.max_selections
    
    def get_status_summary(self) -> str:
        """
        获取状态摘要字符串
        
        Returns:
            str: 状态摘要，如"已选择 3/8 张图片"
        """
        count = len(self.selected_images)
        if count == 0:
            return f"请选择图片 (最多{self.max_selections}张)"
        elif count < self.max_selections:
            return f"已选择 {count}/{self.max_selections} 张图片"
        else:
            return f"已选择 {count}/{self.max_selections} 张图片 (已达上限)"
    
    def __str__(self) -> str:
        """字符串表示"""
        return f"ImageSelectionManager(selected={len(self.selected_images)}/{self.max_selections})"
    
    def __repr__(self) -> str:
        """详细字符串表示"""
        return (f"ImageSelectionManager(selected={len(self.selected_images)}, "
                f"max={self.max_selections}, "
                f"images={self.selected_images})")


# 测试代码（仅在直接运行时执行）
if __name__ == "__main__":
    # 设置日志
    logging.basicConfig(level=logging.INFO)
    
    # 创建管理器实例
    manager = ImageSelectionManager(max_selections=3)  # 测试用，设置为3张
    
    print("=== 图片选择管理器测试 ===")
    print(f"初始状态: {manager}")
    print(f"状态摘要: {manager.get_status_summary()}")
    print()
    
    # 测试添加选择
    test_images = ["img1.jpg", "img2.jpg", "img3.jpg", "img4.jpg"]
    
    print("--- 测试添加选择 ---")
    for img in test_images:
        success, message = manager.add_selection(img)
        print(f"添加 {img}: {'成功' if success else '失败'} - {message}")
        print(f"当前状态: {manager.get_status_summary()}")
        print()
    
    # 测试获取信息
    print("--- 当前选择信息 ---")
    info = manager.get_selection_info()
    print(f"选择信息: {info}")
    print(f"按顺序的图片: {manager.get_ordered_images()}")
    print()
    
    # 测试移除选择
    print("--- 测试移除选择 ---")
    success, message = manager.remove_selection("img2.jpg")
    print(f"移除 img2.jpg: {'成功' if success else '失败'} - {message}")
    print(f"当前状态: {manager.get_status_summary()}")
    print(f"按顺序的图片: {manager.get_ordered_images()}")
    print(f"选择信息: {manager.get_selection_info()}")
    print()
    
    # 测试清空
    print("--- 测试清空所有选择 ---")
    success, message = manager.clear_all()
    print(f"清空结果: {'成功' if success else '失败'} - {message}")
    print(f"最终状态: {manager.get_status_summary()}")
