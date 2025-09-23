import streamlit as st
import requests
from PIL import Image, ImageDraw
import io
import base64
import time
import uuid
from datetime import datetime

# 페이지 설정
st.set_page_config(
    page_title="AI 헤어스타일 변경 서비스",
    page_icon="💇‍♀️",
    layout="wide"
)

# 스타일링
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 2rem;
        border-radius: 10px;
        text-align: center;
        margin-bottom: 2rem;
    }
    .stButton > button {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        border-radius: 20px;
        padding: 0.5rem 2rem;
        font-weight: bold;
    }
    .success-box {
        background: #d4edda;
        color: #155724;
        padding: 1rem;
        border-radius: 5px;
        border: 1px solid #c3e6cb;
        margin: 1rem 0;
    }
    .info-box {
        background: #d1ecf1;
        color: #0c5460;
        padding: 1rem;
        border-radius: 5px;
        border: 1px solid #bee5eb;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

# 세션 상태 초기화
if 'user_id' not in st.session_state:
    st.session_state.user_id = str(uuid.uuid4())[:8]
    
if 'seed_images' not in st.session_state:
    st.session_state.seed_images = {}
    
if 'processing_history' not in st.session_state:
    st.session_state.processing_history = []

# VModel API 설정 (비밀키는 Streamlit Secrets에서 관리)
VMODEL_API_KEY = st.secrets.get("VMODEL_API_KEY", "")

def resize_image_if_needed(image, max_size=1024):
    """이미지가 너무 크면 자동으로 리사이즈"""
    width, height = image.size
    
    # 이미지가 max_size보다 크면 비율을 유지하며 리사이즈
    if width > max_size or height > max_size:
        # 긴 쪽을 기준으로 비율 계산
        if width > height:
            new_width = max_size
            new_height = int(height * (max_size / width))
        else:
            new_height = max_size
            new_width = int(width * (max_size / height))
        
        # 리샘플링으로 고품질 리사이즈
        resized_image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        return resized_image, True  # 리사이즈됨을 표시
    
    return image, False  # 리사이즈 안됨

def validate_image(image):
    """이미지 유효성 검사 및 자동 리사이즈"""
    try:
        if image.size[0] < 100 or image.size[1] < 100:
            return False, "이미지 크기가 너무 작습니다 (최소 100x100)", image
        
        # 자동 리사이즈
        processed_image, was_resized = resize_image_if_needed(image, max_size=1024)
        
        if was_resized:
            original_size = f"{image.size[0]}x{image.size[1]}"
            new_size = f"{processed_image.size[0]}x{processed_image.size[1]}"
            message = f"이미지 크기를 자동 조정했습니다: {original_size} → {new_size}"
        else:
            message = "유효한 이미지입니다"
        
        return True, message, processed_image
        
    except Exception as e:
        return False, f"이미지 검증 실패: {e}", image

def upload_image_to_imgur(image):
    """Imgur에 이미지 업로드하고 URL 반환"""
    try:
        # 이미지를 base64로 변환
        buffer = io.BytesIO()
        image.save(buffer, format='PNG')
        img_b64 = base64.b64encode(buffer.getvalue()).decode()
        
        # Imgur API 호출
        headers = {
            'Authorization': 'Client-ID 546c25a59c58ad7',  # 공개 클라이언트 ID
            'Content-Type': 'application/json',
        }
        
        data = {
            'image': img_b64,
            'type': 'base64',
            'title': 'temp_upload'
        }
        
        response = requests.post(
            'https://api.imgur.com/3/image',
            headers=headers,
            json=data,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                return result['data']['link']
        
        # Imgur 실패시 fallback으로 임시 서비스 사용
        st.warning("이미지 업로드 서비스에 일시적 문제가 있습니다. 다른 방법을 시도합니다...")
        return upload_to_tempfile_io(image)
        
    except Exception as e:
        st.warning(f"이미지 업로드 중 오류: {e}. 다른 방법을 시도합니다...")
        return upload_to_tempfile_io(image)

def upload_to_tempfile_io(image):
    """대안 임시 파일 호스팅 서비스"""
    try:
        buffer = io.BytesIO()
        image.save(buffer, format='PNG')
        buffer.seek(0)
        
        files = {'file': ('image.png', buffer, 'image/png')}
        
        response = requests.post(
            'https://tmpfiles.org/api/v1/upload',
            files=files,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            if 'data' in result and 'url' in result['data']:
                # tmpfiles.org URL을 직접 액세스 가능한 형태로 변환
                temp_url = result['data']['url']
                direct_url = temp_url.replace('https://tmpfiles.org/', 'https://tmpfiles.org/dl/')
                return direct_url
                
    except Exception as e:
        st.error(f"모든 이미지 업로드 서비스가 실패했습니다: {e}")
        return None

def process_with_vmodel_api(seed_image, ref_image):
    """VModel API로 헤어 변경 처리"""
    
    if not VMODEL_API_KEY:
        st.error("⚠️ VModel API 키가 설정되지 않았습니다. Streamlit Secrets에서 VMODEL_API_KEY를 설정해주세요.")
        return None
    
    try:
        # 이미지를 실제 URL로 업로드
        st.info("이미지를 업로드하고 있습니다...")
        target_url = upload_image_to_imgur(seed_image)
        swap_url = upload_image_to_imgur(ref_image)
        
        if not target_url or not swap_url:
            st.error("이미지 업로드에 실패했습니다. 잠시 후 다시 시도해주세요.")
            return None
        
        st.success("이미지 업로드 완료!")
        
        # VModel API 페이로드 (정확한 헤어스타일 모델 사용)
        payload = {
            "version": "5c0440717a995b0bbd93377bd65dbb4fe360f67967c506aa6bd8f6b660733a7e",
            "input": {
                "source": swap_url,      # 헤어스타일 참조 이미지
                "target": target_url,    # 변경할 사람 이미지
                "disable_safety_checker": False,
                "mode": "fast"
            }
        }
        
        headers = {
            "Authorization": f"Bearer {VMODEL_API_KEY}",
            "Content-Type": "application/json"
        }
        
        # Task 생성 API 호출
        response = requests.post(
            "https://api.vmodel.ai/api/tasks/v1/create", 
            json=payload, 
            headers=headers, 
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            
            # 응답 구조 확인
            if result.get('code') == 200 and 'result' in result:
                task_id = result['result'].get('task_id')
                if task_id:
                    return poll_vmodel_task(task_id)
            
        # 에러 응답 표시
        try:
            error_data = response.json()
            st.error(f"API 오류: {error_data}")
        except:
            st.error(f"API 호출 실패: HTTP {response.status_code}")
        
        return None
        
    except Exception as e:
        st.error(f"처리 중 오류 발생: {e}")
        return None

def poll_vmodel_task(task_id, max_attempts=60):
    """VModel Task 상태 폴링 - 60초로 연장"""
    headers = {"Authorization": f"Bearer {VMODEL_API_KEY}"}
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for attempt in range(max_attempts):
        try:
            response = requests.get(
                f"https://api.vmodel.ai/api/tasks/v1/get/{task_id}", 
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                
                # 응답 구조 확인
                if result.get('code') == 200 and 'result' in result:
                    task_result = result['result']
                    status = task_result.get('status', 'processing')
                    
                    # 진행률 업데이트 (60초 기준)
                    progress = min(95, (attempt + 1) * 1.5)
                    progress_bar.progress(progress)
                    
                    if status == 'processing':
                        status_text.text(f"AI 처리 중... ({progress:.0f}%) - {attempt+1}/60회 시도")
                    elif status == 'starting':
                        status_text.text("AI 모델 시작 중...")
                    elif status == 'succeeded':
                        progress_bar.progress(100)
                        status_text.text("완료!")
                        
                        # 결과 이미지 URL 가져오기
                        output = task_result.get('output', [])
                        if output and len(output) > 0:
                            result_url = output[0]
                            img_response = requests.get(result_url, headers=headers, timeout=30)
                            if img_response.status_code == 200:
                                return Image.open(io.BytesIO(img_response.content))
                        
                        st.error("결과 이미지를 찾을 수 없습니다.")
                        return None
                        
                    elif status == 'failed':
                        error_msg = task_result.get('error', '알 수 없는 오류')
                        st.error(f"처리 실패: {error_msg}")
                        return None
                    
                    elif status == 'canceled':
                        st.error("작업이 취소되었습니다.")
                        return None
                
                time.sleep(1)  # 1초마다 체크
            else:
                st.error(f"Task 상태 확인 실패: HTTP {response.status_code}")
                return None
                
        except Exception as e:
            if attempt == max_attempts - 1:
                st.error(f"처리 시간 초과 (60초): {e}")
                return None
            time.sleep(1)
    
    st.error("처리 시간 초과 - VModel 서버가 응답하지 않습니다")
    return None

# 메인 UI
st.markdown("""
<div class="main-header">
    <h1>💇‍♀️ AI 헤어스타일 변경 서비스</h1>
    <p>AI로 원하는 헤어스타일을 미리 체험해보세요!</p>
</div>
""", unsafe_allow_html=True)

# API 키 체크
if not VMODEL_API_KEY:
    st.error("""
    ⚠️ **VModel API 키가 필요합니다!**
    
    1. [VModel.ai](https://vmodel.ai)에서 API 키 발급
    2. Streamlit Cloud 대시보드 → Settings → Secrets
    3. 다음 내용 추가:
    ```
    VMODEL_API_KEY = "your-api-key-here"
    ```
    """)
    st.stop()

# 사이드바
with st.sidebar:
    st.header("🎛️ 설정")
    st.info(f"사용자 ID: {st.session_state.user_id}")
    
    if st.button("🔄 새 세션 시작"):
        st.session_state.clear()
        st.rerun()
    
    st.divider()
    
    st.markdown("""
    ### 📋 사용 방법
    1. **시드 이미지 업로드** (본인 얼굴)
    2. **참조 이미지 업로드** (원하는 헤어스타일)
    3. **AI 변환 실행**
    4. **결과 확인 및 다운로드**
    
    ### 💡 팁
    - 정면을 바라보는 고화질 사진 사용
    - 머리카락이 명확히 보이는 이미지
    - 배경이 단순한 사진 권장
    """)

# 메인 탭
tab1, tab2, tab3 = st.tabs(["🎨 헤어 변경", "📸 시드 관리", "📝 처리 기록"])

with tab2:
    st.header("📸 시드 이미지 관리")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        seed_file = st.file_uploader(
            "시드 이미지 업로드 (본인 얼굴)", 
            type=['png', 'jpg', 'jpeg'],
            help="어떤 크기든 OK! 자동으로 최적 크기로 조정됩니다"
        )
        
        if seed_file:
            seed_image = Image.open(seed_file)
            
            # 자동 리사이즈 포함 검증
            is_valid, message, processed_image = validate_image(seed_image)
            
            if is_valid:
                st.image(processed_image, caption="미리보기 (처리된 이미지)", width=300)
                st.success(message)
                
                # 이미지 정보 표시
                st.caption(f"원본 파일명: {seed_file.name}")
                st.caption(f"처리된 크기: {processed_image.size}")
            else:
                st.image(seed_image, caption="미리보기", width=300)
                st.error(message)
                processed_image = seed_image
    
    with col2:
        if seed_file and st.button("💾 시드 저장", type="primary"):
            seed_image = Image.open(seed_file)
            is_valid, message, processed_image = validate_image(seed_image)
            
            if is_valid:
                # 처리된 이미지로 저장
                seed_id = str(uuid.uuid4())[:8]
                st.session_state.seed_images[seed_id] = {
                    'image': processed_image,  # 처리된 이미지 저장
                    'filename': seed_file.name,
                    'original_size': seed_image.size,
                    'processed_size': processed_image.size,
                    'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
                
                st.markdown(f"""
                <div class="success-box">
                    ✅ 시드 저장 완료!<br>
                    ID: {seed_id}<br>
                    {message}
                </div>
                """, unsafe_allow_html=True)
                time.sleep(1)
                st.rerun()
            else:
                st.error(message)
    
    # 저장된 시드 목록
    if st.session_state.seed_images:
        st.divider()
        st.subheader("💾 저장된 시드 이미지")
        
        for seed_id, seed_data in st.session_state.seed_images.items():
            with st.expander(f"🖼️ {seed_data['filename']} ({seed_data['created_at']})"):
                col1, col2 = st.columns([1, 1])
                
                with col1:
                    st.image(seed_data['image'], width=200)
                
                with col2:
                    st.write(f"**ID**: {seed_id}")
                    st.write(f"**크기**: {seed_data['image'].size}")
                    
                    if st.button(f"🗑️ 삭제", key=f"delete_{seed_id}"):
                        del st.session_state.seed_images[seed_id]
                        st.rerun()

with tab1:
    st.header("🎨 헤어스타일 변경")
    
    if not st.session_state.seed_images:
        st.warning("먼저 시드 이미지를 업로드해주세요!")
        st.info("👈 **시드 관리** 탭에서 시드 이미지를 추가하세요")
    else:
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.subheader("1️⃣ 시드 이미지 선택")
            
            seed_options = {
                f"{data['filename']} ({data['created_at']})": seed_id 
                for seed_id, data in st.session_state.seed_images.items()
            }
            
            selected_seed_name = st.selectbox("시드 선택", list(seed_options.keys()))
            selected_seed_id = seed_options[selected_seed_name]
            selected_seed_data = st.session_state.seed_images[selected_seed_id]
            
            st.image(selected_seed_data['image'], caption="선택된 시드", width=250)
        
        with col2:
            st.subheader("2️⃣ 헤어 참조 이미지")
            
            ref_file = st.file_uploader(
                "원하는 헤어스타일 이미지", 
                type=['png', 'jpg', 'jpeg'],
                help="원하는 헤어스타일이 담긴 사진 (최대 4096x4096)"
            )
            
            if ref_file:
                ref_image = Image.open(ref_file)
                st.image(ref_image, caption="참조 이미지", width=250)
        
        # 처리 실행
        if ref_file:
            st.divider()
            
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                if st.button("🚀 AI 헤어 변경 시작", type="primary", use_container_width=True):
                    
                    ref_image = Image.open(ref_file)
                    
                    # 참조 이미지도 자동 리사이즈
                    is_valid, message, processed_ref_image = validate_image(ref_image)
                    if not is_valid:
                        st.error(f"참조 이미지 오류: {message}")
                        st.stop()
                    
                    if processed_ref_image.size != ref_image.size:
                        st.info(f"참조 이미지 크기 조정: {ref_image.size} → {processed_ref_image.size}")
                    
                    with st.spinner("AI가 헤어스타일을 변경하고 있습니다..."):
                        start_time = time.time()
                        
                        # AI 처리 (자동 리사이즈된 이미지 사용)
                        result_image = process_with_vmodel_api(
                            selected_seed_data['image'],  # 이미 처리된 시드 이미지
                            processed_ref_image  # 처리된 참조 이미지
                        )
                        
                        processing_time = time.time() - start_time
                        
                        if result_image:
                            st.success(f"✨ 헤어 변경 완료! (소요시간: {processing_time:.1f}초)")
                            
                            # 처리 기록 저장
                            history_item = {
                                'id': str(uuid.uuid4())[:8],
                                'seed_filename': selected_seed_data['filename'],
                                'ref_filename': ref_file.name,
                                'result_image': result_image,
                                'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                'processing_time': processing_time
                            }
                            st.session_state.processing_history.append(history_item)
                            
                            # 결과 표시
                            col1, col2, col3 = st.columns([1, 2, 1])
                            with col2:
                                st.image(result_image, caption="변경 결과", width=400)
                                
                                # 다운로드
                                img_buffer = io.BytesIO()
                                result_image.save(img_buffer, format='PNG')
                                st.download_button(
                                    "💾 결과 다운로드",
                                    img_buffer.getvalue(),
                                    f"hair_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png",
                                    "image/png",
                                    use_container_width=True
                                )
                        else:
                            st.error("헤어 변경에 실패했습니다. 다시 시도해주세요.")

with tab3:
    st.header("📝 처리 기록")
    
    if not st.session_state.processing_history:
        st.info("아직 처리 기록이 없습니다.")
    else:
        st.write(f"총 {len(st.session_state.processing_history)}개의 처리 기록")
        
        # 최신 순으로 정렬
        history = sorted(
            st.session_state.processing_history, 
            key=lambda x: x['created_at'], 
            reverse=True
        )
        
        for item in history:
            with st.expander(f"🕐 {item['created_at']} - {item['seed_filename']} → {item['ref_filename']}"):
                col1, col2 = st.columns([1, 1])
                
                with col1:
                    st.write(f"**처리 ID**: {item['id']}")
                    st.write(f"**시드 파일**: {item['seed_filename']}")
                    st.write(f"**참조 파일**: {item['ref_filename']}")
                    st.write(f"**처리 시간**: {item['processing_time']:.1f}초")
                
                with col2:
                    st.image(item['result_image'], caption="처리 결과", width=300)
                    
                    # 다운로드
                    img_buffer = io.BytesIO()
                    item['result_image'].save(img_buffer, format='PNG')
                    st.download_button(
                        "다운로드",
                        img_buffer.getvalue(),
                        f"result_{item['id']}.png",
                        "image/png",
                        key=f"download_{item['id']}"
                    )

# 푸터
st.divider()
st.markdown("""
<div style="text-align: center; color: #666; padding: 1rem;">
    💇‍♀️ AI Hair Style Transfer | Made with ❤️ using Streamlit Cloud<br>
    <small>세션 종료시 데이터가 삭제됩니다. 중요한 결과는 다운로드하세요!</small>
</div>
""", unsafe_allow_html=True)
