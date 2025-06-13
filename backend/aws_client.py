import boto3
import json
import base64
import time
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class AWSBedrockClient:
    def __init__(self, region_name: str = "us-east-1"):
        """
        Initialize AWS Bedrock client
        
        Args:
            region_name: AWS region name
        """
        self.region_name = region_name
        self.bedrock_client = boto3.client('bedrock-runtime', region_name=region_name)
        
    def encode_image_to_base64(self, image_path: str) -> str:
        """
        Encode image file to base64 string
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Base64 encoded image string
        """
        try:
            with open(image_path, 'rb') as image_file:
                return base64.b64encode(image_file.read()).decode('utf-8')
        except Exception as e:
            logger.error(f"Error encoding image {image_path}: {str(e)}")
            raise
    
    def call_claude_sonnet(self, images: List[str], style: str, category: str) -> List[Dict[str, Any]]:
        """
        Call Claude Sonnet 3.7 to generate video shot prompts for multi-shot video
        
        Args:
            images: List of image file paths
            style: Selected style for the video
            category: Image category (nature/animals)
            
        Returns:
            List of shot dictionaries for Nova Reel multi-shot generation
        """
        try:
            # Encode images to base64
            encoded_images = []
            for i, img_path in enumerate(images):
                encoded_img = self.encode_image_to_base64(img_path)
                encoded_images.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": encoded_img
                    }
                })
            
            # Create the message content for multi-shot generation
            content = [
                {
                    "type": "text",
                    "text": f"""You are an expert video prompt generator for Amazon Nova Reel's multi-shot video generation.

Analyze the provided {len(images)} {category} images and create individual shot descriptions for each image with the following style: {style}.

For each image, generate a detailed shot description that:
1. Describes the specific visual elements and composition in that image
2. Incorporates the {style} style characteristics
3. Includes appropriate camera movements (drone shots, tracking, panning, etc.)
4. Specifies visual effects and atmosphere suitable for the style
5. Ensures smooth narrative flow between shots

Please respond with a JSON array containing {len(images)} shot objects, each with:
- "text": Detailed shot description (50-80 words)
- "image_index": The index of the corresponding image (0 to {len(images)-1})

The shots should tell a cohesive visual story that flows naturally from one to the next.

Example format:
[
  {{"text": "Epic aerial rise revealing the landscape, dramatic documentary style with dark atmospheric mood", "image_index": 0}},
  {{"text": "Sweeping drone shot across surface, morning sunlight casting long shadows, documentary style", "image_index": 1}}
]"""
                }
            ]
            
            # Add images to content
            content.extend(encoded_images)
            
            # Prepare the request body
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 1000,
                "messages": [
                    {
                        "role": "user",
                        "content": content
                    }
                ]
            }
            
            # Call Claude Sonnet 3.7
            response = self.bedrock_client.invoke_model(
                modelId="us.anthropic.claude-3-7-sonnet-20250219-v1:0",
                body=json.dumps(body)
            )
            
            # Parse response
            response_body = json.loads(response['body'].read())
            generated_text = response_body['content'][0]['text']
            
            logger.info(f"Generated shot descriptions: {generated_text}")
            
            # Parse JSON response
            try:
                # Extract JSON from the response (in case there's extra text)
                import re
                json_match = re.search(r'\[.*\]', generated_text, re.DOTALL)
                if json_match:
                    json_str = json_match.group()
                    shot_descriptions = json.loads(json_str)
                else:
                    # Fallback: try to parse the entire response as JSON
                    shot_descriptions = json.loads(generated_text)
                
                # Create shot objects with encoded images
                shots = []
                for i, shot_desc in enumerate(shot_descriptions):
                    if i < len(images):  # Ensure we don't exceed available images
                        image_index = shot_desc.get('image_index', i)
                        if image_index < len(images):
                            shots.append({
                                "text": shot_desc['text'],
                                "image": {
                                    "format": "jpeg",
                                    "source": {
                                        "bytes": self.encode_image_to_base64(images[image_index])
                                    }
                                }
                            })
                
                logger.info(f"Created {len(shots)} shots for multi-shot video")
                return shots
                
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"Failed to parse JSON response, falling back to single shot: {e}")
                # Fallback: create a single shot with all images combined
                return [{
                    "text": f"A {style} style video showcasing {category} imagery with cinematic camera movements and smooth transitions",
                    "image": {
                        "format": "jpeg", 
                        "source": {
                            "bytes": self.encode_image_to_base64(images[0])
                        }
                    }
                }]
            
        except Exception as e:
            logger.error(f"Error calling Claude Sonnet: {str(e)}")
            raise Exception(f"Failed to generate shot descriptions with Claude: {str(e)}")
    
    def start_async_nova_reel(self, shots: List[Dict[str, Any]], images: List[str]) -> str:
        """
        Start asynchronous Amazon Nova Reel multi-shot video generation
        
        Args:
            shots: List of shot dictionaries with text and image data
            images: List of image file paths (for reference)
            
        Returns:
            Job ID for tracking the generation process
        """
        try:
            import random
            
            # Prepare the request body for Nova Reel multi-shot generation
            body = {
                "taskType": "MULTI_SHOT_MANUAL",
                "multiShotManualParams": {
                    "shots": shots
                },
                "videoGenerationConfig": {
                    "fps": 24,
                    "dimension": "1280x720",
                    "seed": random.randint(0, 2147483648)
                }
            }
            
            logger.info(f"Starting Nova Reel multi-shot generation with {len(shots)} shots")
            
            # Start async Nova Reel generation
            response = self.bedrock_client.start_async_invoke(
                modelId="amazon.nova-reel-v1:1",
                modelInput=body,
                outputDataConfig={"s3OutputDataConfig": {"s3Uri": "s3://alex-bedrock-nova-video/uploads/"}}
            )
            
            # Extract job ID
            job_id = response['invocationArn']
            logger.info(f"Started Nova Reel async multi-shot generation with job ID: {job_id}")
            return job_id
                
        except Exception as e:
            logger.error(f"Error starting async Nova Reel multi-shot: {str(e)}")
            raise Exception(f"Failed to start multi-shot video generation with Nova Reel: {str(e)}")
    
    def get_async_nova_reel_result(self, job_id: str) -> Dict[str, Any]:
        """
        Get the result of asynchronous Nova Reel video generation
        
        Args:
            job_id: Job ID returned from start_async_nova_reel
            
        Returns:
            Dictionary with status and result data
        """
        try:
            # Get async invoke result
            response = self.bedrock_client.get_async_invoke(
                invocationArn=job_id
            )
            
            status = response['status']
            
            if status == 'Completed':
                # Get the output location
                output_data_config = response.get('outputDataConfig', {})
                s3_uri = output_data_config.get('s3OutputDataConfig', {}).get('s3Uri', '')
                
                if s3_uri:
                    # Download video from S3
                    video_data = self._download_from_s3(s3_uri)
                    return {
                        'status': 'completed',
                        'video_data': video_data,
                        'message': '视频生成完成'
                    }
                else:
                    # Try to get result from response body if available
                    if 'outputDataConfig' in response and 'outputData' in response['outputDataConfig']:
                        output_data = response['outputDataConfig']['outputData']
                        if 'videoGenerationResult' in output_data:
                            video_data = output_data['videoGenerationResult']['video']
                            return {
                                'status': 'completed',
                                'video_data': base64.b64decode(video_data),
                                'message': '视频生成完成'
                            }
                    
                    return {
                        'status': 'error',
                        'message': '无法获取生成的视频数据'
                    }
            
            elif status == 'InProgress':
                return {
                    'status': 'in_progress',
                    'message': '视频正在生成中...'
                }
            
            elif status == 'Failed':
                failure_message = response.get('failureMessage', '未知错误')
                return {
                    'status': 'failed',
                    'message': f'视频生成失败: {failure_message}'
                }
            
            else:
                return {
                    'status': 'unknown',
                    'message': f'未知状态: {status}'
                }
                
        except Exception as e:
            logger.error(f"Error getting async Nova Reel result: {str(e)}")
            return {
                'status': 'error',
                'message': f'获取生成结果时出错: {str(e)}'
            }
    
    def _download_from_s3(self, s3_uri: str) -> bytes:
        """
        Download video data from S3
        
        Args:
            s3_uri: S3 URI of the generated video
            
        Returns:
            Video data as bytes
        """
        try:
            # Parse S3 URI
            if not s3_uri.startswith('s3://'):
                raise ValueError(f"Invalid S3 URI: {s3_uri}")
            
            # Remove s3:// prefix and split bucket and key
            s3_path = s3_uri[5:]  # Remove 's3://'
            bucket_name, key = s3_path.split('/', 1)
            
            # Create S3 client
            s3_client = boto3.client('s3', region_name=self.region_name)
            
            # Try to download output.mp4 first (Nova Reel generates this as the main video)
            try:
                video_key = f"{key}/output.mp4"
                logger.info(f"Trying to download: s3://{bucket_name}/{video_key}")
                response = s3_client.get_object(Bucket=bucket_name, Key=video_key)
                return response['Body'].read()
            except s3_client.exceptions.NoSuchKey:
                # If output.mp4 doesn't exist, list files and find any .mp4 file
                logger.info("output.mp4 not found, looking for other video files...")
                objects = s3_client.list_objects_v2(Bucket=bucket_name, Prefix=key)
                
                if 'Contents' not in objects:
                    raise Exception("No files found in S3 output directory")
                
                # Look for any .mp4 file
                for obj in objects['Contents']:
                    obj_key = obj['Key']
                    if obj_key.endswith('.mp4'):
                        logger.info(f"Found video file: {obj_key}")
                        response = s3_client.get_object(Bucket=bucket_name, Key=obj_key)
                        return response['Body'].read()
                
                raise Exception("No video file (.mp4) found in S3 output directory")
            
        except Exception as e:
            logger.error(f"Error downloading from S3: {str(e)}")
            raise Exception(f"Failed to download video from S3: {str(e)}")
