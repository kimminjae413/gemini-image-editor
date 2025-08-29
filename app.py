# app.py - Gemini 2.5 Flash Image 편집 서버
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import boto3
import base64
import requests
import json
import threading
import time
import uuid
import os
from datetime import datetime
import tempfile
from PIL import Image
import io

# 환경변수 로드
load_dotenv()

app = Flask(__name__)
CORS(app)

# 설정 - 환경변수 사용
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', 'AIzaSyAbF6-puUPZqx7vpDvb_XNrDj3-a_e0ja4')
GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-image:generateContent"

AWS_ACCESS_KEY = os.getenv('AWS_ACCESS_KEY', 'AKIAQXUIYAFFQ2RRHFNH')
AWS_SECRET_KEY = os.getenv('AWS_SECRET_KEY', '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')
S3_BUCKET = "photo-to-video"
S3_REGION = "ap-northeast-2"

# AWS S3 클라이언트 초기화
s3_client = boto3.client(
    's3',
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_KEY,
    region_name=S3_REGION
)

class ImageEditingService:
    def __init__(self):
        self.processing_status = {}
        
    def upload_to_s3(self, image_data, filename):
        try:
            s3_client.put_object(
                Bucket=S3_BUCKET,
                Key=filename,
                Body=image_data,
                ContentType='image/jpeg',
                ACL='public-read'
            )
            return f"https://{S3_BUCKET}.s3.{S3_REGION}.amazonaws.com/{filename}"
        except Exception as e:
            print(f"S3 업로드 오류: {str(e)}")
            return None
    
    def gemini_edit_image(self, image_base64, edit_option, style_description):
        prompts = {
            "face_only": f"Keep the exact same hairstyle and hair color. Only change the facial features to: {style_description}. Maintain all other aspects including clothing and background.",
            "face_clothes": f"Keep the exact same hairstyle and hair color. Change the facial features and clothing to: {style_description}. Maintain the background.",
            "face_clothes_background": f"Keep only the exact same hairstyle and hair color. Transform the facial features, clothing, and background to: {style_description}."
        }
        
        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "inline_data": {
                                "mime_type": "image/jpeg",
                                "data": image_base64
                            }
                        },
                        {
                            "text": prompts.get(edit_option, prompts["face_only"])
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.8,
                "maxOutputTokens": 2048
            }
        }
        
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": GEMINI_API_KEY
        }
        
        try:
            response = requests.post(GEMINI_ENDPOINT, json=payload, headers=headers, timeout=60)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Gemini API 오류: {str(e)}")
            return None
    
    def post_process_image(self, gemini_result):
        try:
            if 'candidates' in gemini_result and len(gemini_result['candidates']) > 0:
                parts = gemini_result['candidates'][0]['content']['parts']
                for part in parts:
                    if 'inline_data' in part:
                        return part['inline_data']['data']
            return None
        except Exception as e:
            print(f"후처리 오류: {str(e)}")
            return None
    
    def process_image_async(self, task_id, image_base64, edit_option, style_description, user_id):
        try:
            self.processing_status[task_id] = {
                'status': 'processing', 
                'progress': 10,
                'message': 'Gemini API 호출 중...'
            }
            
            gemini_result = self.gemini_edit_image(image_base64, edit_option, style_description)
            
            if not gemini_result:
                self.processing_status[task_id] = {
                    'status': 'failed', 
                    'progress': 0,
                    'message': 'Gemini API 호출 실패'
                }
                return
            
            self.processing_status[task_id] = {
                'status': 'processing', 
                'progress': 60,
                'message': '이미지 편집 중...'
            }
            
            final_image_base64 = self.post_process_image(gemini_result)
            
            if not final_image_base64:
                self.processing_status[task_id] = {
                    'status': 'failed', 
                    'progress': 0,
                    'message': '이미지 처리 실패'
                }
                return
            
            self.processing_status[task_id] = {
                'status': 'processing', 
                'progress': 80,
                'message': '결과 이미지 저장 중...'
            }
            
            image_data = base64.b64decode(final_image_base64)
            filename = f"edited/{user_id}_{edit_option}_{int(time.time())}.jpg"
            
            s3_url = self.upload_to_s3(image_data, filename)
            
            if s3_url:
                self.processing_status[task_id] = {
                    'status': 'completed',
                    'progress': 100,
                    'message': '편집 완료',
                    'result_url': s3_url,
                    'edit_option': edit_option,
                    'style_description': style_description
                }
            else:
                self.processing_status[task_id] = {
                    'status': 'failed',
                    'progress': 0,
                    'message': 'S3 업로드 실패'
                }
                
        except Exception as e:
            print(f"비동기 처리 오류: {str(e)}")
            self.processing_status[task_id] = {
                'status': 'failed',
                'progress': 0,
                'message': f'처리 중 오류 발생: {str(e)}'
            }

image_service = ImageEditingService()

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'healthy',
        'service': 'Gemini Image Editing API',
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/edit-image', methods=['POST'])
def edit_image():
    try:
        data = request.json
        image_base64 = data.get('image')
        edit_option = data.get('edit_option', 'face_only')  
        style_description = data.get('style_description', '')
        user_id = data.get('user_id', f'user_{int(time.time())}')
        
        if not image_base64:
            return jsonify({'error': '이미지가 필요합니다'}), 400
            
        if not style_description:
            return jsonify({'error': '스타일 설명이 필요합니다'}), 400
        
        valid_options = ['face_only', 'face_clothes', 'face_clothes_background']
        if edit_option not in valid_options:
            return jsonify({'error': f'유효하지 않은 편집 옵션입니다. 사용 가능: {valid_options}'}), 400
        
        task_id = str(uuid.uuid4())
        result_filename = f"edited/{user_id}_{edit_option}_{int(time.time())}.jpg"
        s3_url = f"https://{S3_BUCKET}.s3.{S3_REGION}.amazonaws.com/{result_filename}"
        
        image_service.processing_status[task_id] = {
            'status': 'queued',
            'progress': 0,
            'message': '편집 요청이 접수되었습니다'
        }
        
        thread = threading.Thread(
            target=image_service.process_image_async,
            args=(task_id, image_base64, edit_option, style_description, user_id)
        )
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'success': True,
            'task_id': task_id,
            'status_url': f'/api/status/{task_id}',
            's3_url': s3_url,
            'message': '편집이 시작되었습니다. status_url로 진행상황을 확인하세요.',
            'edit_option': edit_option,
            'estimated_time': '30-60초'
        })
        
    except Exception as e:
        return jsonify({'error': f'서버 오류: {str(e)}'}), 500

@app.route('/api/status/<task_id>', methods=['GET'])
def get_status(task_id):
    try:
        if task_id not in image_service.processing_status:
            return jsonify({'error': '존재하지 않는 작업 ID입니다'}), 404
            
        status_info = image_service.processing_status[task_id]
        
        if status_info['status'] == 'completed':
            response = {
                'task_id': task_id,
                **status_info,
                'download_ready': True
            }
        else:
            response = {
                'task_id': task_id,
                **status_info,
                'download_ready': False
            }
            
        return jsonify(response)
        
    except Exception as e:
        return jsonify({'error': f'상태 확인 오류: {str(e)}'}), 500

@app.route('/api/upload-test', methods=['POST'])
def upload_test():
    try:
        if 'image' not in request.files:
            return jsonify({'error': '이미지 파일이 없습니다'}), 400
            
        file = request.files['image']
        if file.filename == '':
            return jsonify({'error': '파일이 선택되지 않았습니다'}), 400
        
        image_data = file.read()
        image_base64 = base64.b64encode(image_data).decode('utf-8')
        
        try:
            img = Image.open(io.BytesIO(image_data))
            image_info = {
                'format': img.format,
                'size': img.size,
                'mode': img.mode
            }
        except:
            image_info = {'error': '이미지 정보를 읽을 수 없습니다'}
        
        return jsonify({
            'success': True,
            'message': '이미지 업로드 성공',
            'image_base64': image_base64[:100] + '...',
            'image_size': len(image_base64),
            'image_info': image_info
        })
        
    except Exception as e:
        return jsonify({'error': f'업로드 오류: {str(e)}'}), 500

@app.route('/', methods=['GET'])
def index():
    return """
    <h1>Gemini 2.5 Flash Image 편집 API</h1>
    <h2>엔드포인트:</h2>
    <ul>
        <li><strong>POST /api/edit-image</strong> - 이미지 편집 요청</li>
        <li><strong>GET /api/status/{task_id}</strong> - 작업 상태 확인</li>
        <li><strong>POST /api/upload-test</strong> - 이미지 업로드 테스트</li>
        <li><strong>GET /health</strong> - 서버 상태 확인</li>
    </ul>
    
    <h2>편집 옵션:</h2>
    <ul>
        <li><strong>face_only</strong> - 얼굴만 변경 (헤어스타일 유지)</li>
        <li><strong>face_clothes</strong> - 얼굴 + 옷 변경 (헤어스타일 유지)</li>
        <li><strong>face_clothes_background</strong> - 얼굴 + 옷 + 배경 변경 (헤어스타일만 유지)</li>
    </ul>
    
    <h2>사용 예시:</h2>
    <pre>
curl -X POST http://223.130.134.220:5003/api/edit-image \\
  -H "Content-Type: application/json" \\
  -d '{
    "image": "base64_encoded_image",
    "edit_option": "face_only",
    "style_description": "young professional look with gentle smile",
    "user_id": "test_user"
  }'
    </pre>
    """

if __name__ == '__main__':
    print("Gemini 2.5 Flash Image 편집 서버 시작...")
    print(f"서버 주소: http://localhost:5003")
    print(f"API 문서: http://localhost:5003")
    print(f"S3 버킷: {S3_BUCKET}")
    
    app.run(debug=False, host='0.0.0.0', port=5003, threaded=True)
