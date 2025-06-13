import os
import uuid
import json
from datetime import datetime
from typing import List, Dict, Any, Callable, Optional
import logging

from .aws_client import AWSBedrockClient
from .prompt_generator import PromptGenerator

logger = logging.getLogger(__name__)

class VideoGenerator:
    def __init__(self, output_dir: str = "generated_videos"):
        """
        Initialize video generator
        
        Args:
            output_dir: Directory to save generated videos
        """
        self.output_dir = output_dir
        self.aws_client = AWSBedrockClient()
        self.prompt_generator = PromptGenerator()
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Store for tracking async jobs
        self.jobs_file = os.path.join(output_dir, "jobs.json")
        self.active_jobs = self._load_jobs()
    
    def _load_jobs(self) -> Dict[str, Dict]:
        """Load active jobs from file"""
        try:
            if os.path.exists(self.jobs_file):
                with open(self.jobs_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error loading jobs: {str(e)}")
        return {}
    
    def _save_jobs(self):
        """Save active jobs to file"""
        try:
            with open(self.jobs_file, 'w', encoding='utf-8') as f:
                json.dump(self.active_jobs, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error saving jobs: {str(e)}")
    
    def start_async_video_generation(
        self, 
        images: List[str], 
        style: str, 
        category: str
    ) -> Dict[str, Any]:
        """
        Start asynchronous multi-shot video generation
        
        Args:
            images: List of image file paths
            style: Selected style for the video
            category: Image category (nature/animals)
            
        Returns:
            Dictionary with job information
        """
        try:
            # Validate inputs
            if not images:
                raise ValueError("No images provided")
            
            if len(images) > 8:  # Nova Reel 1.1 supports up to 8 shots
                raise ValueError("Maximum 8 images allowed for multi-shot video")
            
            # Validate image files exist
            for img_path in images:
                if not os.path.exists(img_path):
                    raise FileNotFoundError(f"Image file not found: {img_path}")
            
            logger.info(f"Starting async multi-shot video generation with {len(images)} images, style: {style}, category: {category}")
            
            # Step 1: Generate shot descriptions using Claude Sonnet
            shots = self.aws_client.call_claude_sonnet(images, style, category)
            
            logger.info(f"Generated {len(shots)} shot descriptions for multi-shot video")
            
            # Step 2: Start async multi-shot video generation using Nova Reel
            job_id = self.aws_client.start_async_nova_reel(shots, images)
            
            # Generate unique session ID for tracking
            session_id = f"session_{uuid.uuid4().hex[:8]}"
            
            # Store job information
            job_info = {
                "session_id": session_id,
                "job_id": job_id,
                "status": "started",
                "created_at": datetime.now().isoformat(),
                "images": images,
                "style": style,
                "category": category,
                "shots": shots,
                "images_count": len(images),
                "shots_count": len(shots),
                "generation_type": "multi_shot"
            }
            
            self.active_jobs[session_id] = job_info
            self._save_jobs()
            
            logger.info(f"Started async multi-shot video generation with session ID: {session_id}")
            
            return {
                "status": "success",
                "message": f"多镜头视频生成已开始 ({len(shots)} 个镜头)",
                "session_id": session_id,
                "job_id": job_id,
                "shots_count": len(shots)
            }
            
        except Exception as e:
            error_msg = f"启动多镜头视频生成失败: {str(e)}"
            logger.error(error_msg)
            
            return {
                "status": "error",
                "message": error_msg,
                "error_details": str(e)
            }
    
    def check_async_video_status(self, session_id: str) -> Dict[str, Any]:
        """
        Check the status of async video generation
        
        Args:
            session_id: Session ID returned from start_async_video_generation
            
        Returns:
            Dictionary with current status and result if completed
        """
        try:
            if session_id not in self.active_jobs:
                return {
                    "status": "error",
                    "message": "未找到对应的生成任务"
                }
            
            job_info = self.active_jobs[session_id]
            job_id = job_info["job_id"]
            
            # Check status with AWS
            result = self.aws_client.get_async_nova_reel_result(job_id)
            
            if result['status'] == 'completed':
                # Save video file
                video_filename = f"video_{session_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
                video_path = os.path.join(self.output_dir, video_filename)
                
                with open(video_path, 'wb') as f:
                    f.write(result['video_data'])
                
                logger.info(f"Video saved to: {video_path}")
                
                # Update job status
                job_info["status"] = "completed"
                job_info["completed_at"] = datetime.now().isoformat()
                job_info["video_path"] = video_path
                job_info["video_filename"] = video_filename
                self._save_jobs()
                
                return {
                    "status": "completed",
                    "message": "多镜头视频生成完成",
                    "video_path": video_path,
                    "video_filename": video_filename,
                    "shots_count": job_info.get("shots_count", len(job_info.get("shots", []))),
                    "images_count": job_info["images_count"],
                    "style": job_info["style"],
                    "category": job_info["category"],
                    "generation_type": job_info.get("generation_type", "multi_shot")
                }
            
            elif result['status'] == 'in_progress':
                job_info["status"] = "in_progress"
                self._save_jobs()
                
                return {
                    "status": "in_progress",
                    "message": result['message']
                }
            
            elif result['status'] == 'failed':
                job_info["status"] = "failed"
                job_info["error_message"] = result['message']
                self._save_jobs()
                
                return {
                    "status": "failed",
                    "message": result['message']
                }
            
            else:
                return {
                    "status": "unknown",
                    "message": result.get('message', '未知状态')
                }
                
        except Exception as e:
            error_msg = f"检查生成状态时出错: {str(e)}"
            logger.error(error_msg)
            
            return {
                "status": "error",
                "message": error_msg,
                "error_details": str(e)
            }
            
            # Update progress
            if progress_callback:
                progress_callback("生成完成")
            
            return {
                "status": "success",
                "message": "视频生成成功",
                "video_path": video_path,
                "video_filename": video_filename,
                "prompt": enhanced_prompt,
                "images_count": len(images),
                "style": style,
                "category": category
            }
            
        except Exception as e:
            error_msg = f"视频生成失败: {str(e)}"
            logger.error(error_msg)
            
            if progress_callback:
                progress_callback(f"错误: {str(e)}")
            
            return {
                "status": "error",
                "message": error_msg,
                "error_details": str(e)
            }
    
    def get_available_styles(self) -> Dict[str, list]:
        """Get all available styles"""
        return self.prompt_generator.get_all_styles()
    
    def get_flat_style_list(self) -> list:
        """Get flat list of all styles"""
        return self.prompt_generator.get_flat_style_list()
    
    def get_active_jobs(self) -> Dict[str, Dict]:
        """Get all active jobs"""
        return self.active_jobs.copy()
    
    def cleanup_old_videos(self, max_age_hours: int = 24):
        """
        Clean up old generated videos
        
        Args:
            max_age_hours: Maximum age of videos to keep in hours
        """
        try:
            current_time = datetime.now()
            
            for filename in os.listdir(self.output_dir):
                if filename.endswith('.mp4'):
                    file_path = os.path.join(self.output_dir, filename)
                    file_time = datetime.fromtimestamp(os.path.getctime(file_path))
                    
                    age_hours = (current_time - file_time).total_seconds() / 3600
                    
                    if age_hours > max_age_hours:
                        os.remove(file_path)
                        logger.info(f"Cleaned up old video: {filename}")
                        
        except Exception as e:
            logger.error(f"Error cleaning up videos: {str(e)}")
    
    # Keep the original synchronous method for backward compatibility
    def generate_video(
        self, 
        images: List[str], 
        style: str, 
        category: str,
        progress_callback: Callable[[str], None] = None
    ) -> Dict[str, Any]:
        """
        Generate video from images with specified style (synchronous version)
        
        Args:
            images: List of image file paths
            style: Selected style for the video
            category: Image category (nature/animals)
            progress_callback: Callback function to report progress
            
        Returns:
            Dictionary with generation result
        """
        try:
            # Validate inputs
            if not images:
                raise ValueError("No images provided")
            
            if len(images) > 6:
                raise ValueError("Maximum 6 images allowed")
            
            # Validate image files exist
            for img_path in images:
                if not os.path.exists(img_path):
                    raise FileNotFoundError(f"Image file not found: {img_path}")
            
            # Update progress
            if progress_callback:
                progress_callback("正在分析图片...")
            
            logger.info(f"Starting video generation with {len(images)} images, style: {style}, category: {category}")
            
            # Step 1: Generate prompt using Claude Sonnet
            if progress_callback:
                progress_callback("正在生成提示词...")
            
            base_prompt = self.aws_client.call_claude_sonnet(images, style, category)
            
            # Enhance prompt with style information
            enhanced_prompt = self.prompt_generator.enhance_prompt_with_style(base_prompt, style)
            
            logger.info(f"Generated enhanced prompt: {enhanced_prompt}")
            
            # Step 2: Generate video using Nova Reel (synchronous)
            if progress_callback:
                progress_callback("正在生成视频...")
            
            # For backward compatibility, we'll use the old synchronous method if it exists
            if hasattr(self.aws_client, 'call_nova_reel'):
                video_data = self.aws_client.call_nova_reel(enhanced_prompt, images)
            else:
                raise Exception("Synchronous video generation not available. Please use async method.")
            
            # Step 3: Save video file
            video_filename = f"video_{uuid.uuid4().hex}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
            video_path = os.path.join(self.output_dir, video_filename)
            
            with open(video_path, 'wb') as f:
                f.write(video_data)
            
            logger.info(f"Video saved to: {video_path}")
            
            # Update progress
            if progress_callback:
                progress_callback("生成完成")
            
            return {
                "status": "success",
                "message": "视频生成成功",
                "video_path": video_path,
                "video_filename": video_filename,
                "prompt": enhanced_prompt,
                "images_count": len(images),
                "style": style,
                "category": category
            }
            
        except Exception as e:
            error_msg = f"视频生成失败: {str(e)}"
            logger.error(error_msg)
            
            if progress_callback:
                progress_callback(f"错误: {str(e)}")
            
            return {
                "status": "error",
                "message": error_msg,
                "error_details": str(e)
            }
